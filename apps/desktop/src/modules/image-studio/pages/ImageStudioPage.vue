<script setup lang="ts">
import { NAlert, NButton, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '../../../shared/ui/PageHeader.vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import ImageControls from '../components/ImageControls.vue'
import ImageHistory from '../components/ImageHistory.vue'
import ImagePreview from '../components/ImagePreview.vue'
import ImageTasks from '../components/ImageTasks.vue'
import ImageMaskEditor from '../components/ImageMaskEditor.vue'
import type { ImageArtifact, ImageJob } from '../domain/image-state'
import { useImageStudioStore } from '../stores/image-studio.store'

const store = useImageStudioStore()
const message = useMessage()
const route = useRoute()
const {
  form,
  artifacts,
  jobs,
  activeJob,
  selectedId,
  selectedArtifact,
  imageModels,
  hasActiveJob,
} = storeToRefs(store)
const historySection = ref<HTMLElement | null>(null)
const controlsSection = ref<HTMLElement | null>(null)
const showMask = ref(false)
const maskSource = computed(() => store.inputUrls[form.value.referenceIds?.[0] ?? ''])
const previewSource = computed(
  () => store.inputUrls[selectedArtifact.value?.reference_ids?.[0] ?? ''],
)
const locked = computed(
  () =>
    hasActiveJob.value ||
    store.submitting ||
    store.loading ||
    store.uploading ||
    store.preparingEdit,
)
watch(
  () => route.query.prompt,
  (value) => {
    if (typeof value === 'string' && !hasActiveJob.value)
      form.value = { ...form.value, prompt: value }
  },
  { immediate: true },
)
onMounted(() => {
  void store.loadWorkspace()
})
onBeforeUnmount(() => store.dispose())

async function save(): Promise<void> {
  if (!selectedArtifact.value) return
  try {
    await store.saveArtifact(selectedArtifact.value.id)
    message.success('图片已导出为 PNG')
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '保存图片失败')
  }
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
async function saveMask(blob: Blob | null): Promise<void> {
  await store.setMask(blob)
  if (!store.inputError) showMask.value = false
}
async function editSelected(): Promise<void> {
  await store.editArtifact()
  controlsSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <section class="page-content image-studio-page">
    <PageHeader title="图片创作" subtitle="从文字开始，或让已有画面焕发新的灵感">
      <template #actions>
        <NButton
          secondary
          @click="historySection?.scrollIntoView({ behavior: 'smooth', block: 'start' })"
        >
          <StudioIcon name="image" :size="18" />作品历史
        </NButton>
      </template>
    </PageHeader>
    <NAlert
      v-if="store.error || store.modelError"
      type="error"
      :show-icon="false"
      class="image-page-notice"
      role="alert"
    >
      {{ store.error || store.modelError
      }}<NButton v-if="store.modelError" text type="primary" @click="store.loadWorkspace">
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
    <div ref="controlsSection" class="image-creation-layout">
      <ImageControls
        v-model:form="form"
        :models="imageModels"
        :locked="locked"
        :submitting="store.submitting"
        :input-urls="store.inputUrls"
        :input-names="store.inputNames"
        :input-error="store.inputError"
        :uploading="store.uploading"
        @generate="store.generate"
        @upload="store.uploadReferences"
        @remove="store.removeReference"
        @move="store.moveReference"
        @mask="showMask = true"
        @retry-inputs="store.restoreInputs()"
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
        :source-url="previewSource"
        :editing-locked="locked"
        @edit="editSelected"
        @cancel="store.cancel"
        @save="save"
        @reuse="reuse(selectedArtifact)"
        @retry-image="selectedId && store.loadImage(selectedId)"
        @reconnect="store.refreshJob"
      />
    </div>
    <ImageMaskEditor
      v-if="showMask && maskSource"
      :source="maskSource"
      :mask-url="store.inputUrls[form.maskId ?? '']"
      :saving="store.uploading"
      @close="showMask = false"
      @save="saveMask"
    />
    <ImageTasks :jobs="jobs" :locked="locked" @reuse="reuse" @select="select" />
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
.image-page-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  margin-bottom: 22px;
}
.image-page-heading .page-subtitle {
  margin-bottom: 0;
}
.image-page-heading .n-button :deep(.n-button__content) {
  gap: 8px;
}
.image-creation-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 20px;
  align-items: stretch;
  scroll-margin-top: 16px;
}
.image-page-notice {
  margin-bottom: 16px;
}
.image-page-notice .n-button {
  margin-left: 12px;
}
@media (max-width: 1120px) {
  .image-creation-layout {
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 15px;
  }
}
@media (max-width: 960px) {
  .image-creation-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .image-creation-layout > :first-child {
    order: 1;
  }
  .image-creation-layout > :last-child {
    order: 2;
  }
}
@media (max-width: 680px) {
  .image-page-heading {
    align-items: start;
  }
  .image-page-heading .n-button {
    flex-shrink: 0;
    font-size: 12px;
    padding: 0 12px;
  }
  .page-title {
    font-size: 23px;
  }
  .page-subtitle {
    font-size: 12px;
    line-height: 1.6;
  }
}
</style>
