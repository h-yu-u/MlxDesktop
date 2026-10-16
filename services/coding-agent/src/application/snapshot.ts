import type { RepositoryPort } from './ports.js'
export async function buildSnapshot(
  repo: RepositoryPort,
  fingerprint: (root: string) => Promise<string>,
  id: string,
) {
  const session = repo.get('session', id)
  const project = repo.get('project', session.projectId)
  const version = repo.active() ? null : await fingerprint(project.path)
  const checks = repo
    .list('verification')
    .filter((item) => item.sessionId === session.id)
    .map((item) => ({ ...item, stale: item.stale || item.fingerprint !== version }))
  return {
    session,
    project,
    runs: repo
      .list('run')
      .filter((item) => item.sessionId === session.id)
      .slice(-50)
      .map((run) =>
        run.verification === 'passed' && run.fingerprint !== version
          ? { ...run, verification: 'partial' as const }
          : run,
      ),
    approvals: repo
      .list('approval')
      .filter((item) => item.sessionId === session.id)
      .slice(-50)
      .map((item) => (item.status === 'pending' ? item : { ...item, parameters: {} })),
    verifications: checks.slice(-20),
    events: repo.events(0, session.id).slice(-100),
    watermark: repo.watermark(),
    activeRun: repo.active() ?? null,
  }
}
