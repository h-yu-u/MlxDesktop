import type { RuntimeEvent } from './types'

export class RuntimeEventStreamParser {
  private buffer = ''

  push(chunk: string): RuntimeEvent[] {
    this.buffer = `${this.buffer}${chunk}`.replace(/\r\n/g, '\n')
    const events: RuntimeEvent[] = []
    let boundary = this.buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const frame = this.buffer.slice(0, boundary)
      this.buffer = this.buffer.slice(boundary + 2)
      const event = parseFrame(frame)
      if (event) events.push(event)
      boundary = this.buffer.indexOf('\n\n')
    }
    return events
  }
}

function parseFrame(frame: string): RuntimeEvent | undefined {
  const data = frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')
  if (!data) return undefined
  try {
    const value: unknown = JSON.parse(data)
    return isRuntimeEvent(value) ? value : undefined
  } catch {
    return undefined
  }
}

function isRuntimeEvent(value: unknown): value is RuntimeEvent {
  if (typeof value !== 'object' || value === null) return false
  const event = value as Record<string, unknown>
  return typeof event.seq === 'number'
    && typeof event.type === 'string'
    && typeof event.payload === 'object'
    && event.payload !== null
}
