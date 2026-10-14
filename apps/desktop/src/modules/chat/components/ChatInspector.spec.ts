import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import ChatInspector from './ChatInspector.vue'
import { useChatStore } from '../stores/chat.store'

describe('ChatInspector', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('resets supported generation settings and disables unsupported settings', async () => {
    const store = useChatStore()
    store.maxTokens = 1024
    store.temperature = 1.3
    const wrapper = mount(ChatInspector, { props: { clearing: false } })
    await wrapper.findAll('button').find((button) => button.text() === '重置')?.trigger('click')
    expect(store.maxTokens).toBe(512)
    expect(store.temperature).toBe(0.7)
    expect(wrapper.findAll('[role="slider"][aria-disabled="true"]')).toHaveLength(2)
    wrapper.unmount()
  })

  it('locks actions and parameters while a request is pending', () => {
    const store = useChatStore()
    store.pending = true
    store.state.messages = [{ id: 'message', role: 'user', content: 'hello' }]
    const wrapper = mount(ChatInspector, { props: { clearing: false } })
    expect(wrapper.findAll('button').every((button) => button.attributes('disabled') !== undefined)).toBe(true)
    expect(wrapper.findAll('input').every((input) => input.attributes('disabled') !== undefined)).toBe(true)
    wrapper.unmount()
  })
})
