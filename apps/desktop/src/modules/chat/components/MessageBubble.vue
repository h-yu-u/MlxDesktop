<script setup lang="ts">
import { computed, ref } from 'vue'
import { refThrottled } from '@vueuse/core'
import { NButton } from 'naive-ui'
import { renderMarkdown } from '../../../shared/lib/render-markdown'
import type { ChatMessage } from '../domain/chat-state'
import { useCodeCopy } from '../presentation/use-code-copy'

const props = defineProps<{ message: ChatMessage; canContinue?: boolean }>()
defineEmits<{ continue: [] }>()
const source = computed(() => props.message.content)
const streaming = computed(() => props.message.state === 'streaming')
const streamingSource = refThrottled(source, 100)
const html = computed(() => renderMarkdown(streaming.value ? streamingSource.value : source.value))
const body = ref<HTMLElement | null>(null)
const { handleCopy } = useCodeCopy(body, html)
</script>

<template>
  <article class="message" :class="message.role">
    <div class="message-role">
      {{ message.role === 'user' ? '你' : 'MLX Studio' }}
    </div>
    <ul v-if="message.attachments?.length" class="message-attachments" aria-label="消息附件">
      <li v-for="attachment in message.attachments" :key="attachment.id">
        <span aria-hidden="true">▧</span> {{ attachment.originalName }}
      </li>
    </ul>
    <!-- Sanitized with DOMPurify before insertion; raw scripts and active embeds are removed. -->
    <!-- eslint-disable vue/no-v-html -->
    <div ref="body" class="message-body markdown-body" @click="handleCopy" v-html="html" />
    <!-- eslint-enable vue/no-v-html -->
    <div v-if="message.finishReason === 'length'" class="message-limit">
      <span>已达到本次输出长度上限，回答可能尚未完成。</span>
      <NButton v-if="canContinue" secondary size="small" @click="$emit('continue')">
        继续回答
      </NButton>
    </div>
  </article>
</template>

<style scoped>
.markdown-body :deep(.code-block) {
  margin: 1em 0;
  overflow: hidden;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--surface-sidebar);
  color: var(--text-primary);
}
.markdown-body :deep(.code-toolbar) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 12px;
  border-bottom: 1px solid var(--line);
  font-size: 11px;
  color: var(--muted);
}
.markdown-body :deep(.code-copy) {
  flex-shrink: 0;
  padding: 4px 8px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.markdown-body :deep(.code-copy:hover) {
  background: var(--surface-hover);
  color: var(--text-primary);
}
.markdown-body :deep(.code-copy:focus-visible) {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.markdown-body :deep(.code-copy:disabled) {
  cursor: wait;
}
.markdown-body :deep(pre) {
  overflow: auto;
  margin: 0;
  padding: 12px;
}
.markdown-body :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.9em;
}
.markdown-body :deep(p:first-child) {
  margin-top: 0;
}
.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}
.message-attachments {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  list-style: none;
  padding: 0;
  margin: 0 0 10px;
}
.message-attachments li {
  padding: 5px 9px;
  border-radius: 8px;
  background: var(--surface-card);
  font-size: 12px;
}
</style>

<style scoped src="./MessageBubble.styles.css"></style>
