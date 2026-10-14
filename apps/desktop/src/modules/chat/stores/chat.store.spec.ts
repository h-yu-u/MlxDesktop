import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStore } from './chat.store'

const api = vi.hoisted(() => ({ delete: vi.fn(), get: vi.fn(), post: vi.fn(), subscribe: vi.fn() }))
vi.mock('../../../shared/api/runtime', () => ({ runtimeClient: async () => api }))

function populatedStore(): ReturnType<typeof useChatStore> {
  const store = useChatStore()
  store.conversationId = 'current'
  store.conversations = [
    { id: 'current', title: '当前会话', modelId: null },
    { id: 'other', title: '保留会话', modelId: null },
  ]
  store.state.messages = [{ id: 'message', role: 'user', content: 'hello' }]
  return store
}

describe('chat workspace actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    api.delete.mockReset(); api.get.mockReset(); api.post.mockReset(); api.subscribe.mockReset()
  })

  it('sends the selected real model and renders its streamed reply', async () => {
    let receive: ((event: { type: string; payload: Record<string, unknown> }) => void) | undefined
    api.subscribe.mockImplementation((handler) => {
      receive = handler
      return new Promise(() => {})
    })
    api.post.mockResolvedValue({ jobId: 'real-job' })
    api.get.mockImplementation(async (path: string) => {
      if (path.includes('/runtime/info')) return { event_sequence: 3 }
      if (path === '/internal/v1/conversations') return []
      return { id: 'local-chat', modelId: 'qwen-local', messages: [
        { id: 'user-1', role: 'user', content: '你好' },
        { id: 'assistant-1', role: 'assistant', content: '你好，我是本地模型。' },
      ] }
    })
    const store = useChatStore()
    store.conversationId = 'local-chat'
    store.selectedModelId = 'qwen-local'
    await store.send('你好')
    expect(api.post).toHaveBeenCalledWith('/internal/v1/conversations/local-chat/messages',
      expect.objectContaining({ model_id: 'qwen-local', content: '你好' }))
    receive?.({ type: 'generation.delta', payload: { job_id: 'real-job', text: '你好，' } })
    expect(store.state.messages.at(-1)?.content).toBe('你好，')
    receive?.({ type: 'generation.delta', payload: { job_id: 'real-job', text: '我是本地模型。' } })
    receive?.({ type: 'job.succeeded', payload: { job_id: 'real-job' } })
    await vi.waitFor(() => expect(store.state.messages.at(-1)?.id).toBe('assistant-1'))
    expect(store.state.messages.at(-1)?.content).toBe('你好，我是本地模型。')
    expect(store.busy).toBe(false)
  })

  it('defaults to a real local model when FakeEngine is also registered', async () => {
    api.get.mockImplementation(async (path: string) => path.includes('/models') ? [
      { id: 'fake', engine: 'fake', outputModalities: ['text'] },
      { id: 'qwen-local', engine: 'mlx-vlm', outputModalities: ['text'], state: 'available' },
    ] : [])
    const store = useChatStore()
    await store.loadWorkspace()
    expect(store.selectedModelId).toBe('qwen-local')
  })

  it('preserves an explicit model selection when refreshing the workspace', async () => {
    api.get.mockImplementation(async (path: string) => path.includes('/models') ? [
      { id: 'fake', engine: 'fake', outputModalities: ['text'] },
      { id: 'qwen-local', engine: 'mlx-vlm', outputModalities: ['text'] },
    ] : [])
    const store = useChatStore()
    store.selectedModelId = 'fake'
    await store.loadWorkspace()
    expect(store.selectedModelId).toBe('fake')
  })

  it('removes only the current conversation after the API succeeds', async () => {
    const store = populatedStore()
    await store.clearConversation()
    expect(api.delete).toHaveBeenCalledWith('/internal/v1/conversations/current')
    expect(store.conversations.map((item) => item.id)).toEqual(['other'])
    expect(store.conversationId).toBeNull()
    expect(store.state.messages).toEqual([])
  })

  it('preserves messages and selection if deletion fails', async () => {
    const store = populatedStore()
    api.delete.mockRejectedValue(new Error('offline'))
    await expect(store.clearConversation()).rejects.toThrow('offline')
    expect(store.conversationId).toBe('current')
    expect(store.state.messages).toHaveLength(1)
    expect(store.conversations).toHaveLength(2)
  })

  it('cannot delete a conversation during generation', async () => {
    const store = populatedStore()
    store.state.status = 'sending'
    await store.clearConversation()
    expect(api.delete).not.toHaveBeenCalled()
    expect(store.conversationId).toBe('current')
  })
})
