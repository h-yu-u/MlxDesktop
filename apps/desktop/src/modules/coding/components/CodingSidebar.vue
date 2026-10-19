<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NInput, NSelect, NSwitch } from 'naive-ui'
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
      <article v-for="item in visible" :key="item.id" :class="{ selected: item.id === sessionId }">
        <button
          class="session-title"
          :aria-current="item.id === sessionId"
          @click="emit('session', item.id)"
        >
          <span v-if="item.pinned">⌖ </span><span v-if="item.id === activeSession">● </span
          >{{ item.title }}
        </button>
        <div class="session-actions">
          <NButton text size="tiny" :disabled="pending" @click="emit('rename', item)"
            >重命名</NButton
          >
          <NButton text size="tiny" :disabled="pending" @click="emit('pin', item)">{{
            item.pinned ? '取消置顶' : '置顶'
          }}</NButton>
          <NButton
            text
            size="tiny"
            :disabled="pending || item.id === activeSession"
            @click="emit('archive', item)"
            >{{ item.archived ? '恢复' : '归档' }}</NButton
          >
          <NButton
            text
            size="tiny"
            :disabled="pending || item.id === activeSession"
            @click="emit('remove', item)"
            >删除</NButton
          >
        </div>
      </article>
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
.session-list article {
  padding: 10px 8px;
  border-radius: 8px;
}
.selected {
  background: var(--surface-hover);
}
.session-title {
  border: 0;
  padding: 0;
  background: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
  overflow-wrap: anywhere;
}
.session-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  opacity: 0.7;
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
