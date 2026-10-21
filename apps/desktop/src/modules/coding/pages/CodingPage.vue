<script setup lang="ts">
import { CapabilityPicker, type ExtensionSelection } from '../../../capabilities/extensions'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NEmpty, NInput, NModal, NSplit, useDialog } from 'naive-ui'
import { useCodingStore } from '../stores/coding.store'
import type { CodingSession } from '../application/ports'
import { statusLabel } from '../domain/status'
import CodingSidebar from '../components/CodingSidebar.vue'
import CodingTimeline from '../components/CodingTimeline.vue'
import CodingComposer from '../components/CodingComposer.vue'
import CodingInspector from '../components/CodingInspector.vue'
import ApprovalCard from '../components/ApprovalCard.vue'
const coding = useCodingStore(),
  route = useRoute(),
  router = useRouter(),
  dialog = useDialog()
const selection = ref<ExtensionSelection | undefined>()
const rename = ref<CodingSession | null>(null),
  title = ref(''),
  renameOpen = ref(false),
  splitSize = ref(0.46)
watch(
  () => coding.projectId,
  () => {
    selection.value = undefined
  },
)
const selectedProject = computed(() => coding.projects.find((item) => item.id === coding.projectId))
const approvals = computed(
  () => coding.snapshot?.approvals.filter((item) => item.status === 'pending') ?? [],
)
const currentSessionActive = computed(
  () => coding.busy && coding.active?.sessionId === coding.sessionId,
)
function sessionUrl(item: CodingSession): string {
  return `/coding/projects/${encodeURIComponent(item.projectId)}/sessions/${encodeURIComponent(item.id)}`
}
async function openSession(id: string): Promise<void> {
  const item = coding.sessions.find((item) => item.id === id)
  if (item) await router.push(sessionUrl(item))
}
async function createSession(): Promise<void> {
  const item = await coding.newSession()
  if (item) await router.push(sessionUrl(item))
}
function openRename(item: CodingSession): void {
  rename.value = item
  title.value = item.title
  renameOpen.value = true
}
async function saveRename(): Promise<boolean> {
  if (!rename.value) return false
  await coding.updateSession(rename.value.id, { title: title.value.trim() })
  return !coding.error
}
function removeSession(item: CodingSession): void {
  dialog.warning({
    title: '删除开发会话',
    content: `删除「${item.title}」的记录？项目文件会保留。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: () => coding.removeSession(item.id),
  })
}
async function submit(): Promise<void> {
  await coding.send(coding.draftText, false, selection.value)
}
async function queue(): Promise<void> {
  await coding.send(coding.draftText, true, selection.value)
}
async function steer(): Promise<void> {
  await coding.steer(coding.draftText)
}
function routeText(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined
}
onMounted(() => {
  void coding.loadWorkspace(routeText(route.params.projectId), routeText(route.params.sessionId))
})
watch(
  () => route.params.sessionId,
  (id) => {
    if (typeof id === 'string' && id !== coding.sessionId)
      void coding.loadWorkspace(routeText(route.params.projectId), id)
  },
)
onUnmounted(() => coding.dispose())
</script>
<template>
  <div class="coding-workspace">
    <CodingSidebar
      :projects="coding.projects"
      :sessions="coding.sessions"
      :project-id="coding.projectId"
      :session-id="coding.sessionId"
      :active-session="coding.active?.sessionId"
      :pending="coding.pending"
      :has-more="coding.sessionsHasMore"
      @more="coding.loadMoreSessions"
      @open="coding.openProject"
      @project="coding.selectProject"
      @create="createSession"
      @session="openSession"
      @rename="openRename"
      @pin="coding.updateSession($event.id, { pinned: !$event.pinned })"
      @archive="coding.updateSession($event.id, { archived: !$event.archived })"
      @remove="removeSession"
    />
    <div class="coding-main">
      <header class="coding-header">
        <div>
          <h1>{{ coding.snapshot?.session.title ?? '本地开发工作区' }}</h1>
          <small
            >{{ coding.snapshot?.project.path ?? selectedProject?.path ?? '选择项目后开始' }}
            <span v-if="coding.snapshot?.project.git">
              · {{ coding.snapshot.project.branch || 'Detached HEAD' }}</span
            ></small
          >
        </div>
        <div class="coding-header-actions">
          <NButton
            v-for="item in ['changes', 'files'] as const"
            :key="item"
            size="small"
            quaternary
            :aria-pressed="coding.panel === item"
            :disabled="!coding.sessionId"
            @click="coding.inspect(item)"
            >{{ item === 'changes' ? '变更' : '文件' }}</NButton
          >
        </div>
      </header>
      <NAlert
        v-if="coding.error"
        class="coding-alert"
        type="error"
        closable
        @close="coding.error = null"
        >{{ coding.error }}<NButton text @click="coding.loadWorkspace()">重试连接</NButton></NAlert
      >
      <NAlert v-if="coding.preparingModel" class="coding-alert" type="info">
        正在准备本地模型…<NButton text @click="coding.cancelActive">停止</NButton>
      </NAlert>
      <NAlert v-if="coding.busy && !coding.preparingModel" class="coding-alert" type="info"
        >{{ statusLabel(coding.active!.status) }} · {{ statusLabel(coding.active!.phase)
        }}<span v-if="!currentSessionActive">
          · 其他会话正在执行；切换查看不会停止任务</span
        ></NAlert
      >
      <div class="coding-body">
        <NSplit
          direction="horizontal"
          :size="coding.panel ? splitSize : 1"
          :disabled="!coding.panel"
          :min="0.25"
          :max="coding.panel ? 0.7 : 1"
          :resize-trigger-size="coding.panel ? 4 : 0"
          @update:size="splitSize = $event"
        >
          <template #1>
            <CodingTimeline
              v-if="coding.snapshot"
              :events="coding.snapshot.events"
              :runs="coding.snapshot.runs"
            />
            <NEmpty v-else class="coding-empty" description="打开项目并新建或选择开发会话" />
            <div v-if="approvals.length" class="coding-approvals">
              <ApprovalCard
                v-for="approval in approvals"
                :key="approval.id"
                :approval="approval"
                :pending="coding.pending"
                @resolve="coding.resolve"
              />
            </div>
            <CodingComposer
              v-model="coding.draftText"
              :active-status="coding.active?.status"
              :models="coding.models"
              :model-id="coding.selectedModelId"
              :mode="coding.mode"
              :ready="!!coding.selectedModelId"
              :busy="coding.busy"
              :pending="coding.pending"
              :enabled="!!coding.sessionId && !coding.snapshot?.session.archived"
              :current-session-active="currentSessionActive"
              @model="coding.selectedModelId = $event"
              @mode="coding.mode = $event"
              @submit="submit"
              @queue="queue"
              @steer="steer"
              @stop="coding.cancel"
              ><template #capabilities
                ><CapabilityPicker
                  :scope="{
                    workspace: 'coding',
                    kind: 'project',
                    scopeId: coding.projectId || 'unselected',
                  }"
                  :mode="coding.mode"
                  :disabled="coding.pending || !coding.projectId"
                  @change="selection = $event" /></template
            ></CodingComposer>
          </template>
          <template #2>
            <CodingInspector
              v-if="coding.panel"
              :panel="coding.panel"
              :changes="coding.changes"
              :selected="coding.selectedChange"
              :files="coding.fileList"
              :content="coding.fileContent"
              :path="coding.filePath"
              :error="coding.inspectorError"
              :has-more="coding.changesHasMore"
              :busy="coding.busy"
              :pending="coding.inspectorPending"
              @more="coding.loadMoreChanges"
              @close="coding.resetInspector"
              @panel="coding.inspect"
              @refresh="coding.refreshInspector"
              @read="coding.previewFile"
              @restore="coding.restore"
              @detail="coding.loadChange"
            />
          </template>
        </NSplit>
      </div>
    </div>
    <NModal
      v-model:show="renameOpen"
      preset="dialog"
      title="重命名会话"
      positive-text="保存"
      negative-text="取消"
      :positive-button-props="{ disabled: !title.trim() || coding.pending }"
      @positive-click="saveRename"
      ><NInput v-model:value="title" :maxlength="160" aria-label="开发会话名称"
    /></NModal>
  </div>
</template>
<style scoped src="./CodingPage.styles.css"></style>
