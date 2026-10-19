import type { Project, Run } from '../domain/types.js'
import type { RepositoryPort, RunPorts, ToolContext } from './ports.js'
import type { Approvals } from './approvals.js'
interface PolicyInput {
  repo: RepositoryPort
  ports: RunPorts
  run: Run
  project: Project
  abort: AbortController
  approvals: Approvals
  update(patch: Partial<Run>): void
  command: ToolContext['command']
}
export class RunPolicy {
  private calls = 0
  private seen = new Set<string>()
  constructor(private input: PolicyInput) {}
  context(): ToolContext {
    const { project, run, ports, command, update } = this.input
    return {
      root: project.path,
      mode: run.mode,
      workspace: ports.workspace(project.path, run),
      command,
      tick: (id, name) => this.tick(id, name),
      authorizeWrite: (id, path, content, expected) =>
        this.authorizeWrite(id, path, content, expected),
      changed: () => update({ verification: 'not_run', fingerprint: null }),
    }
  }
  private tick(id: string, name: string): void {
    const { run, repo, abort, update } = this.input
    if (abort.signal.aborted) throw new Error('CANCELLED')
    if (this.seen.has(id)) throw new Error('DUPLICATE_TOOL_ID')
    this.seen.add(id)
    if (++this.calls > 48) {
      abort.abort()
      throw new Error('TOOL_BUDGET_EXCEEDED')
    }
    update({
      phase: ['write', 'edit'].includes(name)
        ? 'editing'
        : name === 'run_command'
          ? 'executing'
          : 'exploring',
    })
    repo.append(run.sessionId, run.id, 'tool.started', name, { toolCallId: id })
  }
  private async authorizeWrite(
    id: string,
    path: string,
    content: string,
    expectedHash: string | null,
  ): Promise<void> {
    if (
      !/(?:^|\/)(?:tests?|__tests__)(?:\/|$)|(?:^|\/)test_[^/]+|\.(?:test|spec)\.[^/]+$|(?:^|\/)(?:package\.json|pyproject\.toml|.*lock|[^/]*config[^/]*)$/.test(
        path,
      )
    )
      return
    const { run, project, approvals, abort, update } = this.input
    update({ status: 'awaiting_approval' })
    const allowed = await approvals.request(
      {
        runId: run.id,
        sessionId: run.sessionId,
        toolCallId: id,
        action: 'file_write',
        parameters: { path, content, expectedHash },
        command: `修改测试或验证配置：${path}`,
        cwd: project.path,
      },
      abort.signal,
    )
    if (abort.signal.aborted) throw new Error('CANCELLED')
    update({ status: 'running' })
    if (!allowed) throw new Error('APPROVAL_DENIED')
  }
}
