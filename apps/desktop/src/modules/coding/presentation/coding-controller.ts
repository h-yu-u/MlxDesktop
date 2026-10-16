import { createCodingInspector } from './coding-inspector-controller'
import { codingErrorText, modelNeedsVerification } from './coding-errors'
import { computed, ref, type Ref } from 'vue'
import type { ModelSummary, CodingSessionPatch } from '@mlx-studio/api-client'
import type {
  CodingGateway,
  CodingProject,
  CodingSession,
  CodingSnapshot,
  CodingCapability,
} from '../application/ports'
import { activeStatus, type CodingMode } from '../domain/status'
interface Dependencies {
  gateway: CodingGateway
  models: Readonly<Ref<readonly ModelSummary[]>>
  refreshModels(): Promise<void>
  pickDirectory(): Promise<string | null>
  observe(after: number, refresh: () => Promise<number>, fail: (error: unknown) => void): () => void
}
export function createCodingController(deps: Dependencies) {
  const projects = ref<CodingProject[]>([]),
    sessions = ref<CodingSession[]>([]),
    snapshot = ref<CodingSnapshot | null>(null)
  const capabilities = ref<CodingCapability[]>([]),
    selectedModelId = ref(''),
    projectId = ref(''),
    sessionId = ref('')
  const mode = ref<CodingMode>('develop'),
    pending = ref(false),
    error = ref<string | null>(null)
  const preparingModel = ref(false)
  const models = computed(() =>
    deps.models.value
      .filter((model) => model.outputModalities.includes('text'))
      .map((model) => ({ label: model.displayName, value: model.id })),
  )
  const modelReady = computed(() =>
    capabilities.value.some(
      (item) => item.id === selectedModelId.value && item.status === 'verified',
    ),
  )
  const active = computed(() => snapshot.value?.activeRun ?? null)
  const busy = computed(() => !!active.value && activeStatus(active.value.status))
  const inspector = createCodingInspector({
    gateway: deps.gateway,
    sessionId,
    busy,
    onRestored: refresh,
  })
  let epoch = 0,
    release: (() => void) | undefined
  async function guard<T>(action: () => Promise<T>): Promise<T | undefined> {
    pending.value = true
    error.value = null
    try {
      return await action()
    } catch (cause) {
      error.value = codingErrorText(cause)
      if (modelNeedsVerification(cause))
        capabilities.value = capabilities.value.filter((item) => item.id !== selectedModelId.value)
      return undefined
    } finally {
      pending.value = false
    }
  }
  async function refresh(): Promise<number> {
    const owner = epoch,
      id = sessionId.value
    if (!id) return 0
    const result = await deps.gateway.snapshot(id)
    if (owner !== epoch || id !== sessionId.value) return result.watermark
    const previous = snapshot.value?.watermark ?? result.watermark
    snapshot.value = result
    if (
      result.events.some(
        (event) =>
          event.seq > previous && ['file.changed', 'verification.finished'].includes(event.type),
      )
    )
      void inspector.refreshInspector()
    error.value = null
    return result.watermark
  }
  async function openSession(id: string): Promise<void> {
    epoch++
    release?.()
    sessionId.value = id
    snapshot.value = null
    inspector.resetInspector()
    await guard(async () => {
      const after = await refresh()
      if (sessionId.value !== id) return
      release = deps.observe(after, refresh, (cause) => {
        error.value = cause instanceof Error ? cause.message : '正在重新连接 Coding'
      })
    })
  }
  async function selectProject(id: string): Promise<void> {
    if (projectId.value !== id) {
      epoch++
      release?.()
      sessionId.value = ''
      snapshot.value = null
      inspector.resetInspector()
    }
    projectId.value = id
    await guard(async () => {
      sessions.value = await deps.gateway.sessions(id)
    })
  }
  async function loadWorkspace(routeProject?: string, routeSession?: string): Promise<void> {
    await guard(async () => {
      const [items, caps, settings] = await Promise.all([
        deps.gateway.projects(),
        deps.gateway.capabilities(),
        deps.gateway.settings(),
        deps.refreshModels(),
      ])
      projects.value = items
      capabilities.value = caps
      if (!selectedModelId.value)
        selectedModelId.value =
          settings.defaultModelId ||
          (caps.find((item) => item.status === 'verified')?.id ?? models.value[0]?.value ?? '')
    })
    const target = routeProject ?? (projectId.value || projects.value[0]?.id)
    if (target) await selectProject(target)
    if (routeSession) await openSession(routeSession)
    else if (sessionId.value) await openSession(sessionId.value)
  }
  async function openProject(): Promise<void> {
    await guard(async () => {
      const path = await deps.pickDirectory()
      if (!path) return
      const project = await deps.gateway.register(path)
      projects.value = [...projects.value.filter((item) => item.id !== project.id), project]
      await selectProject(project.id)
    })
  }
  async function newSession(): Promise<CodingSession | undefined> {
    if (!projectId.value) return
    const session = await guard(() => deps.gateway.create(projectId.value))
    if (session) {
      sessions.value.push(session)
      await openSession(session.id)
    }
    return session
  }
  async function updateSession(id: string, patch: CodingSessionPatch): Promise<void> {
    await guard(async () => {
      const updated = await deps.gateway.update(id, patch)
      sessions.value = sessions.value.map((item) => (item.id === id ? updated : item))
      if (sessionId.value === id) await refresh()
    })
  }
  async function removeSession(id: string): Promise<void> {
    await guard(async () => {
      await deps.gateway.remove(id)
      sessions.value = sessions.value.filter((item) => item.id !== id)
      if (sessionId.value === id) {
        epoch++
        release?.()
        sessionId.value = ''
        snapshot.value = null
        inspector.resetInspector()
      }
    })
  }
  async function send(text: string, queue = false): Promise<boolean> {
    if (
      (busy.value && !queue) ||
      pending.value ||
      !selectedModelId.value ||
      !sessionId.value ||
      !text.trim()
    )
      return false
    const modelId = selectedModelId.value,
      target = sessionId.value,
      selectedMode = mode.value
    return !!(await guard(async () => {
      if (!capabilities.value.some((item) => item.id === modelId && item.status === 'verified'))
        await prepareModel(modelId)
      const submission = {
        submissionId: crypto.randomUUID(),
        text,
        modelId,
        mode: selectedMode,
        queue,
      }
      try {
        await deps.gateway.submit(target, submission)
      } catch (cause) {
        if (!modelNeedsVerification(cause)) throw cause
        capabilities.value = capabilities.value.filter((item) => item.id !== modelId)
        await prepareModel(modelId)
        // Reuse the idempotency key when a cached model identity has expired.
        await deps.gateway.submit(target, submission)
      }
      await refresh()
      return true
    }))
  }
  async function cancel(): Promise<void> {
    if (active.value)
      await guard(async () => {
        await deps.gateway.cancel(active.value!.id)
        await refresh()
      })
  }
  async function steer(text: string): Promise<boolean> {
    return (
      !!active.value &&
      !!(await guard(async () => {
        await deps.gateway.steer(active.value!.id, text)
        await refresh()
        return true
      }))
    )
  }
  async function resolve(id: string, allowed: boolean): Promise<void> {
    await guard(async () => {
      await deps.gateway.resolve(id, allowed)
      await refresh()
    })
  }
  async function cancelActive(): Promise<void> {
    try {
      await deps.gateway.cancelActive()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '停止失败'
    }
  }
  async function prepareModel(id: string): Promise<void> {
    preparingModel.value = true
    try {
      const result = await deps.gateway.verifyModel(id)
      capabilities.value = [...capabilities.value.filter((item) => item.id !== result.id), result]
      if (result.status !== 'verified') throw new Error(result.detail)
    } finally {
      preparingModel.value = false
    }
  }
  async function verifyModel(): Promise<void> {
    await guard(() => prepareModel(selectedModelId.value))
  }
  function dispose(): void {
    epoch++
    release?.()
    release = undefined
    inspector.resetInspector()
  }
  return {
    projects,
    sessions,
    snapshot,
    capabilities,
    selectedModelId,
    projectId,
    sessionId,
    mode,
    pending,
    error,
    preparingModel,
    ...inspector,
    models,
    modelReady,
    active,
    busy,
    loadWorkspace,
    openProject,
    selectProject,
    openSession,
    newSession,
    updateSession,
    removeSession,
    send,
    cancel,
    steer,
    resolve,
    verifyModel,
    cancelActive,
    dispose,
  }
}
