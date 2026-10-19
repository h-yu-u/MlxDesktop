import { SubmitImage } from '../application/submit-image'
import { imageJobError, validationMessages } from './image-feedback'
import { computed, ref } from 'vue'
import {
  ImageValidationError,
  isTerminal,
  type ImageArtifact,
  type ImageDraft,
  type ImageJob,
} from '../domain/image-state'
import type { ImageGateway } from '../application/ports'
import type { useModelDirectory } from '../../../capabilities/models'
import { MediaCache } from '../../../capabilities/media'
import { JobPoller } from '../../../capabilities/jobs'
import { createImageInputs } from './image-inputs'
import { createImageDraft } from '../domain/image-draft'
interface ImageDependencies {
  directory: ReturnType<typeof useModelDirectory>
  refreshModels(): Promise<void>
  gateway: ImageGateway
  exportImage(blob: Blob, id: string): Promise<void> | void
}

export function createImageController(deps: ImageDependencies) {
  const models = deps.directory
  const submission = new SubmitImage(deps.gateway)
  const form = ref<ImageDraft>(createImageDraft())
  const inputs = createImageInputs(form, deps.gateway)
  const artifacts = ref<ImageArtifact[]>([])
  const jobs = ref<ImageJob[]>([])
  const activeJob = ref<ImageJob | null>(null)
  const selectedId = ref<string | null>(null)
  const urls = ref<Record<string, string>>({})
  const imageErrors = ref<Record<string, string>>({})
  const loading = ref(false)
  const historyLoading = ref(false)
  const submitting = ref(false)
  const preparingEdit = ref(false)
  const cancelling = ref(false)
  const savingId = ref<string | null>(null)
  const error = ref<string | null>(null)
  const historyError = ref<string | null>(null)
  const syncError = ref<string | null>(null)
  const hasMore = ref(false)
  const imageModels = computed(() =>
    models.items.filter((model) => model.task === 'image-generation'),
  )
  const modelError = computed(() => models.error)
  const selectedArtifact = computed(
    () => artifacts.value.find((item) => item.id === selectedId.value) ?? null,
  )
  const hasActiveJob = computed(() => !!activeJob.value && !isTerminal(activeJob.value))
  const poller = new JobPoller()
  let epoch = 0
  let scope = new AbortController()
  let disposed = false
  const media = new MediaCache(deps.gateway.image, () => {
    urls.value = media.snapshot()
  })
  let historyTask: Promise<void> | undefined
  let polling = false
  const loadingImages = new Set<string>()

  async function loadWorkspace(): Promise<void> {
    scope.abort()
    scope = new AbortController()
    const owner = ++epoch
    disposed = false
    loading.value = true
    error.value = null
    try {
      await deps.refreshModels()
      if (!imageModels.value.some((item) => item.id === form.value.modelId)) {
        form.value.modelId =
          imageModels.value.find(
            (item) => item.source !== 'builtin' && item.capabilities.imageEditing,
          )?.id ??
          imageModels.value.find((item) => item.source !== 'builtin')?.id ??
          imageModels.value[0]?.id ??
          null
      }
      const nextJobs = await deps.gateway.listJobs(scope.signal)
      if (owner !== epoch || disposed) return
      jobs.value = nextJobs
      activeJob.value =
        jobs.value.find((item) => !isTerminal(item)) ?? activeJob.value ?? jobs.value[0] ?? null
      await loadHistory(true)
      if (hasActiveJob.value) schedulePoll()
      await inputs.restoreInputs()
    } catch (cause) {
      error.value = errorText(cause)
    } finally {
      loading.value = false
    }
  }

  async function loadHistory(reset = true): Promise<void> {
    const owner = epoch
    if (historyTask) await historyTask
    if (owner !== epoch || disposed) return
    const task = fetchHistoryPage(reset)
    historyTask = task
    try {
      await task
    } finally {
      if (historyTask === task) historyTask = undefined
    }
  }

  async function fetchHistoryPage(reset: boolean): Promise<void> {
    const owner = epoch
    historyLoading.value = true
    historyError.value = null
    try {
      const offset = reset ? 0 : artifacts.value.length
      const next = await deps.gateway.history(offset, scope.signal)
      if (owner !== epoch || disposed) return
      artifacts.value = reset ? next : [...artifacts.value, ...next]
      hasMore.value = next.length === 24
      if (!artifacts.value.some((item) => item.id === selectedId.value))
        selectedId.value = artifacts.value[0]?.id ?? null
      await Promise.all(next.map((item) => loadImage(item.id)))
      const source = selectedArtifact.value?.reference_ids?.[0]
      if (source) await inputs.restoreInputs([source])
    } catch (cause) {
      if (owner === epoch && !disposed) historyError.value = errorText(cause)
    } finally {
      if (owner === epoch && !disposed) historyLoading.value = false
    }
  }

  async function loadImage(id: string): Promise<void> {
    const owner = epoch
    if (urls.value[id] || loadingImages.has(id)) return
    loadingImages.add(id)
    try {
      await media.get(id)
      if (owner !== epoch || disposed) return
      delete imageErrors.value[id]
    } catch (cause) {
      if (owner === epoch && !disposed) imageErrors.value[id] = errorText(cause)
    } finally {
      loadingImages.delete(id)
    }
  }

  async function generate(): Promise<boolean> {
    const owner = epoch
    if (submitting.value || hasActiveJob.value || inputs.uploading.value || preparingEdit.value)
      return false
    error.value = null
    submitting.value = true
    try {
      const next = await submission.run(form.value)
      if (!next) return false
      if (owner !== epoch || disposed) return false
      activeJob.value = next
      syncError.value = null
      jobs.value = [
        activeJob.value,
        ...jobs.value.filter((item) => item.id !== activeJob.value?.id),
      ]
      schedulePoll()
      return true
    } catch (cause) {
      error.value = errorText(cause)
      return false
    } finally {
      submitting.value = false
    }
  }

  async function refreshJob(): Promise<void> {
    if (!activeJob.value || polling) return
    poller.stop()
    const owner = epoch
    polling = true
    const id = activeJob.value.id
    syncError.value = null
    try {
      const next = await deps.gateway.job(id, scope.signal)
      if (owner !== epoch || disposed || activeJob.value?.id !== id) return
      activeJob.value = next
      jobs.value = [next, ...jobs.value.filter((item) => item.id !== id)]
      if (next.state === 'succeeded') {
        await loadHistory(true)
        selectedId.value = next.artifact_id
      } else if (next.state === 'failed') error.value = imageJobError(next.error_code)
      if (!isTerminal(next)) schedulePoll()
    } catch (cause) {
      if (owner === epoch && !disposed) syncError.value = `任务状态同步中断：${errorText(cause)}`
    } finally {
      polling = false
    }
  }

  function schedulePoll(): void {
    if (!disposed) poller.schedule(refreshJob)
  }

  async function cancel(): Promise<void> {
    if (!activeJob.value || !hasActiveJob.value || cancelling.value) return
    cancelling.value = true
    try {
      await deps.gateway.cancel(activeJob.value.id)
      await refreshJob()
    } catch (cause) {
      error.value = errorText(cause)
    } finally {
      cancelling.value = false
    }
  }

  function selectArtifact(id: string): void {
    selectedId.value = id
    void loadImage(id)
    const source = selectedArtifact.value?.reference_ids?.[0]
    if (source) void inputs.restoreInputs([source])
  }

  function reuse(item: ImageArtifact | ImageJob): void {
    if (hasActiveJob.value || submitting.value) return
    form.value = createImageDraft(
      item,
      imageModels.value.map((model) => model.id),
    )
    void inputs.restoreInputs()
    error.value = form.value.modelId ? null : '历史作品使用的模型已移除，请重新选择模型。'
  }

  async function saveArtifact(id: string): Promise<void> {
    const owner = epoch
    savingId.value = id
    try {
      const blob = await deps.gateway.image(id, scope.signal)
      if (owner === epoch && !disposed) await deps.exportImage(blob, id)
    } catch (cause) {
      if (owner === epoch && !disposed)
        error.value = cause instanceof Error ? cause.message : 'Image export failed'
    } finally {
      savingId.value = null
    }
  }

  async function editArtifact(): Promise<void> {
    const item = selectedArtifact.value
    if (
      !item ||
      hasActiveJob.value ||
      submitting.value ||
      inputs.uploading.value ||
      preparingEdit.value
    )
      return
    const model =
      imageModels.value.find(
        (entry) => entry.id === form.value.modelId && entry.capabilities.imageEditing,
      ) ??
      imageModels.value.find(
        (entry) => entry.source !== 'builtin' && entry.capabilities.imageEditing,
      )
    if (!model) {
      error.value = '请先导入支持图片编辑的完整模型。'
      return
    }
    const owner = epoch
    preparingEdit.value = true
    try {
      const blob = await deps.gateway.image(item.id, scope.signal)
      if (owner !== epoch || disposed) return
      form.value = {
        ...form.value,
        modelId: model.id,
        mode: 'edit',
        prompt: '',
        referenceIds: [],
        maskId: null,
        strength: 1,
        width: item.width,
        height: item.height,
        steps: 40,
      }
      await inputs.uploadReferences([new File([blob], '原作品.png', { type: 'image/png' })])
    } catch (cause) {
      if (owner === epoch && !disposed) error.value = errorText(cause)
    } finally {
      if (owner === epoch) preparingEdit.value = false
    }
  }

  function dispose(): void {
    disposed = true
    scope.abort()
    submitting.value = false
    preparingEdit.value = false
    cancelling.value = false
    savingId.value = null
    epoch += 1
    poller.stop()
    polling = false
    historyTask = undefined
    loadingImages.clear()
    media.dispose()
    inputs.disposeInputs()
  }

  return {
    ...inputs,
    editArtifact,
    preparingEdit,
    form,
    artifacts,
    jobs,
    activeJob,
    selectedId,
    urls,
    imageErrors,
    loading,
    historyLoading,
    submitting,
    cancelling,
    savingId,
    error,
    historyError,
    syncError,
    hasMore,
    imageModels,
    modelError,
    selectedArtifact,
    hasActiveJob,
    loadWorkspace,
    loadHistory,
    loadImage,
    generate,
    refreshJob,
    cancel,
    selectArtifact,
    reuse,
    saveArtifact,
    dispose,
  }
}
function errorText(cause: unknown): string {
  return cause instanceof ImageValidationError
    ? (validationMessages[cause.code] ?? '图片参数无效')
    : cause instanceof Error
      ? cause.message
      : '图片工作区请求失败'
}
