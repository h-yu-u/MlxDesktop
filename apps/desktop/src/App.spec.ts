import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

const mocks = vi.hoisted(() => ({ loadWorkspace: vi.fn() }))
vi.mock('./modules/chat/stores/chat.store', async () => {
  const { defineStore } = await import('pinia')
  return {
    useChatStore: defineStore('sidebar-test-chat', {
      state: () => ({ conversations: [], busy: false, pending: false }),
      actions: { loadWorkspace: mocks.loadWorkspace },
    }),
  }
})
async function render(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ['/chat', '/coding', '/models', '/image-studio', '/audio-studio', '/settings'].map(
      (path) => ({
        path,
        meta: { workspace: path === '/chat' ? 'chat' : path === '/coding' ? 'coding' : undefined },
        component: { template: '<div class="test-page">页面内容</div>' },
      }),
    ),
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(App, {
    global: {
      plugins: [createPinia(), router],
      stubs: { RuntimeStatusBanner: true, TaskCenter: true },
    },
  })
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => vi.clearAllMocks())
describe('workspace sidebar visibility', () => {
  it.each(['/chat', '/coding', '/models', '/image-studio', '/audio-studio', '/settings'])(
    'shows conversation navigation only on chat when opening %s',
    async (path) => {
      const { wrapper } = await render(path)
      const chat = path === '/chat'
      expect(wrapper.find('.sidebar-content').exists()).toBe(chat)
      expect(wrapper.get('.app-shell').classes().includes('has-chat-sidebar')).toBe(chat)
      expect(wrapper.find('.topbar').exists()).toBe(!chat && path !== '/coding')
      expect(wrapper.get('[aria-label="主导航"]').findAll('.rail-link')).toHaveLength(6)
      expect(mocks.loadWorkspace).toHaveBeenCalledTimes(chat ? 1 : 0)
      expect(wrapper.get('.test-page').text()).toBe('页面内容')
      wrapper.unmount()
    },
  )
  it('hides the conversation panel across other pages and restores it on return', async () => {
    const { wrapper, router } = await render('/chat')
    for (const path of ['/models', '/image-studio', '/settings']) {
      await router.push(path)
      await flushPromises()
      expect(wrapper.find('[aria-label="最近对话"]').exists()).toBe(false)
      expect(wrapper.find('[aria-label="搜索历史对话"]').exists()).toBe(false)
      expect(wrapper.get('.app-shell').classes()).not.toContain('has-chat-sidebar')
    }
    await router.push('/chat')
    await flushPromises()
    expect(wrapper.find('[aria-label="最近对话"]').exists()).toBe(true)
    expect(wrapper.get('.app-shell').classes()).toContain('has-chat-sidebar')
    expect(mocks.loadWorkspace).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
