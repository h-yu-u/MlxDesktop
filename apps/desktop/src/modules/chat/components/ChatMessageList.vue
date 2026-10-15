<script setup lang="ts">
import { NSpin, NEmpty } from 'naive-ui'
import { ref } from 'vue'
import type { ChatMessage, ChatState } from '../domain/chat-state'
import ChatWelcome from './ChatWelcome.vue'
import MessageBubble from './MessageBubble.vue'
import { useAutoScroll } from '../presentation/use-auto-scroll'
defineProps<{
  messages: ChatMessage[]
  totalCount: number
  status: ChatState['status']
  error: string | null
}>()
defineEmits<{ prompt: [text: string]; image: [text: string]; continue: [] }>()
const messageList = ref<HTMLElement | null>(null)
useAutoScroll(messageList)
</script>
<template>
  <div
    ref="messageList"
    class="message-list"
    :class="{ 'is-empty': !totalCount }"
    aria-live="polite"
  >
    <div v-if="status === 'loading'" class="chat-loading">
      <NSpin size="medium" /><span>正在读取本地工作区…</span>
    </div>
    <ChatWelcome
      v-else-if="!totalCount"
      @prompt="$emit('prompt', $event)"
      @image="$emit('image', $event)"
    />
    <MessageBubble
      v-for="item in messages"
      :key="item.id"
      v-memo="[item, status === 'sending', item === messages.at(-1)]"
      :message="item"
      :can-continue="status !== 'sending' && item === messages.at(-1)"
      @continue="$emit('continue')"
    />
    <NEmpty v-if="totalCount && !messages.length" description="没有找到匹配的消息" />
    <p v-if="error" role="alert" class="error-text">
      {{ error }}
    </p>
  </div>
</template>
<style scoped src="./ChatMessageList.styles.css"></style>
