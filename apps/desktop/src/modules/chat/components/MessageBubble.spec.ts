import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import MessageBubble from './MessageBubble.vue'
import { renderMarkdown } from '../../../shared/lib/render-markdown'
import { copyText } from '../../../platform/clipboard'

vi.mock('../../../platform/clipboard', () => ({ copyText: vi.fn() }))

vi.mock('../../../shared/lib/render-markdown', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../shared/lib/render-markdown')>()
  return { ...actual, renderMarkdown: vi.fn(actual.renderMarkdown) }
})
afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
  vi.mocked(copyText).mockReset()
})
it('bounds Markdown work during streaming and immediately renders the exact final text', async () => {
  vi.useFakeTimers()
  const message = {
    id: 'job',
    role: 'assistant' as const,
    content: '',
    state: 'streaming' as const,
  }
  const wrapper = mount(MessageBubble, { props: { message } })
  for (let index = 1; index <= 100; index++) {
    await wrapper.setProps({ message: { ...message, content: `**Answer ${index}**` } })
  }
  expect(vi.mocked(renderMarkdown).mock.calls.length).toBeLessThan(5)
  await wrapper.setProps({ message: { ...message, content: '**Final**', state: 'complete' } })
  expect(wrapper.get('.markdown-body strong').text()).toBe('Final')
  wrapper.unmount()
  vi.runAllTimers()
})
it('explains truncation and offers continuing only when allowed', async () => {
  const wrapper = mount(MessageBubble, {
    props: {
      message: {
        id: 'job',
        role: 'assistant',
        content: 'partial',
        state: 'complete',
        finishReason: 'length',
      },
      canContinue: true,
    },
  })
  expect(wrapper.text()).toContain('已达到本次输出长度上限')
  await wrapper.get('button').trigger('click')
  expect(wrapper.emitted('continue')).toHaveLength(1)
  await wrapper.setProps({ canContinue: false })
  expect(wrapper.findAll('button').some((button) => button.text().includes('继续'))).toBe(false)
  wrapper.unmount()
})
it('keeps unsafe HTML escaped after throttling', () => {
  const wrapper = mount(MessageBubble, {
    props: { message: { id: 'job', role: 'assistant', content: '<script>alert(1)</script>' } },
  })
  expect(wrapper.find('script').exists()).toBe(false)
  expect(wrapper.text()).toContain('<script>')
  wrapper.unmount()
})

it('copies only the selected code block, with original whitespace and decoded characters', async () => {
  const wrapper = mount(MessageBubble, {
    props: {
      message: {
        id: 'job',
        role: 'assistant',
        content: '正文\n\n```ts\nconst value = "<&>";\n  // 中文\n```\n\n```sh\necho second\n```',
      },
    },
  })
  const buttons = wrapper.findAll('button.code-copy')
  expect(buttons).toHaveLength(2)
  await buttons[0]!.trigger('click')
  await flushPromises()
  expect(copyText).toHaveBeenLastCalledWith('const value = "<&>";\n  // 中文\n')
  expect(buttons[0]!.text()).toBe('已复制')
  expect(buttons[1]!.text()).toBe('复制')
  await buttons[1]!.trigger('click')
  expect(copyText).toHaveBeenLastCalledWith('echo second\n')
  wrapper.unmount()
})

it('clears obsolete feedback when code changes and copies the latest visible code', async () => {
  vi.useFakeTimers()
  const message = {
    id: 'job',
    role: 'assistant' as const,
    state: 'streaming' as const,
    content: '```ts\nconst x = 1;\n```',
  }
  const wrapper = mount(MessageBubble, { props: { message } })
  await wrapper.get('button.code-copy').trigger('click')
  await Promise.resolve()
  await wrapper.setProps({ message: { ...message, content: '```ts\nconst x = 2;\n```' } })
  await vi.advanceTimersByTimeAsync(100)
  expect(wrapper.get('button.code-copy').text()).toBe('复制')
  await wrapper.get('button.code-copy').trigger('click')
  expect(copyText).toHaveBeenLastCalledWith('const x = 2;\n')
  await vi.advanceTimersByTimeAsync(1800)
  expect(wrapper.get('button.code-copy').text()).toBe('复制')
  wrapper.unmount()
  expect(vi.getTimerCount()).toBe(0)
})

it('shows failures and permits retrying without reporting a false success', async () => {
  vi.mocked(copyText).mockRejectedValueOnce(new Error('denied')).mockResolvedValueOnce()
  const wrapper = mount(MessageBubble, {
    props: { message: { id: 'job', role: 'assistant', content: '```\nhello\n```' } },
  })
  await wrapper.get('button.code-copy').trigger('click')
  await flushPromises()
  expect(wrapper.get('button.code-copy').text()).toBe('复制失败，重试')
  await wrapper.get('button.code-copy').trigger('click')
  await flushPromises()
  expect(wrapper.get('button.code-copy').text()).toBe('已复制')
  wrapper.unmount()
})

it('keeps unresolved citation feedback when only some sources exist', () => {
  const wrapper = mount(MessageBubble, {
    props: {
      message: {
        id: 'partial',
        role: 'assistant',
        state: 'complete',
        content: '[[cite:known]] and [[cite:missing]]',
        sources: [
          {
            id: 'known',
            title: 'Known',
            url: 'https://example.com',
            kind: 'web',
            representation: 'snippet_only',
            contentHash: '',
            retrievedAt: '',
          },
        ],
      },
    },
  })
  expect(wrapper.text()).toContain('部分引用无法定位')
  wrapper.unmount()
})
