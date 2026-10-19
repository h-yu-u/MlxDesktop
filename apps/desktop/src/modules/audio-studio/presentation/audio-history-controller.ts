import { computed, ref } from 'vue'
import { RequestScope } from '../../../capabilities/requests'
import { MediaCache } from '../../../capabilities/media'
import type { AudioArtifact, AudioGateway } from '../application/ports'
interface Dependencies {
  gateway: AudioGateway
  exportAudio(blob: Blob, id: string): Promise<void> | void
  onError(cause: unknown): void
}
export function createAudioHistoryController(deps: Dependencies) {
  const artifacts = ref<AudioArtifact[]>([]),
    selectedId = ref<string | null>(null)
  const urls = ref<Record<string, string>>({}),
    historyLoading = ref(false),
    hasMore = ref(false)
  const savingId = ref<string | null>(null)
  const selectedArtifact = computed(
    () => artifacts.value.find((item) => item.id === selectedId.value) ?? null,
  )
  const scope = new RequestScope()
  const media = new MediaCache(
    deps.gateway.audio,
    () => {
      urls.value = media.snapshot()
    },
    2,
  )
  async function action(run: (owner: number) => Promise<void>): Promise<void> {
    const owner = scope.owner
    try {
      await run(owner)
    } catch (cause) {
      if (scope.owns(owner)) deps.onError(cause)
    }
  }
  async function loadHistory(reset = true): Promise<void> {
    if (historyLoading.value) return
    const owner = scope.owner
    historyLoading.value = true
    await action(async () => {
      const page = await deps.gateway.history(reset ? 0 : artifacts.value.length, scope.signal)
      if (!scope.owns(owner)) return
      artifacts.value = reset ? page : [...artifacts.value, ...page]
      hasMore.value = page.length === 24
      if (!artifacts.value.some((item) => item.id === selectedId.value))
        selectedId.value = artifacts.value[0]?.id ?? null
      if (selectedId.value) await select(selectedId.value)
    })
    if (scope.owns(owner)) historyLoading.value = false
  }
  async function select(id: string): Promise<void> {
    selectedId.value = id
    await action(async () => {
      await media.get(id)
    })
  }
  async function save(id: string): Promise<void> {
    const owner = scope.owner
    savingId.value = id
    await action(async () => {
      const blob = await deps.gateway.audio(id, scope.signal)
      if (scope.owns(owner)) await deps.exportAudio(blob, id)
    })
    if (scope.owns(owner)) savingId.value = null
  }
  async function remove(id: string): Promise<void> {
    await action(async (owner) => {
      await deps.gateway.deleteArtifact(id)
      if (scope.owns(owner)) {
        media.dispose()
        await loadHistory(true)
      }
    })
  }
  function dispose(): void {
    scope.dispose()
    media.dispose()
    historyLoading.value = false
    savingId.value = null
  }
  function activate(): void {
    scope.reset()
  }
  return {
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
    dispose,
    activate,
  }
}
