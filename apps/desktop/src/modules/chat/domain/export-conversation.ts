import type { ChatMessage } from './chat-state'
export function formatConversation(title: string, messages: ChatMessage[]): string {
  return [
    `# ${title}`,
    ...messages.map((item) => {
      const attachments = item.attachments?.map((file) => `附件：${file.originalName}`).join('\n')
      return `## ${item.role === 'user' ? '你' : 'MLX Studio'}\n\n${item.content}${attachments ? `\n\n${attachments}` : ''}`
    }),
  ].join('\n\n')
}
