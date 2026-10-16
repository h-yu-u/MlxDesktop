import { DatabaseSync } from 'node:sqlite'
import { mkdirSync, realpathSync } from 'node:fs'
import { join } from 'node:path'
import type { Entities, Event, Run } from '../domain/types.js'

// This is the sole writer of Coding metadata. Pi owns the actual model transcript.
export class Repository {
  private db: DatabaseSync
  constructor(readonly directory: string) {
    mkdirSync(directory, { recursive: true, mode: 0o700 })
    this.directory = realpathSync(directory)
    this.db = new DatabaseSync(join(directory, 'coding.db'))
    this.db
      .exec(`PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS entities (kind TEXT, id TEXT, value TEXT NOT NULL, PRIMARY KEY(kind,id));
      CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, sessionId TEXT, runId TEXT, type TEXT, text TEXT, data TEXT);`)
    for (const run of this.list('run')) {
      if (!['completed', 'failed', 'cancelled', 'interrupted'].includes(run.status)) {
        this.save(
          'run',
          { ...run, status: 'interrupted', error: 'HOST_RESTARTED' },
          'run.interrupted',
          '进程已中断；继续前请重新检查工作区',
        )
      }
    }
    for (const approval of this.list('approval')) {
      if (approval.status === 'pending') this.save('approval', { ...approval, status: 'denied' })
    }
  }
  get<K extends keyof Entities>(kind: K, id: string): Entities[K] {
    const row = this.db.prepare('SELECT value FROM entities WHERE kind=? AND id=?').get(kind, id)
    if (!row || typeof row.value !== 'string') throw new Error(`${kind.toUpperCase()}_NOT_FOUND`)
    return JSON.parse(row.value) as Entities[K]
  }
  list<K extends keyof Entities>(kind: K): Entities[K][] {
    return this.db
      .prepare('SELECT value FROM entities WHERE kind=? ORDER BY rowid')
      .all(kind)
      .map((row) => JSON.parse(String(row.value)) as Entities[K])
  }
  save<K extends keyof Entities>(
    kind: K,
    item: Entities[K],
    type?: string,
    text = '',
  ): Entities[K] {
    this.db.exec('BEGIN IMMEDIATE')
    try {
      this.db
        .prepare(
          'INSERT INTO entities VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET value=excluded.value',
        )
        .run(kind, item.id, JSON.stringify(item))
      if (type && 'sessionId' in item)
        this.append(
          item.sessionId,
          'runId' in item ? item.runId : kind === 'run' ? item.id : null,
          type,
          text,
          eventProjection(kind, item),
        )
      this.db.exec('COMMIT')
    } catch (error) {
      this.db.exec('ROLLBACK')
      throw error
    }
    return item
  }
  append(
    sessionId: string,
    runId: string | null,
    type: string,
    text: string,
    data: unknown = null,
  ): void {
    this.db
      .prepare('INSERT INTO events(sessionId,runId,type,text,data) VALUES(?,?,?,?,?)')
      .run(sessionId, runId, type, text.slice(0, 65536), JSON.stringify(data))
  }
  events(after: number, sessionId?: string): Event[] {
    const rows = sessionId
      ? this.db
          .prepare(
            'SELECT * FROM (SELECT * FROM events WHERE sessionId=? ORDER BY seq DESC LIMIT 300) ORDER BY seq',
          )
          .all(sessionId)
      : this.db.prepare('SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT 50').all(after)
    return rows.map((row) => ({
      seq: Number(row.seq),
      sessionId: String(row.sessionId),
      runId: row.runId === null ? null : String(row.runId),
      type: String(row.type),
      text: String(row.text),
      data: JSON.parse(String(row.data)) as unknown,
    }))
  }
  watermark(): number {
    return Number(
      this.db.prepare("SELECT seq FROM sqlite_sequence WHERE name='events'").get()?.seq ?? 0,
    )
  }
  delete(kind: keyof Entities, id: string): void {
    this.db.prepare('DELETE FROM entities WHERE kind=? AND id=?').run(kind, id)
  }
  deleteSession(id: string): void {
    for (const kind of ['run', 'approval', 'change', 'verification'] as const) {
      for (const item of this.list(kind)) if (item.sessionId === id) this.delete(kind, item.id)
    }
    this.db.prepare('DELETE FROM events WHERE sessionId=?').run(id)
    this.delete('session', id)
  }
  active(): Run | undefined {
    return this.list('run').find(
      (run) => !['completed', 'failed', 'cancelled', 'interrupted'].includes(run.status),
    )
  }
  close(): void {
    this.db.close()
  }
}

function eventProjection<K extends keyof Entities>(kind: K, item: Entities[K]): unknown {
  if (kind === 'run' && 'status' in item)
    return {
      id: item.id,
      status: item.status,
      phase: 'phase' in item ? item.phase : '',
      verification: 'verification' in item ? item.verification : '',
    }
  if (kind === 'approval' && 'command' in item)
    return {
      id: item.id,
      action: 'action' in item ? item.action : '',
      command: item.command,
      status: 'status' in item ? item.status : '',
    }
  if (kind === 'change' && 'path' in item)
    return { id: item.id, path: item.path, state: 'state' in item ? item.state : '' }
  if (kind === 'verification' && 'exitCode' in item)
    return { id: item.id, exitCode: item.exitCode, fingerprint: item.fingerprint }
  return { id: item.id }
}
