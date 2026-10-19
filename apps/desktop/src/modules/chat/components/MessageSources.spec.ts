import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import MessageSources from './MessageSources.vue'
import { renderMarkdown } from '../../../shared/lib/render-markdown'

it('recognizes only source-map citations outside code and preserves raw HTML safety', () => {
  const html = renderMarkdown(
    'Source [[cite:w1]] unknown [[cite:foreign]]\n\n`[[cite:w1]]`\n\n```\n[[cite:w1]]\n```\n<script>bad</script>',
    { w1: '#source-1-w1' },
  )
  const root = document.createElement('div')
  root.innerHTML = html
  expect(root.querySelectorAll('a.citation')).toHaveLength(1)
  expect(root.querySelector('a.citation')?.getAttribute('href')).toBe('#source-1-w1')
  expect(root.querySelector('script')).toBeNull()
  expect(root.querySelectorAll('code')).toHaveLength(2)
  expect(root.querySelector('.citation-unresolved')?.textContent).toContain('foreign')
})
it('labels snippets without fetching icons and refuses unsafe external URLs', () => {
  const wrapper = mount(MessageSources, {
    props: {
      prefix: 'source-',
      sources: [
        {
          id: 'w1',
          kind: 'web',
          title: 'Title',
          url: 'javascript:alert(1)',
          retrievedAt: '2026-10-19',
          representation: 'snippet_only',
          contentHash: 'hash',
        },
      ],
    },
  })
  expect(wrapper.text()).toContain('未读取全文')
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.get('a').attributes('href')).toBeUndefined()
})
