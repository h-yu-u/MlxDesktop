import type { CodingEvent } from '../application/ports'
export type TimelineEntry =
  | { kind: 'message'; event: CodingEvent }
  | { kind: 'activity'; seq: number; runId: string | null; events: CodingEvent[] }
export function timelineEntries(events: readonly CodingEvent[]): TimelineEntry[] {
  const result: TimelineEntry[] = []
  for (const event of events) {
    if (['tool.finished', 'verification.finished'].includes(event.type)) {
      const previous = result.at(-1)
      if (previous?.kind === 'activity' && previous.runId === event.runId)
        previous.events.push(event)
      else result.push({ kind: 'activity', seq: event.seq, runId: event.runId, events: [event] })
    } else if (
      ['run.started', 'user.steering', 'run.interrupted'].includes(event.type) ||
      (event.type === 'assistant.message' && (event.text.trim() || eventError(event.data)))
    )
      result.push({ kind: 'message', event })
  }
  return result
}
export function eventError(data: unknown): string | null {
  return data && typeof data === 'object' && 'error' in data && typeof data.error === 'string'
    ? data.error
    : null
}
export function activityText(event: CodingEvent): string {
  if (event.type === 'verification.finished') return event.text
  if (!event.data || typeof event.data !== 'object' || !('result' in event.data)) return ''
  const result = event.data.result
  if (
    !result ||
    typeof result !== 'object' ||
    !('preview' in result) ||
    typeof result.preview !== 'string'
  )
    return ''
  try {
    const envelope: unknown = JSON.parse(result.preview)
    if (
      !envelope ||
      typeof envelope !== 'object' ||
      !('content' in envelope) ||
      !Array.isArray(envelope.content)
    )
      return result.preview
    return envelope.content
      .filter(
        (block: unknown): block is { type: string; text: string } =>
          !!block && typeof block === 'object' && 'text' in block && typeof block.text === 'string',
      )
      .map((block) => block.text)
      .join('\n')
  } catch {
    return result.preview
  }
}
export function activityLabel(name: string): string {
  return (
    (
      {
        list: '浏览项目',
        read: '读取文件',
        search: '搜索代码',
        write: '保存文件',
        edit: '修改代码',
        git_status: '查看 Git 状态',
        run_command: '运行命令',
      } as Record<string, string>
    )[name] ?? name
  )
}
