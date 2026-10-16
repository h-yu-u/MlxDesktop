import { buildSnapshot } from './snapshot.js'
import { localProvider } from './local-provider.js'
import { defaultSettings, validateSettings } from '../domain/settings.js'
import { randomUUID } from 'node:crypto'
import type { Provider, RepositoryPort, ProjectPort } from './ports.js'
import { object, string, mode, terminal, type Capability } from '../domain/types.js'
import { Runs } from './runs.js'
export class CodingService {
  constructor(
    readonly repo: RepositoryPort,
    private runs: Runs,
    private projects: ProjectPort,
  ) {}
  private handlers: Record<string, (p: Record<string, unknown>) => Promise<unknown>> = {
    'settings.get': async (p) => {
      return this.repo.list('settings')[0] ?? defaultSettings
    },
    'settings.update': async (p) => {
      {
        if (this.repo.active()) throw new Error('CODING_BUSY')
        return this.repo.save('settings', validateSettings(p))
      }
    },
    'projects.list': async (p) => {
      return this.repo.list('project')
    },
    'projects.register': async (p) => {
      {
        const project = await this.projects.register(string(p.path))
        return (
          this.repo.list('project').find((item) => item.path === project.path) ??
          this.repo.save('project', project)
        )
      }
    },
    'projects.get': async (p) => {
      return this.repo.get('project', string(p.id))
    },
    'projects.update': async (p) => {
      {
        const project = this.repo.get('project', string(p.id))
        if (this.repo.active()) throw new Error('CODING_BUSY')
        const commands = p.commands
        if (!Array.isArray(commands) || commands.length > 8) throw new Error('INVALID_COMMANDS')
        return this.repo.save('project', {
          ...project,
          commands: commands.map((value) => string(value, 4096)),
        })
      }
    },
    'projects.remove': async (p) => {
      {
        const id = string(p.id)
        if (this.repo.list('session').some((item) => item.projectId === id))
          throw new Error('PROJECT_HAS_SESSIONS')
        this.repo.delete('project', id)
        return { removed: true }
      }
    },
    'sessions.list': async (p) => {
      return this.repo.list('session').filter((item) => item.projectId === string(p.projectId))
    },
    'sessions.create': async (p) => {
      {
        const project = this.repo.get('project', string(p.projectId))
        return this.repo.save('session', {
          id: randomUUID(),
          projectId: project.id,
          title: typeof p.title === 'string' ? string(p.title, 160) : '新开发会话',
          pinned: false,
          archived: false,
          piPath: null,
        })
      }
    },
    'sessions.get': async (p) => {
      return this.repo.get('session', string(p.id))
    },
    'sessions.update': async (p) => {
      {
        const session = this.repo.get('session', string(p.id))
        if (
          this.repo
            .list('run')
            .some((run) => run.sessionId === session.id && !terminal(run.status)) &&
          p.archived === true
        )
          throw new Error('SESSION_IN_USE')
        return this.repo.save('session', {
          ...session,
          title: p.title === undefined ? session.title : string(p.title, 160),
          pinned: typeof p.pinned === 'boolean' ? p.pinned : session.pinned,
          archived: typeof p.archived === 'boolean' ? p.archived : session.archived,
        })
      }
    },
    'sessions.remove': async (p) => {
      {
        const id = string(p.id)
        if (this.repo.list('run').some((run) => run.sessionId === id && !terminal(run.status)))
          throw new Error('SESSION_IN_USE')
        this.repo.get('session', id)
        this.repo.deleteSession(id)
        return { removed: true }
      }
    },
    'sessions.snapshot': async (p) =>
      buildSnapshot(this.repo, this.projects.fingerprint, string(p.id)),
    'sessions.files': async (p) => {
      return { files: await this.projects.files(this.projectPath(string(p.id))) }
    },
    'sessions.read': async (p) =>
      this.projects.read(this.projectPath(string(p.id)), string(p.path)),
    'sessions.changes': async (p) => {
      {
        const id = string(p.id),
          root = this.projectPath(id),
          project = this.repo.get('project', this.repo.get('session', id).projectId)
        return {
          managed: this.repo
            .list('change')
            .filter((item) => item.sessionId === id)
            .map((item) => ({
              ...item,
              before: item.before === null ? null : '',
              after: '',
              contentLoaded: false,
            })),
          workspace: project.git ? await this.projects.git(root, 'status') : '',
          diff: p.diff === true && project.git ? await this.projects.git(root, 'diff') : '',
          scope: '受管修改可归因；命令与外部编辑仅展示为工作区变化',
        }
      }
    },
    'changes.get': async (p) => ({ ...this.repo.get('change', string(p.id)), contentLoaded: true }),
    'changes.restore': async (p) => {
      {
        if (this.repo.active()) throw new Error('CODING_BUSY')
        const change = this.repo.get('change', string(p.id)),
          root = this.projectPath(change.sessionId)
        if (change.restored) return change
        const run = this.repo.get('run', change.runId)
        await this.projects.restore(root, change, run)
        this.repo.save(
          'run',
          { ...run, verification: 'not_run', fingerprint: null },
          'verification.invalidated',
        )
        return this.repo.save('change', { ...change, restored: true }, 'file.restored', change.path)
      }
    },
    'runs.submit': async (p) => {
      {
        const provider = localProvider(p)
        provider.contextWindow = Math.min(
          provider.contextWindow,
          (this.repo.list('settings')[0] ?? defaultSettings).contextBudget,
        )
        if (
          !this.repo
            .list('capability')
            .some(
              (item) =>
                item.id === provider.modelId &&
                item.status === 'verified' &&
                item.modelFingerprint === provider.fingerprint,
            )
        )
          throw new Error('MODEL_TOOLS_UNVERIFIED')
        return this.runs.submit({
          sessionId: string(p.sessionId),
          submissionId: string(p.submissionId),
          text: string(p.text, 32000),
          mode: mode(p.mode),
          provider,
          queue: p.queue === true,
        })
      }
    },
    'sessions.verify': async (p) => {
      {
        const provider = localProvider(p),
          id = string(p.sessionId)
        const project = this.repo.get('project', this.repo.get('session', id).projectId)
        if (!project.commands.length) throw new Error('VERIFICATION_COMMANDS_REQUIRED')
        return this.runs.submit({
          sessionId: id,
          submissionId: string(p.submissionId),
          text: '运行项目配置的验证命令',
          mode: 'develop',
          provider,
          verifyOnly: true,
        })
      }
    },
    'runs.cancel-active': async () => {
      const active = this.repo.active()
      return active ? this.runs.cancel(active.id) : { cancelled: false }
    },
    'runs.cancel': async (p) => {
      return this.runs.cancel(string(p.id))
    },
    'runs.steer': async (p) => {
      await this.runs.steer(string(p.id), string(p.text, 16000))
      return { accepted: true }
    },
    'approvals.resolve': async (p) => {
      {
        if (typeof p.allowed !== 'boolean') throw new Error('INVALID_APPROVAL')
        this.runs.resolve(string(p.id), p.allowed)
        return { resolved: true }
      }
    },
    'events.list': async (p) => {
      return {
        events: this.repo.events(typeof p.after === 'number' ? p.after : 0),
        watermark: this.repo.watermark(),
      }
    },
    'capabilities.list': async (p) => {
      return this.repo.list('capability')
    },
    'capabilities.verify': async (p) => {
      return this.probe(localProvider(p))
    },
    shutdown: async (p) => {
      await this.close()
      return { closed: true }
    },
  }
  async dispatch(method: string, raw: unknown): Promise<unknown> {
    const handler = this.handlers[method]
    if (!handler) throw new Error('UNKNOWN_METHOD')
    return handler(object(raw))
  }

