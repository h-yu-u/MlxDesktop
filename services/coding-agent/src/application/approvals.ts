import { randomUUID } from 'node:crypto'
import type { Approval } from '../domain/types.js'
import { terminal } from '../domain/types.js'
import type { RepositoryPort } from './ports.js'
export class Approvals {
  private pending = new Map<string, (allowed: boolean) => void>()
  constructor(private repo: RepositoryPort) {}
  async request(
    input: Omit<Approval, 'id' | 'expiresAt' | 'status' | 'policyVersion'>,
    signal: AbortSignal,
    trusted = false,
  ): Promise<boolean> {
    if (signal.aborted) throw new Error('CANCELLED')
    const approval: Approval = {
      ...input,
      id: randomUUID(),
      expiresAt: Date.now() + 300000,
      status: 'pending',
      policyVersion: 1,
    }
    this.repo.save('approval', approval, 'approval.requested', input.command)
    if (trusted) {
      this.repo.save('approval', { ...approval, status: 'allowed' })
      return true
    }
    return new Promise<boolean>((resolve) => {
      const timer = setTimeout(() => this.resolve(approval.id, false), 300000)
      const stop = (): void => this.resolve(approval.id, false)
      this.pending.set(approval.id, (allowed) => {
        clearTimeout(timer)
        signal.removeEventListener('abort', stop)
        resolve(allowed)
      })
      signal.addEventListener('abort', stop, { once: true })
      if (signal.aborted) this.resolve(approval.id, false)
    })
  }
  resolve(id: string, allowed: boolean): void {
    const approval = this.repo.get('approval', id)
    if (approval.status !== 'pending') throw new Error('APPROVAL_ALREADY_RESOLVED')
    const valid =
      approval.expiresAt > Date.now() && !terminal(this.repo.get('run', approval.runId).status)
    this.repo.save(
      'approval',
      { ...approval, status: allowed && valid ? 'allowed' : 'denied' },
      'approval.resolved',
    )
    this.pending.get(id)?.(allowed && valid)
    this.pending.delete(id)
  }
  denyRun(runId: string): void {
    for (const approval of this.repo.list('approval'))
      if (approval.runId === runId && approval.status === 'pending')
        this.resolve(approval.id, false)
  }
}
