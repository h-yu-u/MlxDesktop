import DOMPurify from 'dompurify'
import { marked, type Tokens } from 'marked'

const renderer = new marked.Renderer()
renderer.html = (token: Tokens.HTML | Tokens.Tag) => escapeHtml(token.text)
renderer.code = (token: Tokens.Code) => {
  const language = token.lang?.trim().split(/\s+/)[0] || '代码'
  return `<div class="code-block"><div class="code-toolbar"><span>${escapeHtml(language)}</span><button type="button" class="code-copy" aria-label="复制代码">复制</button></div><pre><code>${escapeHtml(token.text)}\n</code></pre></div>\n`
}

export function renderMarkdown(source: string): string {
  const parsed = marked.parse(source, { async: false, gfm: true, breaks: true, renderer })
  return DOMPurify.sanitize(parsed, {
    FORBID_TAGS: ['style', 'iframe', 'form', 'input', 'object', 'embed'],
    FORBID_ATTR: ['style'],
  })
}

function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (character) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[character] ?? character,
  )
}
