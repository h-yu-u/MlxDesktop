import { ref, type Ref } from 'vue'
import type { AgentChatRequest } from '@mlx-studio/api-client'
import type { ChatMessage } from '../domain/chat-state'

export function createChatHandoff(
  conversation: Ref<string | null>,
  error: (message: string) => void,
) {
  const selected = ref<{
    request: NonNullable<AgentChatRequest['handoff']>
    preview: string
  } | null>(null)
  async function choose(message: ChatMessage) {
    if (!conversation.value || message.state === 'streaming') return
    if (message.content.length > 24000) {
      error('消息过长，请选择较短的消息创建工具任务')
      return
    }
    const source = conversation.value
    const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(message.content))
    if (source !== conversation.value) return
    selected.value = {
      request: {
        sourceConversationId: source,
        targetWorkspace: 'chat',
        messages: [
          {
            id: message.id,
            contentHash: [...new Uint8Array(hash)]
              .map((byte) => byte.toString(16).padStart(2, '0'))
              .join(''),
          },
        ],
      },
      preview: message.content,
    }
  }
  return { selected, choose }
}