  private projectPath(id: string): string {
    return this.repo.get('project', this.repo.get('session', id).projectId).path
  }
  private async probe(provider: Provider): Promise<Capability> {
    if (this.repo.active()) throw new Error('CODING_BUSY')
    const directory = await this.projects.createProbe()
    const project = this.repo.save('project', {
      ...(await this.projects.register(directory)),
      commands: ["/usr/bin/grep -qx 'after' probe.txt"],
    })
    await this.projects.writeProbe(directory)
    const session = this.repo.save('session', {
      id: randomUUID(),
      projectId: project.id,
      title: '工具协议验证',
      pinned: false,
      archived: false,
      piPath: null,
    })
    try {
      const run = await this.runs.submit({
        sessionId: session.id,
        submissionId: randomUUID(),
        text: "Coding capability probe: first request both list and read probe.txt in a single response, then replace its entire content with after followed by a newline using the returned hash, run exactly /usr/bin/grep -qx 'after' probe.txt. If a check fails read the file and repair it, then run the same check. Do not change any other files. Finish with a short summary.",
        mode: 'develop',
        provider,
        probe: true,
      })
      await this.runs.wait(run.id)
      const final = this.repo.get('run', run.id),
        events = this.repo.events(0, session.id)
      const passed =
        final.status === 'completed' &&
        final.verification === 'passed' &&
        (await this.projects.read(directory, 'probe.txt')).content.trimEnd() === 'after' &&
        events.some((event) => event.type === 'tool.started' && event.text === 'read') &&
        this.repo
          .list('change')
          .some((change) => change.runId === run.id && change.state === 'written')
      const result: Capability = {
        id: provider.modelId,
        status: passed ? 'verified' : 'unverified',
        verifiedAt: passed ? new Date().toISOString() : null,
        engineVersion: provider.engineVersion,
        modelFingerprint: provider.fingerprint,
        parserVersion: 'mlx-tools-v2',
        detail: passed
          ? '已验证 Pi → MLX 结构化推理 → read/write → 命令退出码 → 多轮工具结果。'
          : `工具闭环未通过：${final.error ?? final.verification}`,
      }
      await this.projects.report(session.id, {
        capability: result,
        run: final,
        events,
        verifications: this.repo.list('verification').filter((item) => item.runId === run.id),
      })
      return this.repo.save('capability', result)
    } finally {
      if (!this.repo.active() || terminal(this.repo.get('run', this.repo.active()!.id).status)) {
        this.repo.deleteSession(session.id)
        this.repo.delete('project', project.id)
        await this.projects.removeProbe(directory)
      }
    }
  }
  async close(): Promise<void> {
    await this.runs.close()
  }
}
