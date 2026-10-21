<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NInput, NSelect, NSwitch } from 'naive-ui'
import SessionListItem from '../../../shared/ui/SessionListItem.vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import type { CodingProject, CodingSession } from '../application/ports'
const props = defineProps<{
  projects: CodingProject[]
  sessions: CodingSession[]
  projectId: string
  sessionId: string
  activeSession?: string
  pending: boolean
  hasMore?: boolean
}>()
const emit = defineEmits<{
  project: [id: string]
  open: []
  more: []
  create: []
  session: [id: string]
  rename: [item: CodingSession]
  pin: [item: CodingSession]
  archive: [item: CodingSession]
  remove: [item: CodingSession]
}>()
const query = ref(''),
  archived = ref(false)
const projectOptions = computed(() =>
  props.projects.map((item) => ({ label: item.name, value: item.id })),
)
const visible = computed(() =>
  [...props.sessions]
    .filter(
      (item) =>
        item.archived === archived.value &&
        item.title.toLowerCase().includes(query.value.toLowerCase()),
    )
    .sort((a, b) => Number(b.pinned) - Number(a.pinned)),
)
function sessionAction(key: string, item: CodingSession): void {
  if (key === 'rename') emit('rename', item)
  if (key === 'archive') emit('archive', item)
  if (key === 'delete') emit('remove', item)
}
</script>
<template>
  <aside class="coding-sidebar" aria-label="Coding 项目与会话">
    <h2>Coding</h2>
    <NButton :disabled="pending" @click="emit('open')">打开项目</NButton>
    <NSelect
      :value="projectId || null"
      :options="projectOptions"
      placeholder="选择项目"
      aria-label="选择开发项目"
      @update:value="emit('project', $event)"
    />
    <NButton :disabled="!projectId || pending" @click="emit('create')">新建会话</NButton>
    <NInput v-model:value="query" placeholder="搜索会话" aria-label="搜索开发会话" clearable />
    <label class="archive-switch"><NSwitch v-model:value="archived" size="small" /> 查看归档</label>
    <div class="session-list">
      <SessionListItem
        v-for="item in visible"
        :id="item.id"
        :key="item.id"
        :title="item.title"
        :selected="item.id === sessionId"
        :pending="pending"
        :status="item.id === activeSession ? 'running' : item.archived ? 'archived' : undefined"
        :actions="[
          { key: 'rename', label: '重命名' },
          {
            key: 'archive',
            label: item.archived ? '恢复' : '归档',
            disabled: item.id === activeSession,
          },
          { key: 'delete', label: '删除', disabled: item.id === activeSession, danger: true },
        ]"
        @select="emit('session', item.id)"
        @action="({ key }) => sessionAction(key, item)"
      >
        <template #trailing
          ><NButton
            quaternary
            circle
            size="small"
            :aria-label="`${item.pinned ? '取消置顶' : '置顶'}：${item.title}`"
            :aria-pressed="item.pinned"
            :disabled="pending"
            @click="emit('pin', item)"
            ><StudioIcon name="pin" :size="17" /></NButton
        ></template>
      </SessionListItem>
      <NButton v-if="hasMore" :disabled="pending" @click="emit('more')">加载更多会话</NButton>
      <p v-if="!visible.length">{{ projectId ? '暂无匹配会话' : '先打开本地项目' }}</p>
    </div>
  </aside>
</template>
<style scoped>
.coding-sidebar {
  width: 232px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 24px 16px;
  background: var(--surface-sidebar);
  border-right: 1px solid var(--line);
}
h2 {
  margin: 0 0 4px;
  font-size: 20px;
}
.session-list {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}
.archive-switch,
p {
  color: var(--muted);
  font-size: 12px;
}
@media (max-width: 1000px) {
  .coding-sidebar {
    width: 195px;
    padding: 16px 12px;
  }
}
@media (max-width: 680px) {
  .coding-sidebar {
    width: auto;
    max-height: 210px;
    overflow-y: auto;
    flex-shrink: 0;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }
}
</style>
