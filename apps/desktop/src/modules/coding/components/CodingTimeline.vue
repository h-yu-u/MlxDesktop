<script setup lang="ts">
import { ArtifactLinks } from '../../../capabilities/extensions'
import { computed } from 'vue'
import { NEmpty, NTag } from 'naive-ui'
import type { CodingEvent, CodingRun } from '../application/ports'
import { codingRunErrorText } from '../presentation/coding-errors'
import {
  activityLabel,
  activityText,
  eventError,
  timelineEntries,
} from '../presentation/coding-activity'
import { statusLabel } from '../domain/status'
import MarkdownContent from '../../../shared/ui/MarkdownContent.vue'
import { useMarkdownCopy } from '../../../shared/ui/markdown-copy'
import { copyText } from '../../../platform/clipboard'
const { copyState, copyCode } = useMarkdownCopy(copyText)
const props = defineProps<{ events: CodingEvent[]; runs: CodingRun[] }>()
const entries = computed(() => timelineEntries(props.events))
</script>
<template>
  <section class="coding-timeline" aria-label="开发任务时间线" aria-live="polite">
    <NEmpty v-if="!events.length" description="描述需要完成的开发任务" />
    <template
      v-for="entry in entries"
      :key="entry.kind === 'message' ? entry.event.seq : entry.seq"
    >
      <details v-if="entry.kind === 'activity'" class="coding-activity">
        <summary>{{ entry.events.length }} 项操作</summary>
        <details v-for="event in entry.events" :key="event.seq">
          <summary>
            {{ event.type === 'verification.finished' ? '命令输出' : activityLabel(event.text) }}
          </summary>
          <pre>{{ activityText(event) }}</pre>
          <ArtifactLinks :data="event.data" />
        </details>
      </details>
      <article
        v-else
        :class="{ user: ['run.started', 'user.steering'].includes(entry.event.type) }"
      >
        <pre v-if="['run.started', 'user.steering'].includes(entry.event.type)">{{
          entry.event.text
        }}</pre>
        <MarkdownContent
          v-else-if="entry.event.text.trim()"
          :content-id="`${entry.event.sessionId}:${entry.event.runId}:${entry.event.seq}`"
          :source="entry.event.text"
          :copy-state="copyState"
          @copy-code="copyCode"
        />
        <details v-if="eventError(entry.event.data)">
          <summary>错误详情</summary>
          <pre>{{ codingRunErrorText(eventError(entry.event.data) ?? '') }}</pre>
        </details>
      </article>
      <!-- eslint-enable vue/no-v-html -->
    </template>
    <footer v-for="run in runs" :key="run.id">
      <NTag v-if="run.status !== 'completed'" size="small">{{ statusLabel(run.status) }}</NTag>
      <span v-else>已完成</span>
      <small v-if="run.verificationPlan">
        · 验证范围：{{ run.verificationPlan.scope }}
        <span v-if="run.verificationPlan.invalid">（配置已变更，未验证）</span></small
      >
      <span v-if="run.error"> · {{ codingRunErrorText(run.error) }}</span>
    </footer>
  </section>
</template>
<style scoped>
.coding-timeline {
  flex: 1;
  height: 100%;
  box-sizing: border-box;
  min-height: 0;
  overflow-y: auto;
  padding: 24px clamp(20px, 5%, 64px);
  display: flex;
  flex-direction: column;
  gap: 20px;
}
article {
  max-width: 100%;
  font-size: 14px;
  line-height: 1.7;
}
.user {
  align-self: flex-end;
  max-width: min(85%, 760px);
  border-radius: 16px;
  background: var(--surface-hover);
  padding: 10px 16px;
}
pre {
  font: inherit;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 0;
}
.coding-activity {
  color: var(--muted);
  font-size: 12px;
}
.coding-activity details {
  margin: 10px 0 0 14px;
}
.coding-activity pre {
  padding: 10px;
  max-height: 260px;
  overflow-y: auto;
  background: var(--surface-sidebar);
  border-radius: 8px;
  font-family: monospace;
}
summary {
  cursor: pointer;
  color: var(--muted);
  font-size: 12px;
}
footer {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--muted);
  font-size: 12px;
}
</style>
