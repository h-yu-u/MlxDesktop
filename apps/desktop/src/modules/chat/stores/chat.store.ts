import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { runtimeClient } from '../../../shared/api/runtime'
import {
  initialChatState,
  reduceChatState,
  type ChatState,
} from '../domain/chat-state'
import {
  numberField,
  readConversation,
  readConversations,
  readMessages,
  readModels,
  stringField,
  type ConversationOption,
  type ModelOption,
} from './chat-mappers'

interface RuntimeEventLike {
  type: string
  payload: Record<string, unknown>
}

export const useChatStore = defineStore('chat', () => {
  const state = ref<ChatState>({ ...initialChatState })
  const models = ref<ModelOption[]>([])
  const conversations = ref<ConversationOption[]>([])
  const conversationId = ref<string | null>(null)
  const selectedModelId = ref('builtin-fake-text')
  const maxTokens = ref(512)
  const temperature = ref(0.7)
  const busy = computed(() => state.value.status === 'sending')
  let streamAbort: AbortController | undefined

  async function loadWorkspace(): Promise<void> {
    state.value = { ...state.value, status: 'loading', error: null }
    try {
      const client = await runtimeClient()
      const [modelResult, conversationResult] = await Promise.all([
        client.get('/internal/v1/models'),
        client.get('/internal/v1/conversations'),
      ])
      models.value = readModels(modelResult)
      conversations.value = readConversations(conversationResult)
      if (!models.value.some((model) => model.id === selectedModelId.value) && models.value[0]) {
        selectedModelId.value = models.value[0].id
      }
      state.value = { ...state.value, status: 'idle' }
      if (conversationId.value) await openConversation(conversationId.value)
    } catch (error) {
      state.value = { ...state.value, status: 'error', error: errorMessage(error) }
    }
  }

  async function newConversation(): Promise<void> {
    const client = await runtimeClient()
    const result = await client.post('/internal/v1/conversations', {
      title: '新对话',
      model_id: selectedModelId.value,
    })
    const item = readConversation(result)
    conversationId.value = item.id
    conversations.value = [item, ...conversations.value]
    state.value = reduceChatState(state.value, {
      type: 'conversation.loaded',
      messages: [],
    })
  }

  async function openConversation(id: string): Promise<void> {
    const client = await runtimeClient()
    const result = await client.get(
      `/internal/v1/conversations/${encodeURIComponent(id)}`,
    )
    const item = readConversation(result)
    conversationId.value = id
    selectedModelId.value = item.modelId ?? selectedModelId.value
    state.value = reduceChatState(state.value, {
      type: 'conversation.loaded',
      messages: readMessages(result),
    })
  }

  async function send(content: string, files: File[] = []): Promise<boolean> {
    if ((!content.trim() && !files.length) || busy.value) return false
    if (!conversationId.value) await newConversation()
    const client = await runtimeClient()
    const attachments = await Promise.all(files.map((file) => client.uploadImage(file)))
    const prompt = content.trim() || '请描述图片内容。'
    const after = await currentEventSequence(client)
    const pendingEvents: RuntimeEventLike[] = []
    abortEventStream()
    streamAbort = new AbortController()
    const activeAbort = streamAbort
    const onEvent = (event: RuntimeEventLike): void => {
      if (!state.value.activeJobId) {
        pendingEvents.push(event)
        return
      }
      applyEvent(event)
    }
    void client.subscribe(onEvent, activeAbort.signal, after).catch((error: unknown) => {
      if (!activeAbort.signal.aborted) {
        state.value = { ...state.value, error: errorMessage(error) }
      }
    })
    try {
      const result = await client.post(
        `/internal/v1/conversations/${conversationId.value}/messages`,
        {
          content: prompt,
          model_id: selectedModelId.value,
          max_tokens: maxTokens.value,
          temperature: temperature.value,
          attachment_ids: attachments.map((item) => item.id),
        },
      )
      const jobId = stringField(result, 'jobId')
      if (!jobId) throw new Error('Runtime 未返回任务 ID')
      state.value = reduceChatState(state.value, {
        type: 'send.started',
        userMessage: {
          id: crypto.randomUUID(),
          role: 'user',
          content: prompt,
          state: 'complete',
          attachments,
        },
        assistantMessage: {
          id: jobId,
          role: 'assistant',
          content: '',
          state: 'streaming',
        },
      })
      for (const event of pendingEvents) applyEvent(event)
      return true
    } catch (error) {
      abortEventStream()
      throw error
    }
  }

  async function cancel(): Promise<void> {
    const jobId = state.value.activeJobId
    if (!jobId || !conversationId.value) return
    const client = await runtimeClient()
    await client.post(
      `/internal/v1/conversations/${conversationId.value}/cancel?job_id=${encodeURIComponent(jobId)}`,
    )
  }

  function applyEvent(event: RuntimeEventLike): void {
    const jobId = stringField(event.payload, 'job_id')
    if (!jobId) return
    if (event.type === 'generation.delta') {
      state.value = reduceChatState(state.value, {
        type: event.type,
        jobId,
        text: stringField(event.payload, 'text') ?? '',
      })
      return
    }
    const terminalEvent = terminalChatEvent(event.type)
    if (!terminalEvent) return
    state.value = reduceChatState(state.value, { ...terminalEvent, jobId })
    abortEventStream()
    if (event.type === 'job.succeeded') void refreshConversationList()
  }

  async function refreshConversationList(): Promise<void> {
    const client = await runtimeClient()
    conversations.value = readConversations(await client.get('/internal/v1/conversations'))
    if (conversationId.value) await openConversation(conversationId.value)
  }

  function abortEventStream(): void {
    streamAbort?.abort()
    streamAbort = undefined
  }

  return {
    state,
    models,
    conversations,
    conversationId,
    selectedModelId,
    maxTokens,
    temperature,
    busy,
    loadWorkspace,
    newConversation,
    openConversation,
    send,
    cancel,
  }
})

async function currentEventSequence(
  client: Awaited<ReturnType<typeof runtimeClient>>,
): Promise<number> {
  const info = await client.get('/internal/v1/runtime/info')
  return numberField(info, 'event_sequence') ?? 0
}

function terminalChatEvent(type: string):
  | { type: 'generation.completed' }
  | { type: 'generation.cancelled' }
  | { type: 'generation.failed'; message: string }
  | undefined {
  if (type === 'job.succeeded') return { type: 'generation.completed' }
  if (type === 'job.cancelled') return { type: 'generation.cancelled' }
  if (type === 'job.failed') {
    return { type: 'generation.failed', message: '生成失败，请检查 Runtime 状态' }
  }
  return undefined
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Runtime 请求失败'
}
