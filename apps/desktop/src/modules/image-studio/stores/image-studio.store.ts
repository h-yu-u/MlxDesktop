import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { runtimeClient } from '../../../shared/api/runtime'
import { useModelsStore } from '../../models/stores/models.store'
import { buildImageRequest, imageJobError, isTerminal, readArtifact, readJob, readList, type ImageArtifact, type ImageDraft, type ImageJob } from '../domain/image-state'
import { saveImageBlob } from '../services/save-image'

export const useImageStudioStore = defineStore('image-studio', () => {
  const models = useModelsStore()
  const form = ref<ImageDraft>({ modelId: null, prompt: '', width: 512, height: 512, steps: 20, seed: null })
  const artifacts = ref<ImageArtifact[]>([])
  const jobs = ref<ImageJob[]>([])
  const activeJob = ref<ImageJob | null>(null)
  const selectedId = ref<string | null>(null)
  const urls = ref<Record<string, string>>({})
  const imageErrors = ref<Record<string, string>>({})
  const loading = ref(false)
  const historyLoading = ref(false)
  const submitting = ref(false)
  const cancelling = ref(false)
  const savingId = ref<string | null>(null)
  const error = ref<string | null>(null)
  const historyError = ref<string | null>(null)
  const syncError = ref<string | null>(null)
  const hasMore = ref(false)
  const imageModels = computed(() => models.items.filter((model) => model.task === 'image-generation'))
  const modelError = computed(() => models.error)
  const selectedArtifact = computed(() => artifacts.value.find((item) => item.id === selectedId.value) ?? null)
  const hasActiveJob = computed(() => !!activeJob.value && !isTerminal(activeJob.value))
  let pollTimer: ReturnType<typeof setTimeout> | undefined
  let historyTask: Promise<void> | undefined
  let polling = false
  const loadingImages = new Set<string>()

  async function loadWorkspace(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await models.refresh()
      if (!imageModels.value.some((item) => item.id === form.value.modelId)) {
        form.value.modelId = imageModels.value.find((item) => item.source !== 'builtin')?.id ?? imageModels.value[0]?.id ?? null
      }
      const client = await runtimeClient()
      jobs.value = readList(await client.get('/internal/v1/image-jobs'), readJob)
      activeJob.value = jobs.value.find((item) => !isTerminal(item)) ?? activeJob.value ?? jobs.value[0] ?? null
      await loadHistory(true)
      if (hasActiveJob.value) schedulePoll()
    } catch (cause) { error.value = errorText(cause) }
    finally { loading.value = false }
  }

  async function loadHistory(reset = true): Promise<void> {
    if (historyTask) await historyTask
    const task = fetchHistoryPage(reset)
    historyTask = task
    try { await task }
    finally { if (historyTask === task) historyTask = undefined }
  }

  async function fetchHistoryPage(reset: boolean): Promise<void> {
    historyLoading.value = true
    historyError.value = null
    try {
      const client = await runtimeClient()
      const offset = reset ? 0 : artifacts.value.length
      const next = readList(await client.get(`/internal/v1/image-artifacts?limit=24&offset=${offset}`), readArtifact)
      artifacts.value = reset ? next : [...artifacts.value, ...next]
      hasMore.value = next.length === 24
      if (!artifacts.value.some((item) => item.id === selectedId.value)) selectedId.value = artifacts.value[0]?.id ?? null
      const keep = new Set(artifacts.value.map((item) => item.id))
      for (const id of Object.keys(urls.value)) {
        if (!keep.has(id)) { URL.revokeObjectURL(urls.value[id] ?? ''); delete urls.value[id]; delete imageErrors.value[id] }
      }
      await Promise.all(next.map((item) => loadImage(item.id)))
    } catch (cause) { historyError.value = errorText(cause) }
    finally { historyLoading.value = false }
  }

  async function loadImage(id: string): Promise<void> {
    if (urls.value[id] || loadingImages.has(id)) return
    loadingImages.add(id)
    try {
      const blob = await (await runtimeClient()).downloadImageArtifact(id)
      urls.value[id] = URL.createObjectURL(blob)
      delete imageErrors.value[id]
    } catch (cause) { imageErrors.value[id] = errorText(cause) }
    finally { loadingImages.delete(id) }
  }

  async function generate(): Promise<boolean> {
    if (submitting.value || hasActiveJob.value) return false
    error.value = null
    submitting.value = true
    try {
      const request = buildImageRequest(form.value)
      activeJob.value = readJob(await (await runtimeClient()).post('/internal/v1/image-jobs', request))
      syncError.value = null
      jobs.value = [activeJob.value, ...jobs.value.filter((item) => item.id !== activeJob.value?.id)]
      schedulePoll()
      return true
    } catch (cause) { error.value = errorText(cause); return false }
    finally { submitting.value = false }
  }

  async function refreshJob(): Promise<void> {
    if (!activeJob.value || polling) return
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = undefined }
    polling = true
    const id = activeJob.value.id
    syncError.value = null
    try {
      const next = readJob(await (await runtimeClient()).get(`/internal/v1/image-jobs/${encodeURIComponent(id)}`))
      if (activeJob.value?.id !== id) return
      activeJob.value = next
      jobs.value = [next, ...jobs.value.filter((item) => item.id !== id)]
      if (next.state === 'succeeded') {
        await loadHistory(true)
        selectedId.value = next.artifact_id
      } else if (next.state === 'failed') error.value = imageJobError(next.error_code)
      if (!isTerminal(next)) schedulePoll()
    } catch (cause) { syncError.value = `任务状态同步中断：${errorText(cause)}` }
    finally { polling = false }
  }

  function schedulePoll(): void {
    if (pollTimer) clearTimeout(pollTimer)
    pollTimer = setTimeout(() => { pollTimer = undefined; void refreshJob() }, 750)
  }

  async function cancel(): Promise<void> {
    if (!activeJob.value || !hasActiveJob.value || cancelling.value) return
    cancelling.value = true
    try {
      await (await runtimeClient()).post(`/internal/v1/image-jobs/${encodeURIComponent(activeJob.value.id)}/cancel`)
      await refreshJob()
    } catch (cause) { error.value = errorText(cause) }
    finally { cancelling.value = false }
  }

  function selectArtifact(id: string): void {
    selectedId.value = id
    void loadImage(id)
  }

  function reuse(item: ImageArtifact | ImageJob): void {
    if (hasActiveJob.value || submitting.value) return
    form.value = { modelId: imageModels.value.some((model) => model.id === item.model_id) ? item.model_id : null,
      prompt: item.prompt, width: item.width, height: item.height, steps: item.steps, seed: item.seed }
    error.value = form.value.modelId ? null : '历史作品使用的模型已移除，请重新选择模型。'
  }

  async function saveArtifact(id: string): Promise<void> {
    savingId.value = id
    try { saveImageBlob(await (await runtimeClient()).downloadImageArtifact(id), id) }
    finally { savingId.value = null }
  }

  function dispose(): void {
    if (pollTimer) clearTimeout(pollTimer)
    for (const url of Object.values(urls.value)) URL.revokeObjectURL(url)
    urls.value = {}
  }

  return { form, artifacts, jobs, activeJob, selectedId, urls, imageErrors, loading, historyLoading,
    submitting, cancelling, savingId, error, historyError, syncError, hasMore, imageModels, modelError,
    selectedArtifact, hasActiveJob, loadWorkspace, loadHistory, loadImage, generate, refreshJob, cancel,
    selectArtifact, reuse, saveArtifact, dispose }
})
function errorText(cause: unknown): string { return cause instanceof Error ? cause.message : '图片工作区请求失败' }
