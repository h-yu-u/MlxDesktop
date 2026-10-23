<script setup lang="ts">
import { computed } from 'vue'
import { NButton } from 'naive-ui'
import MarkdownContent from '../../../shared/ui/MarkdownContent.vue'
import { useMarkdownCopy } from '../../../shared/ui/markdown-copy'
import { copyText } from '../../../platform/clipboard'
import type { ChatMessage } from '../domain/chat-state'
import MessageSources from './MessageSources.vue'
import type { MessageSource } from '../domain/message-source'

const props = defineProps<{ message: ChatMessage; canContinue?: boolean }>()
defineEmits<{
  continue: []
  preview: [source: MessageSource]
  regenerate: []
  handoff: []
  attachment: [file: NonNullable<ChatMessage['attachments']>[number]]
}>()
const prefix = computed(() => `source-${encodeURIComponent(props.message.id)}-`)
const sourceMap = computed(() => props.message.sources)
const citations = computed(() =>
  Object.fromEntries(
    (sourceMap.value ?? []).map((source) => [source.id, `#${prefix.value}${source.id}`]),
  ),
)
const { copyState, copyCode } = useMarkdownCopy(copyText)
</script>

<template>
  <article class="message" :class="message.role">
    <div class="message-role">
      {{ message.role === 'user' ? '你' : 'MLX Studio' }}
    </div>
    <ul v-if="message.attachments?.length" class="message-attachments" aria-label="消息附件">
      <li v-for="attachment in message.attachments" :key="attachment.id">
        <NButton text @click="$emit('attachment', attachment)"
          ><span aria-hidden="true">▧</span> {{ attachment.originalName }}</NButton
        >
      </li>
    </ul>
    <MarkdownContent
      class="message-body markdown-body"
      :content-id="message.id"
      :source="message.content"
      :streaming="message.state === 'streaming'"
      :citations="citations"
      :copy-state="copyState"
      @copy-code="copyCode"
    />
    <p v-if="message.parameters?.attemptMode === 'local_only'" class="message-limit">
      未进行新的联网检索。
    </p>
    <MessageSources
      :sources="message.sources ?? []"
      :prefix="prefix"
      @preview="$emit('preview', $event)"
    />
    <NButton
      v-if="message.role === 'assistant' && message.parameters?.contextJobId && canContinue"
      text
      size="small"
      @click="$emit('regenerate')"
      >使用相同资料重新生成</NButton
    >
    <div v-if="message.finishReason === 'length'" class="message-limit">
      <span>已达到本次输出长度上限，回答可能尚未完成。</span>
      <NButton v-if="canContinue" secondary size="small" @click="$emit('continue')">
        继续回答
      </NButton>
    </div>
    <NButton v-if="message.state !== 'streaming'" text size="tiny" @click="$emit('handoff')"
      >创建工具任务</NButton
    >
  </article>
</template>

<style scoped>
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
