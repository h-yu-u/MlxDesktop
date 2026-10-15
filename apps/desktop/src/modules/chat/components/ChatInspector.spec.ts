import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatInspector from './ChatInspector.vue'
const runtime = { error: null, info: {}, uptime: '—', diskFree: '—' }
describe('ChatInspector', () => {
  it('emits reset without requiring a Store and disables unsupported settings', async () => {
    const wrapper = mount(ChatInspector, {
      props: {
        clearing: false,
        busy: false,
        messageCount: 0,
        runtime,
        maxTokens: 1024,
        temperature: 1.3,
      },
    })
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '重置')
      ?.trigger('click')
    expect(wrapper.emitted('reset')).toHaveLength(1)
    expect(wrapper.findAll('[role="slider"][aria-disabled="true"]')).toHaveLength(2)
    wrapper.unmount()
  })
  it('locks actions and parameters while a request is pending', () => {
    const wrapper = mount(ChatInspector, {
      props: { clearing: false, busy: true, messageCount: 1, runtime },
    })
    expect(
      wrapper.findAll('button').every((button) => button.attributes('disabled') !== undefined),
    ).toBe(true)
    expect(
      wrapper.findAll('input').every((input) => input.attributes('disabled') !== undefined),
    ).toBe(true)
    wrapper.unmount()
  })
})
