import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './render-markdown'

describe('renderMarkdown', () => {
  it('keeps Markdown while escaping raw HTML and active content', () => {
    const html = renderMarkdown('**safe**\n<script>alert(1)</script>')
    expect(html).toContain('<strong>safe</strong>')
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })
})
