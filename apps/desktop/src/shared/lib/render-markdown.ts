import DOMPurify from 'dompurify'
import { marked, type Tokens } from 'marked'

const renderer = new marked.Renderer()
renderer.html = (token: Tokens.HTML | Tokens.Tag) => escapeHtml(token.text)

export function renderMarkdown(source: string): string {
  const parsed = marked.parse(source, { async: false, gfm: true, breaks: true, renderer })
  return DOMPurify.sanitize(parsed, {
    FORBID_TAGS: ['style', 'iframe', 'form', 'input', 'object', 'embed'],
    FORBID_ATTR: ['style'],
  })
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character] ?? character)
}
