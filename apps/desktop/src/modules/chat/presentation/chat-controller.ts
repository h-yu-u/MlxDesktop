import { computed, ref, type Ref } from 'vue'
import type {
  Conversation,
  ConversationPatch,
  ModelSummary,
  RuntimeEvent,
} from '@mlx-studio/api-client'
import { conversationTitle } from '../domain/conversation-list'
import { formatConversation } from '../domain/export-conversation'
import { SubmitChat } from '../application/submit-chat'
import {
  initialChatState,
  reduceChatState,
  type ChatState,
  type ChatMessage,
} from '../domain/chat-state'
import type { ChatGateway } from '../application/ports'
import { createDeltaBuffer } from './delta-buffer'

interface ChatDependencies {
  gateway: ChatGateway
  models: Readonly<Ref<readonly ModelSummary[]>>
  refreshModels(): Promise<void>
  exportText(content: string, filename: string): void
  observe(
    id: string,
    after: number,
    event: (event: RuntimeEvent) => void,
    resync: () => Promise<number | void>,
  ): () => void
}
export function createChatController(deps: ChatDependencies) {
  const state = ref<ChatState>({ ...initialChatState, messages: [] })
  const conversations = ref<Conversation[]>([])
  const conversationId = ref<string | null>(null)
  const selectedModelId = ref('')
  const pending = ref(false)
  const maxTokens = ref(4096)
  const temperature = ref(0.7)
  const models = computed(() =>
    deps.models.value
      .filter((model) => model.outputModalities.includes('text'))
      .map((model) => ({ ...model, multiImage: model.capabilities.multiImage === true })),
  )
  const busy = computed(() => state.value.status === 'sending')
  const submission = new SubmitChat(deps.gateway)
  let release: (() => void) | undefined
  let readEpoch = 0
  let readAbort: AbortController | undefined
  let viewActive = true
  let viewEpoch = 0
  const deltas = createDeltaBuffer((jobId, text) => {
    state.value = reduceChatState(state.value, { type: 'generation.delta', jobId, text })
  })

  function present(item: Conversation, selectModel = true): void {
    conversationId.value = item.id
    if (selectModel) selectedModelId.value = item.modelId ?? selectedModelId.value
    const messages: ChatMessage[] = item.messages
      .filter((message) => message.role !== 'system')
      .map((message) => ({
        ...message,
        role: message.role === 'user' ? 'user' : 'assistant',
        state: 'complete',
        finishReason: message.parameters.finishReason === 'length' ? 'length' : undefined,
      }))
    state.value = reduceChatState(state.value, { type: 'conversation.loaded', messages })
  }
  async function openConversation(id: string): Promise<void> {
    if (busy.value || pending.value) return
    const epoch = ++readEpoch
    readAbort?.abort()
    readAbort = new AbortController()
    const item = await deps.gateway.get(id, readAbort.signal)
    if (epoch === readEpoch) present(item)
  }
  async function loadWorkspace(): Promise<void> {
    viewActive = true
    const owner = ++viewEpoch
    if (pending.value) return
    if (busy.value && state.value.activeJobId) {
      const id = state.value.activeJobId
      try {
        const sequence = await reconcile()
        if (
          viewActive &&
          owner === viewEpoch &&
          id === state.value.activeJobId &&
          sequence !== undefined
        ) {
          release?.()
          release = deps.observe(id, sequence, applyEvent, reconcile)
        }
      } catch (cause) {
        if (owner === viewEpoch) state.value.error = errorText(cause)
      }
      return
    }
    state.value = { ...state.value, status: 'loading', error: null }
    try {
      const [, items] = await Promise.all([deps.refreshModels(), deps.gateway.list()])
      if (owner !== viewEpoch || !viewActive) return
      conversations.value = items
      if (!models.value.some((model) => model.id === selectedModelId.value)) {
        selectedModelId.value =
          models.value.find((model) => model.source !== 'builtin' && model.state === 'loaded')
            ?.id ??
          models.value.find((model) => model.source !== 'builtin')?.id ??
          models.value[0]?.id ??
          ''
      }
      state.value = { ...state.value, status: 'idle' }
      if (conversationId.value) await openConversation(conversationId.value)
    } catch (cause) {
      state.value = { ...state.value, status: 'error', error: errorText(cause) }
    }
  }
  async function newConversation(): Promise<void> {
    if (busy.value || pending.value) return
    pending.value = true
    try {
      const item = await deps.gateway.create(selectedModelId.value)
      readEpoch += 1
      present(item)
      conversations.value = [item, ...conversations.value]
    } finally {
      pending.value = false
    }
  }
  async function deleteConversation(id: string): Promise<void> {
    if (busy.value || pending.value) return
    pending.value = true
    try {
      await deps.gateway.delete(id)
      readEpoch += 1
      readAbort?.abort()
      conversations.value = conversations.value.filter((item) => item.id !== id)
      if (conversationId.value === id) {
        release?.()
        conversationId.value = null
        state.value = { ...initialChatState, messages: [] }
      }
    } finally {
      pending.value = false
    }
  }
  async function clearConversation(): Promise<void> {
    if (conversationId.value) await deleteConversation(conversationId.value)
  }
  async function updateConversation(id: string, patch: ConversationPatch): Promise<void> {
    if (busy.value || pending.value) return
    pending.value = true
    try {
      const updated = await deps.gateway.update(id, patch)
      conversations.value = conversations.value.map((item) => (item.id === id ? updated : item))
    } finally {
      pending.value = false
    }
  }
  async function renameConversation(id: string, title: string): Promise<void> {
    await updateConversation(id, { title: conversationTitle(title) })
  }
  async function toggleConversationPin(id: string): Promise<void> {
    const item = conversations.value.find((entry) => entry.id === id)
    if (item) await updateConversation(id, { pinned: !item.pinned })
  }
  async function reconcile(): Promise<number | void> {
    deltas.flush()
    const owner = viewEpoch
    if (!conversationId.value) return
    const id = conversationId.value
    const jobId = state.value.activeJobId
    if (jobId) {
      const snapshot = await deps.gateway.job(jobId)
      if (
        owner !== viewEpoch ||
        !viewActive ||
        jobId !== state.value.activeJobId ||
        id !== conversationId.value
      )
        return
      if (['succeeded', 'failed', 'cancelled'].includes(snapshot.state)) {
        applyEvent({
          type: `job.${snapshot.state}`,
          seq: snapshot.event_sequence,
          payload: { job_id: jobId },
        })
        if (snapshot.state === 'succeeded') {
          const item = await deps.gateway.get(id)
          if (owner === viewEpoch && viewActive && id === conversationId.value) present(item, false)
        }
      } else {
        state.value = {
          ...state.value,
          messages: state.value.messages.map((message) =>
            message.id === jobId ? { ...message, content: snapshot.text } : message,
          ),
        }
      }
      return snapshot.event_sequence
    }
    const [items, item] = await Promise.all([deps.gateway.list(), deps.gateway.get(id)])
    if (owner !== viewEpoch || !viewActive || id !== conversationId.value) return
    conversations.value = items
    present(item, false)
  }
  function applyEvent(event: RuntimeEvent): void {
    if (!viewActive) return
    const id = event.payload.job_id
    if (typeof id !== 'string' || id !== state.value.activeJobId) return
    if (event.type === 'generation.delta') {
      deltas.push(id, String(event.payload.text ?? ''))
      return
    }
    const terminal =
      event.type === 'job.succeeded'
        ? {
            type: 'generation.completed' as const,
            finishReason:
              event.payload.finish_reason === 'length' ? ('length' as const) : undefined,
          }
        : event.type === 'job.cancelled'
          ? { type: 'generation.cancelled' as const }
          : event.type === 'job.failed'
            ? { type: 'generation.failed' as const, message: '生成失败，请检查 Runtime 状态' }
            : undefined
    if (!terminal) return
    deltas.flush()
    state.value = reduceChatState(state.value, { ...terminal, jobId: id })
    release?.()
    release = undefined
    if (event.type === 'job.succeeded')
      void reconcile().catch((cause) => {
        state.value.error = errorText(cause)
      })
  }
  async function send(content: string, files: File[] = []): Promise<boolean> {
    if ((!content.trim() && !files.length) || busy.value || pending.value) return false
    pending.value = true
    try {
      if (!conversationId.value) {
        const item = await deps.gateway.create(selectedModelId.value)
        present(item)
        conversations.value = [item, ...conversations.value]
      }
      const result = await submission.run({
        conversationId: conversationId.value!,
        content,
        files,
        modelId: selectedModelId.value,
        maxTokens: maxTokens.value,
        temperature: temperature.value,
      })
      if (!result) return false
      state.value = reduceChatState(state.value, {
        type: 'send.started',
        userMessage: {
          id: crypto.randomUUID(),
          role: 'user',
          content: result.content,
          state: 'complete',
          attachments: result.attachments,
        },
        assistantMessage: { id: result.jobId, role: 'assistant', content: '', state: 'streaming' },
      })
      release?.()
      if (viewActive) release = deps.observe(result.jobId, result.after, applyEvent, reconcile)
      return true
    } finally {
      pending.value = false
    }
  }
  async function cancel(): Promise<void> {
    if (state.value.activeJobId && conversationId.value)
      await deps.gateway.cancel(conversationId.value, state.value.activeJobId)
  }
  function resetParameters(): void {
    if (!busy.value && !pending.value) {
      maxTokens.value = 4096
      temperature.value = 0.7
    }
  }
  function exportConversation(): void {
    const title =
      conversations.value.find((item) => item.id === conversationId.value)?.title ?? '本地对话'
    deps.exportText(formatConversation(title, state.value.messages), 'mlx-studio-conversation.md')
  }
  function dispose(): void {
    deltas.flush()
    viewActive = false
    viewEpoch += 1
    readEpoch += 1
    readAbort?.abort()
    release?.()
    release = undefined
  }
  return {
    state,
    models,
    conversations,
    conversationId,
    selectedModelId,
    pending,
    maxTokens,
    temperature,
    busy,
    loadWorkspace,
    newConversation,
    clearConversation,
    deleteConversation,
    renameConversation,
    toggleConversationPin,
    openConversation,
    send,
    cancel,
    resetParameters,
    exportConversation,
    dispose,
  }
}
function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : '聊天工作区请求失败'
}
