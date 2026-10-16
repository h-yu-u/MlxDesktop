import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { RuntimeError } from '@mlx-studio/api-client'
import { createCodingController } from './coding-controller'
import type { CodingGateway, CodingSnapshot } from '../application/ports'
const project = {
  id: 'p',
  name: 'project',
  path: '/project',
  git: false,
  branch: '',
  dirty: '',
  instructions: '',
  commands: [],
}
const session = {
  id: 's',
  projectId: 'p',
  title: 'session',
  pinned: false,
  archived: false,
  piPath: null,
}
const run = {
  id: 'r',
  sessionId: 's',
  submissionId: 'request',
  text: 'task',
  modelId: 'fake',
  mode: 'develop' as const,
  status: 'running' as const,
  phase: 'exploring',
  verification: 'not_run' as const,
  error: null,
  createdAt: '',
  baseline: '',
  fingerprint: null,
  maxRepairRounds: 2,
}
function snapshot(id = 's'): CodingSnapshot {
  return {
    session: { ...session, id },
    project,
    runs: [],
    approvals: [],
    verifications: [],
    events: [],
    watermark: 12,
    activeRun: null,
  }
}
function fixture() {
  const gateway: CodingGateway = {
    settings: vi.fn(async () => ({
      id: 'coding' as const,
      defaultModelId: 'fake',
      contextBudget: 32768,
      maxRepairRounds: 2,
    })),
    saveSettings: vi.fn(async (value) => value),
    projects: vi.fn(async () => [project]),
    register: vi.fn(async () => project),
    configure: vi.fn(async () => project),
    removeProject: vi.fn(async () => ({})),
    sessions: vi.fn(async () => [session]),
    create: vi.fn(async () => session),
    update: vi.fn(async () => session),
    remove: vi.fn(async () => ({})),
    snapshot: vi.fn(async (id) => snapshot(id)),
    submit: vi.fn(async () => run),
    cancelActive: vi.fn(async () => ({})),
    cancel: vi.fn(async () => ({})),
    steer: vi.fn(async () => ({})),
    resolve: vi.fn(async () => ({})),
    changes: vi.fn(async () => ({ managed: [], workspace: '', diff: '', scope: '' })),
    files: vi.fn(async () => []),
    read: vi.fn(async () => 'content'),
    change: vi.fn(async () => ({
      id: 'c',
      runId: 'r',
      sessionId: 's',
      path: 'a',
      before: null,
      after: '',
      contentLoaded: true,
      restored: false,
      state: 'written' as const,
    })),
    restore: vi.fn(async () => ({})),
    capabilities: vi.fn(async () => []),
    verifyModel: vi.fn(async () => ({
      id: 'fake',
      status: 'verified' as const,
      verifiedAt: '',
      engineVersion: '',
      parserVersion: '',
      modelFingerprint: '',
      detail: '',
    })),
    verify: vi.fn(async () => run),
  }
  const release = vi.fn(),
    observe = vi.fn(() => release)
  const controller = createCodingController({
    gateway,
    models: ref([]),
    refreshModels: vi.fn(async () => {}),
    pickDirectory: vi.fn(async () => null),
    observe,
  })
  return { controller, gateway, release, observe }
}
describe('Coding workspace', () => {
  it('prepares an unverified model automatically before the first task', async () => {
    const { controller, gateway } = fixture()
    await controller.loadWorkspace('p', 's')
    expect(await controller.send('task')).toBe(true)
    expect(gateway.verifyModel).toHaveBeenCalledOnce()
    expect(gateway.submit).toHaveBeenCalledWith(
      's',
      expect.objectContaining({ mode: 'develop', modelId: 'fake', queue: false }),
    )
  })
  it('keeps the task unsent when automatic model preparation fails', async () => {
    const { controller, gateway } = fixture()
    await controller.loadWorkspace('p', 's')
    vi.mocked(gateway.verifyModel).mockResolvedValueOnce({
      id: 'fake',
      status: 'unverified',
      verifiedAt: null,
      engineVersion: '',
      parserVersion: '',
      modelFingerprint: '',
      detail: '模型未能完成工具调用',
    })
    expect(await controller.send('task')).toBe(false)
    expect(gateway.submit).not.toHaveBeenCalled()
    expect(controller.preparingModel.value).toBe(false)
    expect(controller.error.value).toContain('模型未能完成工具调用')
  })
  it('prepares an expired model identity and retries the same submission once', async () => {
    const { controller, gateway } = fixture()
    await controller.loadWorkspace('p', 's')
    await controller.verifyModel()
    vi.mocked(gateway.submit).mockRejectedValueOnce(
      new RuntimeError('reverify', 'MODEL_TOOLS_UNVERIFIED'),
    )
    expect(await controller.send('task')).toBe(true)
    expect(gateway.verifyModel).toHaveBeenCalledTimes(2)
    const calls = vi.mocked(gateway.submit).mock.calls
    expect(calls).toHaveLength(2)
    expect(calls[0]).toEqual(calls[1])
    expect(controller.modelReady.value).toBe(true)
    expect(controller.error.value).toBeNull()
  })
  it('switching sessions and disposing observation never cancels a task', async () => {
    const { controller, gateway, release } = fixture()
    await controller.loadWorkspace('p', 's')
    controller.snapshot.value = { ...snapshot(), activeRun: run }
    await controller.openSession('other')
    controller.dispose()
    expect(release).toHaveBeenCalledTimes(2)
    expect(gateway.cancel).not.toHaveBeenCalled()
  })
  it('keeps queue submission separate from steering and approval', async () => {
    const { controller, gateway } = fixture()
    await controller.loadWorkspace('p', 's')
    await controller.verifyModel()
    controller.snapshot.value = { ...snapshot(), activeRun: run }
    expect(await controller.send('next', true)).toBe(true)
    expect(gateway.submit).toHaveBeenCalledWith(
      's',
      expect.objectContaining({ queue: true, text: 'next' }),
    )
    expect(gateway.steer).not.toHaveBeenCalled()
    controller.snapshot.value = { ...snapshot(), activeRun: run }
    await controller.steer('additional constraint')
    expect(gateway.steer).toHaveBeenCalledWith('r', 'additional constraint')
    await controller.resolve('a', false)
    expect(gateway.resolve).toHaveBeenCalledWith('a', false)
  })
  it('a slow previous-session snapshot cannot replace the selected session', async () => {
    const { controller, gateway } = fixture()
    let finish: ((value: CodingSnapshot) => void) | undefined
    vi.mocked(gateway.snapshot).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const first = controller.openSession('first')
    await controller.openSession('second')
    finish?.(snapshot('first'))
    await first
    expect(controller.snapshot.value?.session.id).toBe('second')
  })
  it('Coding failure stays within its own error state and reconnect can recover', async () => {
    const { controller, gateway } = fixture()
    vi.mocked(gateway.projects).mockRejectedValueOnce(new Error('host unavailable'))
    await controller.loadWorkspace()
    expect(controller.error.value).toBe('host unavailable')
    await controller.loadWorkspace('p', 's')
    expect(controller.error.value).toBeNull()
  })
})
