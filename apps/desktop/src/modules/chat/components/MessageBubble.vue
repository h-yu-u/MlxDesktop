<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '../../../shared/lib/render-markdown'
import type { ChatMessage } from '../domain/chat-state'

const props = defineProps<{ message: ChatMessage }>()
const html = computed(() => renderMarkdown(props.message.content))
</script>

<template>
  <article
    class="message"
    :class="message.role"
  >
    <div class="message-role">
      {{ message.role === 'user' ? '你' : 'MLX Studio' }}
    </div>
    <ul
      v-if="message.attachments?.length"
      class="message-attachments"
      aria-label="消息附件"
    >
      <li
        v-for="attachment in message.attachments"
        :key="attachment.id"
      >
        <span aria-hidden="true">▧</span> {{ attachment.originalName }}
      </li>
    </ul>
    <!-- Sanitized with DOMPurify before insertion; raw scripts and active embeds are removed. -->
    <!-- eslint-disable vue/no-v-html -->
    <div
      class="message-body markdown-body"
      v-html="html"
    />
    <!-- eslint-enable vue/no-v-html -->
  </article>
</template>

<style scoped>
.markdown-body :deep(pre) { overflow: auto; padding: 12px; border-radius: 8px; background: #202535; color: #edf1f8; }
.markdown-body :deep(code) { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9em; }
.markdown-body :deep(p:first-child) { margin-top: 0; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.message-attachments { display:flex; gap:8px; flex-wrap:wrap; list-style:none; padding:0; margin:0 0 10px; }
.message-attachments li { padding:5px 9px; border-radius:8px; background:#242d40; font-size:12px; }
</style>
