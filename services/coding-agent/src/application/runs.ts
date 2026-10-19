import { verificationStatus } from '../domain/verification.js'
import { RunPolicy } from './run-policy.js'
import type { PiSession, Provider, RepositoryPort, RunPorts } from './ports.js'
import { checkModel } from './model-result.js'
import { randomUUID } from 'node:crypto'
import {
  terminal,
  nextStatus,
  type Run,
  type Mode,
  type Project,
  type Session,
} from '../domain/types.js'
import { defaultSettings } from '../domain/settings.js'
import { Approvals } from './approvals.js'
interface Submission {
  sessionId: string
  submissionId: string
  text: string
  mode: Mode
  provider: Provider
  probe?: boolean
  queue?: boolean
  verifyOnly?: boolean
}
export class Runs {
  private queue: { id: string; input: Submission }[] = []
  private current:
    | { id: string; abort: AbortController; pi?: PiSession; task: Promise<void> }
    | undefined
  private approvals: Approvals
  constructor(
    private repo: RepositoryPort,
    private ports: RunPorts,
  ) {
    this.approvals = new Approvals(repo)
  }
  async submit(input: Submission): Promise<Run> {
    const previous = this.repo.findSubmission(input.sessionId, input.submissionId)
    if (previous) {
      if (
        previous.text !== input.text ||
        previous.modelId !== input.provider.modelId ||
        previous.mode !== input.mode
      )
        throw new Error('IDEMPOTENCY_CONFLICT')
      return previous
    }
    if ((this.current || this.repo.active()) && !input.queue) throw new Error('CODING_BUSY')
    if (input.queue && this.queue.length >= 1) throw new Error('CODING_QUEUE_FULL')
    const session = this.repo.get('session', input.sessionId)
    if (session.archived) throw new Error('SESSION_ARCHIVED')
    const project = this.repo.get('project', session.projectId)
    const run: Run = {
      id: randomUUID(),
      sessionId: session.id,
      submissionId: input.submissionId,
      text: input.text,
      modelId: input.provider.modelId,
      mode: input.mode,
      status: this.current ? 'queued' : 'starting',
      phase: 'exploring',
      verification: 'not_run',
      verificationCommands: input.probe || input.verifyOnly ? [...project.commands] : [],
      error: null,
      createdAt: new Date().toISOString(),
      baseline: '',
      fingerprint: null,
      maxRepairRounds: (this.repo.find('settings', 'coding') ?? defaultSettings).maxRepairRounds,
    }
    // Reservation occurs before the first asynchronous execution boundary.
    if (this.current && !input.queue) throw new Error('CODING_BUSY')
    this.repo.save('run', run, 'run.started', input.text)
    if (this.current) this.queue.push({ id: run.id, input })
    else this.start(run.id, input)
    return run
  }
  private start(id: string, input: Submission): void {
    const abort = new AbortController()
    const task = Promise.resolve().then(() =>
      this.execute(id, input.provider, abort, input.probe === true, input.verifyOnly === true),
    )
    this.current = { id, abort, task }
  }
  private update(id: string, patch: Partial<Run>): Run {
    const previous = this.repo.get('run', id)
    const status = patch.status ? nextStatus(previous.status, patch.status) : previous.status
    return this.repo.save('run', { ...previous, ...patch, status }, 'run.updated')
  }
  private async execute(
    id: string,
    provider: Provider,
    abort: AbortController,
    probe: boolean,
    verifyOnly: boolean,
  ): Promise<void> {
    const run = this.repo.get('run', id),
      session = this.repo.get('session', run.sessionId),
      project = this.repo.get('project', session.projectId)
    let opened: Awaited<ReturnType<RunPorts['open']>> | undefined
    const timer = setTimeout(() => abort.abort(), 20 * 60 * 1000)
    try {
      this.update(id, {
        status: 'starting',
        baseline: project.git ? await this.ports.gitStatus(project.path) : '',
      })
      opened = await this.prepare({ run, project, session, provider, abort, probe })
      const pi = opened.session
      if (this.current?.id === id) this.current.pi = pi
      const stop = (): void => {
        void pi.abort()
      }
      abort.signal.addEventListener('abort', stop, { once: true })
      if (abort.signal.aborted) throw new Error('CANCELLED')
      pi.subscribe((event) => this.repo.append(session.id, id, event.type, event.text, event.data))
      this.update(id, { status: 'running' })
      await this.promptAndVerify({ pi, run, project, abort, probe, verifyOnly })
      await this.finalize(run, project.path)
      abort.signal.removeEventListener('abort', stop)
    } catch (error) {
      const cancelled = abort.signal.aborted || this.repo.get('run', id).status === 'cancelling'
      this.update(id, {
        status: cancelled ? 'cancelled' : 'failed',
        error: cancelled
          ? 'CANCELLED'
          : error instanceof Error
            ? error.message.slice(0, 200)
            : 'CODING_FAILED',
      })
    } finally {
      clearTimeout(timer)
      this.approvals.denyRun(id)
      if (opened) {
        this.repo.save('session', {
          ...this.repo.get('session', session.id),
          piPath: opened.path() ?? null,
        })
        opened.session.dispose()
      }
      if (this.current?.id === id) this.current = undefined
      const queued = this.queue.shift()
      if (queued) this.start(queued.id, queued.input)
    }
  }
  private async prepare(input: {
    run: Run
    project: Project
    session: Session
    provider: Provider
    abort: AbortController
    probe: boolean
  }): Promise<Awaited<ReturnType<RunPorts['open']>>> {
    const { run, project, session, provider, abort, probe } = input,
      id = run.id
    const context = new RunPolicy({
      repo: this.repo,
      ports: this.ports,
      run,
      project,
      abort,
      approvals: this.approvals,
      update: (patch) => {
        this.update(id, patch)
      },
      command: (callId, command, signal) =>
        this.command(id, callId, command, signal ?? abort.signal, probe),
    }).context()
    return this.ports.open({
      directory: this.repo.directory,
      project,
      session,
      provider,
      context,
    })
  }
  private async promptAndVerify(input: {
    pi: PiSession
    run: Run
    project: Project
    abort: AbortController
    probe: boolean
    verifyOnly: boolean
  }): Promise<void> {
    const { pi, run, abort, probe, verifyOnly } = input
    const commands = run.verificationCommands ?? []
    const id = run.id
    if (!verifyOnly) {
      await pi.prompt(run.text)
      checkModel(pi)
    }
    for (
      let repair = 0;
      (probe || verifyOnly) && !abort.signal.aborted && commands.length && run.mode === 'develop';
      repair++
    ) {
      let passed = true
      for (const command of commands) {
        const result = await this.command(
          id,
          `verify-${randomUUID()}`,
          command,
          abort.signal,
          probe,
          true,
        )
        if (result.exitCode !== 0) passed = false
      }
      if (passed || repair >= run.maxRepairRounds || verifyOnly) break
      await pi.prompt(
        'Project verification failed. Repair without changing tests or verification configuration. Evidence:\n' +
          JSON.stringify(this.repo.checksForRun(id).slice(-commands.length)),
      )
    }
    if (abort.signal.aborted) throw new Error('CANCELLED')
    if (!verifyOnly) checkModel(pi)
  }
  private async finalize(run: Run, root: string): Promise<void> {
    const id = run.id
    const currentFingerprint = await this.ports.fingerprint(root)
    const checks = this.repo.checksForRun(id)
    const verification = verificationStatus(run, checks, currentFingerprint)
    this.update(id, {
      status: 'completed',
      phase: 'reviewing',
      verification,
      fingerprint: currentFingerprint,
    })
  }
  private async command(
    id: string,
    callId: string,
    command: string,
    signal: AbortSignal,
    probe: boolean,
    verification = probe,
  ) {
    if (probe && command !== "/usr/bin/grep -qx 'after' probe.txt")
      throw new Error('PROBE_COMMAND_NOT_ALLOWED')
    if (/\bgit\s+(?:[^;&|]*\s)?(?:commit|push|reset|clean|rebase)\b/.test(command))
      throw new Error('GIT_MUTATION_DISABLED')
    const run = this.repo.get('run', id),
      session = this.repo.get('session', run.sessionId),
      project = this.repo.get('project', session.projectId)
    if (run.mode === 'analyze') throw new Error('READ_ONLY_MODE')
    if (signal.aborted) throw new Error('CANCELLED')
    this.update(id, {
      status: 'awaiting_approval',
      phase: verification ? 'verifying' : 'executing',
    })
    const allowed = await this.approvals.request(
      {
        runId: id,
        sessionId: session.id,
        toolCallId: callId,
        action: 'command',
        parameters: { command },
        command,
        cwd: project.path,
      },
      signal,
      probe && command === "/usr/bin/grep -qx 'after' probe.txt",
    )
    if (signal.aborted) throw new Error('CANCELLED')
    this.update(id, { status: 'running' })
    if (!allowed) throw new Error('APPROVAL_DENIED')
    const before = await this.ports.fingerprint(project.path)
    const result = await this.ports.commands.run(command, project.path, signal)
    const after = await this.ports.fingerprint(project.path)
    const check = {
      id: randomUUID(),
      purpose: verification ? ('verification' as const) : ('command' as const),
      sessionId: session.id,
      runId: id,
      command,
      ...result,
      fingerprint: before,
      stale: before !== after,
    }
    this.repo.save('verification', check, 'verification.finished', result.output)
    this.update(id, {
      verification: verificationStatus(run, this.repo.checksForRun(id), after),
      fingerprint: before === after ? after : null,
    })
    return result
  }
  resolve(id: string, allowed: boolean): void {
    this.approvals.resolve(id, allowed)
  }
  async cancel(id: string): Promise<Run> {
    const run = this.repo.get('run', id)
    if (terminal(run.status)) return run
    const queued = this.queue.findIndex((item) => item.id === id)
    if (queued >= 0) {
      this.queue.splice(queued, 1)
      return this.update(id, { status: 'cancelled' })
    }
    if (run.status !== 'cancelling') this.update(id, { status: 'cancelling' })
    if (this.current?.id === id) {
      this.current.abort.abort()
      await this.current.task
    }
    return this.repo.get('run', id)
  }
  async steer(id: string, text: string): Promise<void> {
    if (
      this.current?.id !== id ||
      !this.current.pi ||
      this.repo.get('run', id).status === 'cancelling'
    )
      throw new Error('RUN_NOT_READY')
    await this.current.pi.steer(text)
    this.repo.append(this.repo.get('run', id).sessionId, id, 'user.steering', text)
  }
  async wait(id: string): Promise<void> {
    if (this.current?.id === id) await this.current.task
  }
  async close(): Promise<void> {
    for (const queued of [...this.queue]) await this.cancel(queued.id)
    if (this.current) await this.cancel(this.current.id)
    this.ports.commands.close()
  }
}
