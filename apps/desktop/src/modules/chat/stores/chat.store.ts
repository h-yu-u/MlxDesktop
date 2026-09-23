import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { runtimeClient } from '../../../shared/api/runtime'
import { initialChatState, reduceChatState, type ChatMessage, type ChatState } from '../domain/chat-state'

interface ModelOption {
  id: string
  displayName: string
  engine: string
  inputModalities: string[]
  multiImage: boolean
  state?: string
}
interface ConversationOption { id: string; title: string; modelId: string | null }

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
        client.get('/internal/v1/models'), client.get('/internal/v1/conversations'),
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
    const result = await client.post('/internal/v1/conversations', { title: '新对话', model_id: selectedModelId.value })
    const item = readConversation(result)
    conversationId.value = item.id
    conversations.value = [item, ...conversations.value]
    state.value = reduceChatState(state.value, { type: 'conversation.loaded', messages: [] })
  }

  async function openConversation(id: string): Promise<void> {
    const client = await runtimeClient()
    const result = await client.get(`/internal/v1/conversations/${encodeURIComponent(id)}`)
    const item = readConversation(result)
    conversationId.value = id
    selectedModelId.value = item.modelId ?? selectedModelId.value
    state.value = reduceChatState(state.value, { type: 'conversation.loaded', messages: readMessages(result) })
  }

  async function send(content: string, files: File[] = []): Promise<void> {
    if ((!content.trim() && !files.length) || busy.value) return
    if (!conversationId.value) await newConversation()
    const client = await runtimeClient()
    const attachments = await Promise.all(files.map((file) => client.uploadImage(file)))
    const info = await client.get('/internal/v1/runtime/info')
    const after = numberField(info, 'event_sequence') ?? 0
    streamAbort = new AbortController()
    const pendingEvents: Array<{ type: string; payload: Record<string, unknown> }> = []
    const onEvent = (event: { type: string; payload: Record<string, unknown> }) => {
      if (!state.value.activeJobId) { pendingEvents.push(event); return }
      applyEvent(event)
    }
    void client.subscribe(onEvent, streamAbort.signal, after).catch((error: unknown) => {
      if (!streamAbort?.signal.aborted) state.value = { ...state.value, error: errorMessage(error) }
    })
    const result = await client.post(`/internal/v1/conversations/${conversationId.value}/messages`, {
      content: content.trim() || '请描述图片内容。', model_id: selectedModelId.value,
      max_tokens: maxTokens.value, temperature: temperature.value,
      attachment_ids: attachments.map((item) => item.id),
    })
    const jobId = stringField(result, 'jobId')
    if (!jobId) throw new Error('Runtime 未返回任务 ID')
    state.value = reduceChatState(state.value, {
      type: 'send.started',
      userMessage: {
        id: crypto.randomUUID(), role: 'user', content: content.trim() || '请描述图片内容。',
        state: 'complete', attachments,
      },
      assistantMessage: { id: jobId, role: 'assistant', content: '', state: 'streaming' },
    })
    for (const event of pendingEvents) applyEvent(event)
  }

  async function cancel(): Promise<void> {
    const jobId = state.value.activeJobId
    if (!jobId || !conversationId.value) return
    const client = await runtimeClient()
    await client.post(`/internal/v1/conversations/${conversationId.value}/cancel?job_id=${encodeURIComponent(jobId)}`)
  }

  function applyEvent(event: { type: string; payload: Record<string, unknown> }): void {
    const jobId = stringField(event.payload, 'job_id')
    if (!jobId) return
    if (event.type === 'generation.delta') {
      const text = stringField(event.payload, 'text') ?? ''
      state.value = reduceChatState(state.value, { type: event.type, jobId, text })
    } else if (event.type === 'job.succeeded') {
      state.value = reduceChatState(state.value, { type: 'generation.completed', jobId })
      streamAbort?.abort()
      void refreshConversationList()
    } else if (event.type === 'job.cancelled') {
      state.value = reduceChatState(state.value, { type: 'generation.cancelled', jobId })
      streamAbort?.abort()
    } else if (event.type === 'job.failed') {
      state.value = reduceChatState(state.value, { type: 'generation.failed', jobId, message: '生成失败，请检查 Runtime 状态' })
      streamAbort?.abort()
    }
  }

  async function refreshConversationList(): Promise<void> {
    const client = await runtimeClient()
    conversations.value = readConversations(await client.get('/internal/v1/conversations'))
    if (conversationId.value) await openConversation(conversationId.value)
  }

  return {
    state, models, conversations, conversationId, selectedModelId, maxTokens, temperature,
    busy, loadWorkspace, newConversation, openConversation, send, cancel,
  }
})

function readModels(value: unknown): ModelOption[] {
  return Array.isArray(value) ? value.map((item) => ({
    id: stringField(item, 'id') ?? '', displayName: stringField(item, 'displayName') ?? 'Unknown model',
    engine: stringField(item, 'engine') ?? 'unknown', inputModalities: stringArrayField(item, 'inputModalities'),
    multiImage: nestedBooleanField(item, 'capabilities', 'multiImage'),
    state: stringField(item, 'state'),
  })).filter((item) => item.id) : []
}

function readConversations(value: unknown): ConversationOption[] {
  return Array.isArray(value) ? value.map(readConversation) : []
}

function readConversation(value: unknown): ConversationOption {
  return {
    id: stringField(value, 'id') ?? '', title: stringField(value, 'title') ?? 'Untitled',
    modelId: stringField(value, 'modelId') ?? null,
  }
}

function readMessages(value: unknown): ChatMessage[] {
  const messages = arrayField(value, 'messages')
  return messages.map((item) => ({
    id: stringField(item, 'id') ?? crypto.randomUUID(),
    role: stringField(item, 'role') === 'user' ? 'user' : 'assistant',
    content: stringField(item, 'content') ?? '', state: 'complete',
    attachments: readAttachments(item),
  }))
}

function readAttachments(value: unknown): Array<{ id: string; originalName: string; mimeType: string }> {
  if (typeof value !== 'object' || value === null) return []
  const attachments = (value as Record<string, unknown>).attachments
  if (!Array.isArray(attachments)) return []
  return attachments.flatMap((item) => {
    const id = stringField(item, 'id')
    if (!id) return []
    return [{
      id, originalName: stringField(item, 'originalName') ?? '图片',
      mimeType: stringField(item, 'mimeType') ?? 'image/*',
    }]
  })
}

function arrayField(value: unknown, key: string): unknown[] {
  if (typeof value !== 'object' || value === null) return []
  const field = (value as Record<string, unknown>)[key]
  return Array.isArray(field) ? field : []
}

function stringField(value: unknown, key: string): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const field = (value as Record<string, unknown>)[key]
  return typeof field === 'string' ? field : undefined
}

function stringArrayField(value: unknown, key: string): string[] {
  if (typeof value !== 'object' || value === null) return []
  const field = (value as Record<string, unknown>)[key]
  return Array.isArray(field) ? field.filter((item): item is string => typeof item === 'string') : []
}

function nestedBooleanField(value: unknown, parentKey: string, key: string): boolean {
  if (typeof value !== 'object' || value === null) return false
  const parent = (value as Record<string, unknown>)[parentKey]
  if (typeof parent !== 'object' || parent === null) return false
  return (parent as Record<string, unknown>)[key] === true
}

function numberField(value: unknown, key: string): number | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const field = (value as Record<string, unknown>)[key]
  return typeof field === 'number' ? field : undefined
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Runtime 请求失败'
}
