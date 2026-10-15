import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatComposer from './ChatComposer.vue'

const baseProps = {
  busy: false,
  imageLimit: 0,
  draft: 'hello',
  images: [] as File[],
}

describe('ChatComposer', () => {
  it('does not discard or submit a draft while generation is active', async () => {
    const wrapper = mount(ChatComposer, { props: { ...baseProps, busy: true } })
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(wrapper.emitted('update:draft')).toBeUndefined()
    expect(wrapper.props('draft')).toBe('hello')
  })

  it('does not submit when Enter confirms Chinese input or inserts a line break', async () => {
    const wrapper = mount(ChatComposer, { props: baseProps })
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', isComposing: true })
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(wrapper.emitted('submit')).toBeUndefined()
    wrapper.unmount()
  })

  it('shows a pending send instead of cancellation before a job starts', () => {
    const wrapper = mount(ChatComposer, { props: { ...baseProps, busy: true, generating: false } })
    expect(wrapper.text()).not.toContain('停止生成')
    expect(
      wrapper
        .findAll('button')
        .find((button) => button.text() === '发送')
        ?.attributes('disabled'),
    ).toBeDefined()
    wrapper.unmount()
  })

  it('requests submission without clearing controlled draft state', async () => {
    const wrapper = mount(ChatComposer, { props: baseProps })
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('submit')).toHaveLength(1)
    expect(wrapper.emitted('update:draft')).toBeUndefined()
    expect(wrapper.props('draft')).toBe('hello')
  })
})
