import type { Entities, Event, Project, Run, Session } from '../domain/types.js'
export interface RepositoryPort {
  readonly directory: string
  find<K extends keyof Entities>(kind: K, id: string): Entities[K] | undefined
  listSessions(projectId: string, before?: string, limit?: number): Entities['session'][]
  listRuns(sessionId: string, before?: string, limit?: number): Run[]
  listApprovals(sessionId: string): Entities['approval'][]
  checksForRun(runId: string): Entities['verification'][]
  listChecks(sessionId: string): Entities['verification'][]
  changesForRun(runId: string): Entities['change'][]
  changeHeaders(
    sessionId: string,
    before?: string,
    limit?: number,
  ): (Entities['change'] & { contentLoaded: false })[]
  changeDetail(id: string): Entities['change'] & { contentLoaded: true }
  pendingApprovals(runId: string): Entities['approval'][]
  findSubmission(sessionId: string, submissionId: string): Run | undefined
  findProject(path: string): Project | undefined
  get<K extends keyof Entities>(kind: K, id: string): Entities[K]
  list<K extends keyof Entities>(kind: K): Entities[K][]
  save<K extends keyof Entities>(
    kind: K,
    item: Entities[K],
    type?: string,
    text?: string,
  ): Entities[K]
  append(sessionId: string, runId: string | null, type: string, text: string, data?: unknown): void
  events(after: number, sessionId?: string): Event[]
  waitEvents(after: number): Promise<{ events: Event[]; watermark: number }>
  watermark(): number
  delete(kind: keyof Entities, id: string): void
  deleteSession(id: string): void
  active(sessionId?: string): Run | undefined
}
export interface Provider {
  modelId: string
  baseUrl: string
  token: string
  contextWindow: number
  fingerprint: string
  engineVersion: string
}
export interface PiSession {
  prompt(text: string): Promise<void>
  steer(text: string): Promise<unknown>
  abort(): Promise<void>
  dispose(): void
  lastStopReason(): string | undefined
  lastErrorCode(): string | undefined
  subscribe(callback: (event: { type: string; text: string; data: unknown }) => void): void
}
export interface WorkspacePort {
  write(path: string, content: string, expected: string | null): Promise<string>
}
export interface CommandResult {
  exitCode: number | null
  output: string
  truncated: boolean
}
export interface CommandPort {
  run(command: string, root: string, signal?: AbortSignal): Promise<CommandResult>
  close(): void
}
export interface ToolContext {
  root: string
  mode: Run['mode']
  workspace: WorkspacePort
  command(id: string, command: string, signal?: AbortSignal): Promise<unknown>
  tick(id: string, name: string): void
  authorizeWrite(
    id: string,
    path: string,
    content: string,
    expectedHash: string | null,
  ): Promise<void>
  changed(path: string): void
}
export interface RunPorts {
  commands: CommandPort
  fingerprint(root: string): Promise<string>
  gitStatus(root: string): Promise<string>
  workspace(root: string, run: Run): WorkspacePort
  open(input: {
    directory: string
    project: Project
    session: Session
    provider: Provider
    context: ToolContext
  }): Promise<{ session: PiSession; path(): string | undefined }>
}
export interface ProjectPort {
  register(path: string): Promise<Project>
  read(root: string, path: string): Promise<{ content: string; sha256: string }>
  files(root: string): Promise<string[]>
  fingerprint(root: string): Promise<string>
  git(root: string, action: 'status' | 'diff'): Promise<string>
  restore(root: string, change: Entities['change'], run: Run): Promise<void>
  createProbe(): Promise<string>
  writeProbe(root: string): Promise<void>
  report(sessionId: string, report: unknown): Promise<void>
  removeProbe(root: string): Promise<void>
}
