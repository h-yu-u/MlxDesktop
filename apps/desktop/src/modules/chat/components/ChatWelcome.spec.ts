import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatWelcome from './ChatWelcome.vue'

describe('ChatWelcome', () => {
  it('places the code example in the composer without sending a message', async () => {
    const wrapper = mount(ChatWelcome)
    await wrapper.get('.example-card:nth-child(2)').trigger('click')
    expect(wrapper.emitted('prompt')?.[0]).toEqual([
      '用 TypeScript 写一个斐波那契函数，并解释它的实现。',
    ])
    expect(wrapper.emitted('image')).toBeUndefined()
  })

  it('sends image examples to the image workflow', async () => {
    const wrapper = mount(ChatWelcome)
    await wrapper.get('.example-card:nth-child(1)').trigger('click')
    expect(wrapper.emitted('image')?.[0]?.[0]).toContain('山湖风景图')
    expect(wrapper.emitted('prompt')).toBeUndefined()
  })
})
