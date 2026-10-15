import { ref } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'
import type { RuntimeEvent } from '@mlx-studio/api-client'
import { createChatController } from './chat-controller'

function setup() {
  let receive: (event: RuntimeEvent) => void = () => undefined
  const release = vi.fn()
  const gateway = {
    upload: vi.fn(),
    sequence: vi.fn(async () => 0),
    submit: vi.fn(async () => ({ jobId: 'job' })),
    create: vi.fn(),
    delete: vi.fn(),
    update: vi.fn(),
    cancel: vi.fn(),
    list: vi.fn(async () => []),
    get: vi.fn(async () => ({
      id: 'conversation',
      title: 'test',
      modelId: 'model',
      pinned: false,
      messages: [
        {
          id: 'saved',
          role: 'assistant' as const,
          content: 'AB',
          turnId: 'turn',
          attachments: [],
          parameters: { finishReason: 'length' },
        },
      ],
    })),
    job: vi.fn(),
  }
  const controller = createChatController({
    gateway,
    models: ref([]),
    refreshModels: vi.fn(),
    exportText: vi.fn(),
    observe: (_id, _after, event) => {
      receive = event
      return release
    },
  })
  controller.conversationId.value = 'conversation'
  controller.selectedModelId.value = 'model'
  return { controller, release, receive: (event: RuntimeEvent) => receive(event) }
}
afterEach(() => vi.useRealTimers())
it('flushes pending text before cancellation and stops late output', async () => {
  vi.useFakeTimers()
  const { controller, receive, release } = setup()
  await controller.send('hello')
  receive({ type: 'generation.delta', seq: 1, payload: { job_id: 'job', text: 'A' } })
  receive({ type: 'generation.delta', seq: 2, payload: { job_id: 'job', text: 'B' } })
  expect(controller.state.value.messages.at(-1)?.content).toBe('A')
  receive({ type: 'job.cancelled', seq: 3, payload: { job_id: 'job' } })
  expect(controller.state.value.messages.at(-1)?.content).toBe('AB')
  expect(controller.busy.value).toBe(false)
  expect(release).toHaveBeenCalledOnce()
  receive({ type: 'generation.delta', seq: 4, payload: { job_id: 'job', text: 'late' } })
  vi.runAllTimers()
  expect(controller.state.value.messages.at(-1)?.content).toBe('AB')
  controller.dispose()
})
it('preserves truncation metadata when replacing the stream with persisted messages', async () => {
  const { controller, receive } = setup()
  expect(controller.maxTokens.value).toBe(4096)
  await controller.send('hello')
  receive({ type: 'generation.delta', seq: 1, payload: { job_id: 'job', text: 'AB' } })
  receive({ type: 'job.succeeded', seq: 2, payload: { job_id: 'job', finish_reason: 'length' } })
  await vi.waitFor(() => expect(controller.state.value.messages.at(-1)?.id).toBe('saved'))
  expect(controller.state.value.messages.at(-1)?.finishReason).toBe('length')
  controller.dispose()
})
