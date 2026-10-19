<script setup lang="ts">
import { NButton } from 'naive-ui'
import type { MessageSource } from '../domain/message-source'
defineProps<{ sources: readonly MessageSource[]; prefix: string }>()
defineEmits<{ preview: [source: MessageSource] }>()
function safeUrl(url: string): string | undefined {
  try {
    const parsed = new URL(url)
    return ['https:', 'http:'].includes(parsed.protocol) && !parsed.username && !parsed.password
      ? parsed.href
      : undefined
  } catch {
    return undefined
  }
}
</script>
<template>
  <aside v-if="sources.length" class="message-sources" aria-label="参考来源">
    <strong>参考来源</strong>
    <ul>
      <li v-for="source in sources" :id="`${prefix}${source.id}`" :key="source.id">
        <template v-if="source.kind === 'web'">
          <a :href="safeUrl(source.url)" target="_blank" rel="noopener noreferrer"
            >[{{ source.id }}] {{ source.title }}</a
          >
          <small
            >{{
              source.representation === 'snippet_only' ? '仅搜索摘要 · 未读取全文' : '网页摘录'
            }}
            · 检索于 {{ source.retrievedAt }}</small
          >
        </template>
        <template v-else>
          <NButton text @click="$emit('preview', source)"
            >[{{ source.id }}] {{ source.originalName }}</NButton
          >
          <small
            >{{ source.coverage?.complete ? '已覆盖所选内容' : '仅覆盖部分内容' }} ·
            {{
              source.locations
                ?.map((location) =>
                  location.page ? `第 ${location.page} 页` : location.section || location.blockId,
                )
                .filter((value, index, list) => list.indexOf(value) === index)
                .join('、')
            }}</small
          >
        </template>
      </li>
    </ul>
  </aside>
</template>
<style scoped>
.message-sources {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
  font-size: 12px;
}
ul {
  list-style: none;
  padding: 0;
  display: grid;
  gap: 10px;
}
li {
  display: grid;
  gap: 4px;
  overflow-wrap: anywhere;
}
small {
  color: var(--muted);
}
a {
  color: var(--accent);
}
</style>
