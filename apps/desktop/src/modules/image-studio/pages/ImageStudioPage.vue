<script setup lang="ts">
import { NAlert, NButton, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import ImageControls from '../components/ImageControls.vue'
import ImageHistory from '../components/ImageHistory.vue'
import ImagePreview from '../components/ImagePreview.vue'
import ImageTasks from '../components/ImageTasks.vue'
import type { ImageArtifact, ImageJob } from '../domain/image-state'
import { useImageStudioStore } from '../stores/image-studio.store'

const store = useImageStudioStore()
const message = useMessage()
const route = useRoute()
const { form, artifacts, jobs, activeJob, selectedId, selectedArtifact, imageModels, hasActiveJob } = storeToRefs(store)
const historySection = ref<HTMLElement | null>(null)
const controlsSection = ref<HTMLElement | null>(null)
const locked = computed(() => hasActiveJob.value || store.submitting || store.loading)
watch(() => route.query.prompt, (value) => {
  if (typeof value === 'string' && !hasActiveJob.value) form.value = { ...form.value, prompt: value }
}, { immediate: true })
onMounted(() => { void store.loadWorkspace() })

async function save(): Promise<void> {
  if (!selectedArtifact.value) return
  try { await store.saveArtifact(selectedArtifact.value.id); message.success('图片已导出为 PNG') }
  catch (cause) { message.error(cause instanceof Error ? cause.message : '保存图片失败') }
}
function reuse(item: ImageArtifact | ImageJob | null): void {
  if (!item || locked.value) return
  store.reuse(item)
  controlsSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function select(id: string): void {
  store.selectArtifact(id)
  controlsSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <section class="page-content image-studio-page">
    <div class="image-page-heading">
      <div>
        <h1 class="page-title">
          图片创作
        </h1><p class="page-subtitle">
          让灵感在本地成像，每一张作品都自动留存
        </p>
      </div><NButton
        secondary
        @click="historySection?.scrollIntoView({ behavior: 'smooth', block: 'start' })"
      >
        <StudioIcon
          name="image"
          :size="18"
        />作品历史
      </NButton>
    </div>
    <NAlert
      v-if="store.error || store.modelError"
      type="error"
      :show-icon="false"
      class="image-page-notice"
      role="alert"
    >
      {{ store.error || store.modelError }}<NButton
        v-if="store.modelError"
        text
        type="primary"
        @click="store.loadWorkspace"
      >
        重试连接
      </NButton>
    </NAlert>
    <NAlert
      v-if="!imageModels.length && !store.loading && !store.modelError"
      type="info"
      :show-icon="false"
      class="image-page-notice"
    >
      还没有本地生图模型，前往模型库下载或导入后即可选择。
    </NAlert>
    <NAlert
      v-if="store.loading"
      type="info"
      :show-icon="false"
      class="image-page-notice"
      aria-live="polite"
    >
      正在读取模型与作品历史…
    </NAlert>
    <div
      ref="controlsSection"
      class="image-creation-layout"
    >
      <ImageControls
        v-model:form="form"
        :models="imageModels"
        :locked="locked"
        :submitting="store.submitting"
        @generate="store.generate"
      />
      <ImagePreview
        :artifact="selectedArtifact"
        :url="selectedId ? store.urls[selectedId] : undefined"
        :image-error="selectedId ? store.imageErrors[selectedId] : undefined"
        :job="activeJob"
        :submitting="store.submitting"
        :cancelling="store.cancelling"
        :saving="!!store.savingId"
        :sync-error="store.syncError"
        @cancel="store.cancel"
        @save="save"
        @reuse="reuse(selectedArtifact)"
        @retry-image="selectedId && store.loadImage(selectedId)"
        @reconnect="store.refreshJob"
      />
    </div>
    <ImageTasks
      :jobs="jobs"
      :locked="locked"
      @reuse="reuse"
      @select="select"
    />
    <div ref="historySection">
      <ImageHistory
        :artifacts="artifacts"
        :urls="store.urls"
        :errors="store.imageErrors"
        :selected-id="selectedId"
        :loading="store.historyLoading"
        :error="store.historyError"
        :has-more="store.hasMore"
        @select="select"
        @refresh="store.loadHistory(true)"
        @more="store.loadHistory(false)"
      />
    </div>
  </section>
</template>

<style scoped>
.image-page-heading { display: flex; justify-content: space-between; align-items: center; gap: 18px; margin-bottom: 22px; }.image-page-heading .page-subtitle { margin-bottom: 0; }.image-page-heading .n-button :deep(.n-button__content) { gap: 8px; }.image-creation-layout { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 20px; align-items: stretch; scroll-margin-top: 16px; }.image-page-notice { margin-bottom: 16px; }.image-page-notice .n-button { margin-left: 12px; }
@media (max-width: 1120px) { .image-creation-layout { grid-template-columns: 280px minmax(0, 1fr); gap: 15px; } }
@media (max-width: 960px) { .image-creation-layout { grid-template-columns: minmax(0, 1fr); }.image-creation-layout > :first-child { order: 1; }.image-creation-layout > :last-child { order: 2; } }
@media (max-width: 680px) { .image-page-heading { align-items: start; }.image-page-heading .n-button { flex-shrink: 0; font-size: 12px; padding: 0 12px; }.page-title { font-size: 23px; }.page-subtitle { font-size: 12px; line-height: 1.6; } }
</style>
