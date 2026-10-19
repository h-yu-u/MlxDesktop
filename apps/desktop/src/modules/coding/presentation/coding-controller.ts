import type { CodingControllerDependencies } from './coding-controller-ports'
import { SubmissionIdentity } from '../../../capabilities/requests'
import { createProjectSessionController } from './project-session-controller'
import { projectCodingEvent } from './event-projection'
import { decodeCodingProjection } from '@mlx-studio/api-client'
import { createCodingInspector } from './coding-inspector-controller'
import { codingErrorText } from './coding-errors'
import { modelNeedsVerification, submitCodingRun } from '../application/submit-coding-run'
import { ensureModelCapability } from '../application/ensure-model-capability'
import { computed, ref } from 'vue'
import type { CodingSessionPatch, ExtensionSelection as Selection } from '@mlx-studio/api-client'
import type {
  CodingProject,
  CodingSession,
  CodingSnapshot,
  CodingCapability,
  CodingEvent,
} from '../application/ports'
import { activeStatus, isVerified, type CodingMode } from '../domain/status'
export function createCodingController(deps: CodingControllerDependencies) {
  const projects = ref<CodingProject[]>([]),
    snapshot = ref<CodingSnapshot | null>(null)
  const capabilities = ref<CodingCapability[]>([]),
    selectedModelId = ref(''),
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
  const active = computed(() => snapshot.value?.activeRun ?? null)
  const busy = computed(() => !!active.value && activeStatus(active.value.status))
  const projectSelection = createProjectSessionController({
    gateway: deps.gateway,
    guard,
    alive: () => !disposed,
    pending: () => pending.value,
    clearSession: () => {
      epoch++
      release?.()
      release = undefined
      sessionId.value = ''
      snapshot.value = null
      inspector.resetInspector()
    },
  })
  const { projectId, sessions, sessionsHasMore, selectProject, loadMoreSessions } = projectSelection
  const inspector = createCodingInspector({
    gateway: deps.gateway,
    sessionId,
    busy,
    onRestored: refresh,
  })
  const submissionIdentity = new SubmissionIdentity()
  const pendingRequests = new Set<symbol>()
  let disposed = false
  let epoch = 0,
    release: (() => void) | undefined
  async function guard<T>(action: () => Promise<T>, valid?: () => boolean): Promise<T | undefined> {
    const owner = epoch
    const request = Symbol()
    pendingRequests.add(request)
    pending.value = true
    error.value = null
    try {
      return await action()
    } catch (cause) {
      if (owner !== epoch || disposed || valid?.() === false) return undefined
      error.value = codingErrorText(cause)
      if (modelNeedsVerification(cause))
        capabilities.value = capabilities.value.filter((item) => item.id !== selectedModelId.value)
      return undefined
    } finally {
      pendingRequests.delete(request)
      pending.value = pendingRequests.size > 0
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
  function applyEvent(event: CodingEvent): boolean {
    if (!snapshot.value || disposed) return false
    try {
      const next = projectCodingEvent(snapshot.value, event, decodeCodingProjection(event.data))
      if (!next) return false
      snapshot.value = next
      if (
        event.sessionId === sessionId.value &&
        ['file.changed', 'file.restored'].includes(event.type)
      )
        void inspector.refreshInspector()
      return true
    } catch {
      return false
    }
  }
  async function openSession(id: string): Promise<void> {
    const owner = ++epoch
    release?.()
    release = undefined
    sessionId.value = id
    snapshot.value = null
    inspector.resetInspector()
    await guard(async () => {
      const after = await refresh()
      if (owner !== epoch || disposed || sessionId.value !== id) return
      release = deps.observe(
        after,
        refresh,
        (cause) => {
          if (owner !== epoch || disposed) return
          error.value = cause instanceof Error ? cause.message : '正在重新连接 Coding'
        },
        (event) => owner === epoch && !disposed && applyEvent(event),
      )
    })
  }
  async function loadWorkspace(routeProject?: string, routeSession?: string): Promise<void> {
    disposed = false
    const owner = ++epoch
    release?.()
    release = undefined
    await guard(async () => {
      const [items, caps, settings] = await Promise.all([
        deps.gateway.projects(),
        deps.gateway.capabilities(),
        deps.gateway.settings(),
        deps.refreshModels(),
      ])
      if (owner !== epoch || disposed) return
      projects.value = items
      capabilities.value = caps
      if (!selectedModelId.value)
        selectedModelId.value =
          settings.defaultModelId ||
          (caps.find((item) => item.status === 'verified')?.id ?? models.value[0]?.value ?? '')
    })
    if (owner !== epoch || disposed) return
    const target = routeProject ?? (projectId.value || projects.value[0]?.id)
    const selection = projectSelection.generation + 1
    const selectionEpoch = epoch + (target && target !== projectId.value ? 1 : 0)
    if (target) await selectProject(target)
    if (
      disposed ||
      epoch !== selectionEpoch ||
      (target && selection !== projectSelection.generation)
    )
      return
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
    const owner = epoch,
      project = projectId.value
    const session = await guard(() => deps.gateway.create(project))
    if (!session || owner !== epoch || disposed || project !== projectId.value) return
    sessions.value = [session, ...sessions.value]
    await openSession(session.id)
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
  async function send(text: string, queue = false, selection?: Selection): Promise<boolean> {
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
      await submitCodingRun(
        { sessionId: target, modelId, text, mode: selectedMode, queue, selection },
        {
          gateway: deps.gateway,
          ensure: prepareModel,
          invalidate: (id) => {
            capabilities.value = capabilities.value.filter((item) => item.id !== id)
          },
          createId: () =>
            submissionIdentity.for({ target, modelId, text, selectedMode, queue, selection }),
        },
      )
      await refresh()
      submissionIdentity.clear()
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
  async function prepareModel(id: string, force = false): Promise<void> {
    await ensureModelCapability(
      id,
      {
        gateway: deps.gateway,
        capabilities: () => capabilities.value,
        update: (result) => {
          capabilities.value = [
            ...capabilities.value.filter((item) => item.id !== result.id),
            result,
          ]
        },
        preparing: (value) => {
          preparingModel.value = value
        },
      },
      force,
    )
  }
  async function verifyModel(): Promise<void> {
    await guard(() => prepareModel(selectedModelId.value, true))
  }
  function dispose(): void {
    disposed = true
    projectSelection.dispose()
    pendingRequests.clear()
    pending.value = false
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
    modelReady: computed(() => isVerified(capabilities.value, selectedModelId.value)),
    active,
    busy,
    loadWorkspace,
    openProject,
    selectProject,
    sessionsHasMore,
    loadMoreSessions,
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
