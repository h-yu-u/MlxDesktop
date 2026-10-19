import { createAudioHistoryController } from './audio-history-controller'
import { SubmitSpeech } from '../application/submit-speech'
import { computed, ref, watch } from 'vue'
import type {
  AudioArtifact,
  AudioGateway,
  AudioJob,
  SpeechDraft,
  Voice,
} from '../application/ports'
import { compatibleModels, terminal } from '../application/speech-request'
import type { useModelDirectory } from '../../../capabilities/models'
import { JobPoller } from '../../../capabilities/jobs'
import { createVoiceController } from './voice-controller'
import { audioFailure } from './audio-feedback'

interface Dependencies {
  directory: ReturnType<typeof useModelDirectory>
  refreshModels(): Promise<void>
  gateway: AudioGateway
  exportAudio(blob: Blob, id: string): Promise<void> | void
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
  const jobs = ref<AudioJob[]>([])
  const activeJob = ref<AudioJob | null>(null)
  const error = ref<string | null>(null)
  const syncError = ref<string | null>(null)
  const loading = ref(false),
    submitting = ref(false),
    cancelling = ref(false)
  const speechModels = computed(() => compatibleModels(deps.directory.items, form.value.mode))
  const selectedModel = computed(() =>
    speechModels.value.find((model) => model.id === form.value.modelId),
  )
  const busy = computed(() => !!activeJob.value && !terminal(activeJob.value))
  const history = createAudioHistoryController({
    ...deps,
    onError: (cause) => {
      error.value = cause instanceof Error ? cause.message : '作品请求失败'
    },
  })
  const {
    artifacts,
    selectedId,
    selectedArtifact,
    urls,
    historyLoading,
    hasMore,
    savingId,
    loadHistory,
    select,
    save,
    remove,
  } = history
  const poller = new JobPoller()
  let epoch = 0,
    disposed = false
  let scope = new AbortController()
  const submit = new SubmitSpeech(deps.gateway, () => crypto.randomUUID())
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
    history.activate()
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
  async function generate(): Promise<void> {
    if (busy.value || submitting.value || disposed) return
    submitting.value = true
    const owner = epoch
    await action(async () => {
      const job = await submit.execute(form.value, deps.directory.items)
      if (owner !== epoch) return
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
      poller.recovered()
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
      if (owner === epoch && !disposed) {
        syncError.value = cause instanceof Error ? cause.message : '任务同步中断'
        if (busy.value) poller.retry(refreshJob, cause)
      }
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
  function dispose(): void {
    epoch++
    disposed = true
    scope.abort()
    poller.stop()
    poller.recovered()
    history.dispose()
    library.dispose()
    loading.value = false
    submitting.value = false
    cancelling.value = false
    polling = false
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
