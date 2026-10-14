import type { ChatMessage } from '../domain/chat-state'

export function exportConversation(title: string, messages: ChatMessage[]): void {
  const content = [`# ${title}`, ...messages.map((item) => {
    const attachments = item.attachments?.map((file) => `附件：${file.originalName}`).join('\n')
    return `## ${item.role === 'user' ? '你' : 'MLX Studio'}\n\n${item.content}${attachments ? `\n\n${attachments}` : ''}`
  })].join('\n\n')
  const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = 'mlx-studio-conversation.md'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
