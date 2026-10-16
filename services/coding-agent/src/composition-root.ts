import { projectWorkspace } from './adapters/project-workspace.js'
import { Repository } from './adapters/repository.js'
import { Commands } from './adapters/commands.js'
import { fingerprint, git, Workspace } from './adapters/workspace.js'
import { openPi } from './adapters/pi-session.js'
import { Runs } from './application/runs.js'
import { CodingService } from './application/service.js'
export function createCodingService(
  repo: Repository,
  processEvent?: (pid: number, state: 'start' | 'end') => void,
): CodingService {
  const runs = new Runs(repo, {
    commands: new Commands(processEvent),
    fingerprint,
    gitStatus: (root) => git(root, 'status'),
    workspace: (root, run) => new Workspace(repo, root, run),
    open: openPi,
  })
  return new CodingService(repo, runs, projectWorkspace(repo))
}
