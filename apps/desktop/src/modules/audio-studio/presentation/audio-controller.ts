import { computed, ref, watch } from 'vue'
import type {
  AudioArtifact,
  AudioGateway,
  AudioJob,
  SpeechDraft,
  Voice,
} from '../application/ports'
import { buildSpeechRequest, compatibleModels, terminal } from '../application/speech-request'
import type { useModelDirectory } from '../../../capabilities/models'
import { MediaCache } from '../../../capabilities/media'
import { JobPoller } from '../../../capabilities/jobs'
import { createVoiceController } from './voice-controller'
import { audioFailure } from './audio-feedback'

interface Dependencies {
  directory: ReturnType<typeof useModelDirectory>
  refreshModels(): Promise<void>
  gateway: AudioGateway
  exportAudio(blob: Blob, id: string): void
}
export function createAudioController(deps: Dependencies) {
  const form = ref<SpeechDraft>({
    modelId: null,
    mode: 'preset',
    text: '',
    language: 'zh',
    speaker: null,
    voiceId: null,
  })
  const voices = ref<Voice[]>([])
  const library = createVoiceController(deps.gateway, voices)
  const artifacts = ref<AudioArtifact[]>([])
  const jobs = ref<AudioJob[]>([])
  const activeJob = ref<AudioJob | null>(null)
  const selectedId = ref<string | null>(null)
  const urls = ref<Record<string, string>>({})
  const error = ref<string | null>(null)
  const syncError = ref<string | null>(null)
  const loading = ref(false),
    submitting = ref(false),
    cancelling = ref(false)
  const historyLoading = ref(false),
    hasMore = ref(false)
  const savingId = ref<string | null>(null)
  const speechModels = computed(() => compatibleModels(deps.directory.items, form.value.mode))
  const selectedModel = computed(() =>
    speechModels.value.find((model) => model.id === form.value.modelId),
  )
  const selectedArtifact = computed(
    () => artifacts.value.find((item) => item.id === selectedId.value) ?? null,
  )
  const busy = computed(() => !!activeJob.value && !terminal(activeJob.value))
  const media = new MediaCache(
    deps.gateway.audio,
    () => {
      urls.value = media.snapshot()
    },
    2,
  )
  const poller = new JobPoller()
  let epoch = 0,
    disposed = false
  let scope = new AbortController()
  let retry: { key: string; id: string } | undefined
  let polling = false

  watch(
    [speechModels, () => form.value.modelId],
    () => {
      if (!speechModels.value.some((model) => model.id === form.value.modelId))
        form.value.modelId =
          speechModels.value.find((model) => model.source !== 'builtin')?.id ??
          speechModels.value[0]?.id ??
          null
      const operation = selectedModel.value?.speech?.operations.find(
        (op) => op.mode === form.value.mode,
      )
      if (!operation?.presetSpeakers.includes(form.value.speaker ?? ''))
        form.value.speaker = operation?.presetSpeakers[0] ?? null
      if (!operation?.languages.includes(form.value.language))
        form.value.language = operation?.languages[0] ?? 'auto'
    },
    { flush: 'sync', immediate: true },
  )

  async function action(run: (owner: number) => Promise<void>): Promise<boolean> {
    const owner = epoch
    error.value = null
    try {
      await run(owner)
      return owner === epoch && !disposed
    } catch (cause) {
      if (owner === epoch && !disposed)
        error.value = cause instanceof Error ? cause.message : '语音工作区请求失败'
      return false
    }
  }
  async function loadWorkspace(): Promise<void> {
    dispose()
    disposed = false
    scope = new AbortController()
    const owner = epoch
    loading.value = true
    await action(async () => {
      const [, nextVoices, nextJobs, nextReferences] = await Promise.all([
        deps.refreshModels(),
        deps.gateway.voices(scope.signal),
        deps.gateway.jobs(scope.signal),
        deps.gateway.references(scope.signal),
      ])
      if (owner !== epoch) return
      voices.value = nextVoices
      library.references = nextReferences
      jobs.value = nextJobs
      if (!nextVoices.some((v) => v.id === form.value.voiceId))
        form.value.voiceId = nextVoices[0]?.id ?? null
      const resuming = activeJob.value ? !terminal(activeJob.value) : true
      activeJob.value = nextJobs.find((job) => !terminal(job)) ?? nextJobs[0] ?? null
      if (resuming && activeJob.value?.artifact_id) selectedId.value = activeJob.value.artifact_id
      await loadHistory(true)
      if (owner === epoch && busy.value) poller.schedule(refreshJob)
    })
    if (owner === epoch) loading.value = false
  }
  async function loadHistory(reset = true): Promise<void> {
    if (historyLoading.value) return
    const owner = epoch
    historyLoading.value = true
    await action(async () => {
      const page = await deps.gateway.history(reset ? 0 : artifacts.value.length, scope.signal)
      if (owner !== epoch) return
      artifacts.value = reset ? page : [...artifacts.value, ...page]
      hasMore.value = page.length === 24
      if (!artifacts.value.some((item) => item.id === selectedId.value))
        selectedId.value = artifacts.value[0]?.id ?? null
      if (selectedId.value) await select(selectedId.value)
    })
    if (owner === epoch) historyLoading.value = false
  }
  async function select(id: string): Promise<void> {
    selectedId.value = id
    await action(async () => {
      await media.get(id)
    })
  }
  async function generate(): Promise<void> {
    if (busy.value || submitting.value || disposed) return
    submitting.value = true
    const owner = epoch
    await action(async () => {
      const request = buildSpeechRequest(form.value, deps.directory.items)
      const key = JSON.stringify(request)
      if (retry?.key !== key) retry = { key, id: crypto.randomUUID() }
      const job = await deps.gateway.generate({ ...request, clientRequestId: retry.id })
      if (owner !== epoch) return
      retry = undefined
      activeJob.value = job
      jobs.value = [job, ...jobs.value.filter((item) => item.id !== job.id)]
      poller.schedule(refreshJob)
    })
    if (owner === epoch) submitting.value = false
  }
  async function refreshJob(): Promise<void> {
    if (polling || disposed || !activeJob.value) return
    polling = true
    poller.stop()
    const owner = epoch,
      id = activeJob.value.id
    try {
      const job = await deps.gateway.job(id, scope.signal)
      if (owner !== epoch) return
      activeJob.value = job
      jobs.value = jobs.value.map((item) => (item.id === id ? job : item))
      syncError.value = null
      if (job.state === 'succeeded') {
        selectedId.value = job.artifact_id
        await loadHistory(true)
      }
      if (job.state === 'failed') error.value = audioFailure(job.error_code)
      if (terminal(job)) {
        const nextJobs = await deps.gateway.jobs(scope.signal)
        if (owner !== epoch) return
        jobs.value = nextJobs
        activeJob.value = nextJobs.find((item) => !terminal(item)) ?? job
      }
      if (busy.value) poller.schedule(refreshJob)
    } catch (cause) {
      if (owner === epoch) syncError.value = cause instanceof Error ? cause.message : '任务同步中断'
    } finally {
      if (owner === epoch) polling = false
    }
  }
  async function cancel(): Promise<void> {
    if (!activeJob.value || !busy.value || cancelling.value) return
    const id = activeJob.value.id,
      owner = epoch
    cancelling.value = true
    await action(async () => {
      await deps.gateway.cancel(id)
      if (owner === epoch) await refreshJob()
    })
    if (owner === epoch) cancelling.value = false
  }
  function reuse(item: AudioArtifact | AudioJob): void {
    if (busy.value || submitting.value) return
    form.value = {
      mode: item.mode,
      modelId: item.model_id,
      text: item.text,
      language: item.language,
      speaker: item.speaker,
      voiceId: voices.value.some((v) => v.id === item.voice_id) ? item.voice_id : null,
    }
    if (item.mode === 'clone' && !form.value.voiceId)
      error.value = '原音色已删除，请重新选择或保存音色。'
  }
  async function save(id: string): Promise<void> {
    const owner = epoch
    savingId.value = id
    await action(async () => {
      const blob = await deps.gateway.audio(id, scope.signal)
      if (owner === epoch) deps.exportAudio(blob, id)
    })
    if (owner === epoch) savingId.value = null
  }
  async function remove(id: string): Promise<void> {
    await action(async (owner) => {
      await deps.gateway.deleteArtifact(id)
      if (owner === epoch) {
        media.dispose()
        await loadHistory(true)
      }
    })
  }
  function dispose(): void {
    epoch++
    disposed = true
    scope.abort()
    poller.stop()
    media.dispose()
    library.dispose()
    loading.value = false
    submitting.value = false
    cancelling.value = false
    historyLoading.value = false
    polling = false
    savingId.value = null
  }
  return {
    form,
    voices,
    library,
    artifacts,
    jobs,
    activeJob,
    selectedId,
    urls,
    error,
    syncError,
    loading,
    submitting,
    cancelling,
    historyLoading,
    hasMore,
    savingId,
    speechModels,
    selectedModel,
    selectedArtifact,
    busy,
    loadWorkspace,
    loadHistory,
    select,
    generate,
    refreshJob,
    cancel,
    reuse,
    save,
    remove,
    dispose,
  }
}
