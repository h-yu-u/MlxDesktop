import { computed, ref, type Ref } from 'vue'
import type {
  AgentChatSnapshot,
  AgentChatRequest,
  AgentSession,
  ExtensionSelection,
  ModelSummary,
  agentChatEndpoints,
} from '@mlx-studio/api-client'
import { extensionError } from './errors'
interface Dependencies {
  gateway: ReturnType<typeof agentChatEndpoints>
  models: Readonly<Ref<readonly ModelSummary[]>>
  refreshModels(): Promise<void>
  verifyModel(id: string): Promise<unknown>
}
export function createAgentController(deps: Dependencies) {
  const sessions = ref<AgentSession[]>([]),
    sessionId = ref(''),
    modelId = ref('')
  const snapshot = ref<AgentChatSnapshot | null>(null),
    pending = ref(false),
    error = ref(''),
    text = ref('')
  const models = computed(() =>
    deps.models.value
      .filter((model) => model.outputModalities.includes('text'))
      .map((model) => ({ label: model.displayName, value: model.id })),
  )
  const active = computed(() =>
    snapshot.value?.runs.find((run) =>
      ['queued', 'starting', 'running', 'awaiting_approval', 'cancelling'].includes(run.status),
    ),
  )
  let epoch = 0,
    watching: number | undefined
  let retry: { key: string; body: AgentChatRequest } | undefined
  async function guard<T>(action: () => Promise<T>): Promise<T | undefined> {
    const owner = epoch
    pending.value = true
    error.value = ''
    try {
      return await action()
    } catch (cause) {
      if (owner === epoch) error.value = extensionError(cause)
    } finally {
      if (owner === epoch) pending.value = false
    }
  }
  async function refresh(): Promise<void> {
    const owner = epoch,
      id = sessionId.value
    if (!id) return
    const value = await deps.gateway.snapshot(id)
    if (owner === epoch && sessionId.value === id) snapshot.value = value
  }
  async function observe(): Promise<void> {
    if (watching === epoch) return
    const owner = epoch
    watching = owner
    try {
      while (owner === epoch) {
        await refresh()
        if (!active.value) break
        await new Promise((resolve) => setTimeout(resolve, 350))
      }
    } catch (cause) {
      if (owner === epoch) error.value = extensionError(cause)
    } finally {
      if (watching === owner) watching = undefined
    }
  }
  return {
    sessions,
    sessionId,
    modelId,
    snapshot,
    pending,
    error,
    text,
    models,
    active,
    async load() {
      await guard(async () => {
        const owner = epoch
        await deps.refreshModels()
        const items = await deps.gateway.sessions()
        if (owner !== epoch) return
        sessions.value = items
        if (!modelId.value) modelId.value = models.value[0]?.value ?? ''
        if (!sessionId.value) sessionId.value = items[0]?.id ?? ''
        await refresh()
        void observe()
      })
    },
    async open(id: string) {
      epoch++
      sessionId.value = id
      snapshot.value = null
      await guard(refresh)
      void observe()
    },
    async create() {
      await guard(async () => {
        const owner = epoch,
          session = await deps.gateway.create()
        if (owner !== epoch) return
        sessions.value = [session, ...sessions.value]
        sessionId.value = session.id
        await refresh()
      })
    },
    async send(selection: ExtensionSelection) {
      if (active.value || pending.value || !text.value.trim()) return
      const owner = epoch,
        submittedText = text.value,
        selectedModel = modelId.value
      const selected: ExtensionSelection = {
        skillIds: [...selection.skillIds],
        toolIds: [...selection.toolIds],
        ...(selection.mediaBindings
          ? {
              mediaBindings: {
                ...selection.mediaBindings,
                imageReferenceIds: selection.mediaBindings.imageReferenceIds
                  ? [...selection.mediaBindings.imageReferenceIds]
                  : undefined,
              },
            }
          : {}),
      }
      await guard(async () => {
        await deps.verifyModel(selectedModel)
        if (owner !== epoch) return
        if (!sessionId.value) {
          const session = await deps.gateway.create()
          if (owner !== epoch) return
          sessions.value = [session, ...sessions.value]
          sessionId.value = session.id
        }
        const target = sessionId.value,
          key = JSON.stringify({
            target,
            text: submittedText,
            modelId: selectedModel,
            selection: selected,
          })
        if (retry?.key !== key)
          retry = {
            key,
            body: {
              submissionId: crypto.randomUUID(),
              text: submittedText,
              modelId: selectedModel,
              mode: 'develop',
              selection: selected,
            },
          }
        await deps.gateway.submit(target, retry.body)
        if (owner !== epoch) return
        await refresh()
        retry = undefined
        if (text.value === submittedText) text.value = ''
        void observe()
      })
    },
    async cancel() {
      if (active.value)
        await guard(async () => {
          await deps.gateway.cancel(active.value!.id)
          await refresh()
        })
    },
    async resolve(id: string, allowed: boolean) {
      await guard(async () => {
        await deps.gateway.resolve(id, allowed)
        await refresh()
      })
    },
    dispose() {
      epoch++
      watching = undefined
    },
  }
}
