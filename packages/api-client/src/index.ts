/** Authenticated transport boundary for the local Runtime. */

export interface RuntimeConnection {
  baseUrl: string
  token: string
  protocolVersion: number
}

export interface RuntimeEvent {
  seq: number
  type: string
  payload: Record<string, unknown>
}

export class RuntimeClient {
  constructor(private readonly connection: RuntimeConnection) {}

  async get(path: string, signal?: AbortSignal): Promise<unknown> {
    return this.request(path, { method: 'GET', signal })
  }

  async post(path: string, body?: unknown, signal?: AbortSignal): Promise<unknown> {
    return this.request(path, {
      method: 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  }

  async uploadImage(file: File): Promise<{ id: string; mimeType: string; originalName: string }> {
    const response = await fetch(
      `${this.connection.baseUrl}/internal/v1/attachments?filename=${encodeURIComponent(file.name)}`,
      { method: 'POST', headers: { Authorization: `Bearer ${this.connection.token}` }, body: file },
    )
    const payload: unknown = await response.json().catch(() => undefined)
    if (!response.ok) throw new Error(readErrorMessage(payload) ?? `图片上传失败 (${response.status})`)
    if (typeof payload !== 'object' || payload === null || typeof (payload as { id?: unknown }).id !== 'string') {
      throw new Error('Runtime 未返回附件 ID')
    }
    const item = payload as { id: string; mimeType?: string; originalName?: string }
    return { id: item.id, mimeType: item.mimeType ?? 'image/*', originalName: item.originalName ?? file.name }
  }

  async downloadDiagnosticBundle(): Promise<Blob> {
    const response = await fetch(
      `${this.connection.baseUrl}/internal/v1/runtime/diagnostics/bundle`,
      { headers: { Authorization: `Bearer ${this.connection.token}` } },
    )
    if (!response.ok) throw new Error(`诊断包下载失败 (${response.status})`)
    return response.blob()
  }

  async patch(path: string, body: unknown): Promise<unknown> {
    return this.request(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  async delete(path: string): Promise<unknown> {
    return this.request(path, { method: 'DELETE' })
  }

  async subscribe(
    onEvent: (event: RuntimeEvent) => void,
    signal: AbortSignal,
    after = 0,
  ): Promise<void> {
    const response = await fetch(`${this.connection.baseUrl}/internal/v1/events?after=${after}`, {
      headers: { Authorization: `Bearer ${this.connection.token}` },
      signal,
    })
    if (!response.ok || !response.body) throw new Error('无法连接 Runtime 事件流')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    try {
      while (!signal.aborted) {
        const { value, done } = await reader.read()
        if (done) return
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''
        for (const frame of frames) {
          const dataLine = frame.split('\n').find((line) => line.startsWith('data:'))
          if (!dataLine) continue
          const parsed: unknown = JSON.parse(dataLine.slice(5).trim())
          if (isRuntimeEvent(parsed)) onEvent(parsed)
        }
      }
    } finally {
      await reader.cancel().catch(() => undefined)
    }
  }

  private async request(path: string, init: RequestInit): Promise<unknown> {
    const response = await fetch(`${this.connection.baseUrl}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${this.connection.token}`,
        ...init.headers,
      },
    })
    const payload: unknown = await response.json().catch(() => undefined)
    if (!response.ok) {
      const message = readErrorMessage(payload) ?? `Runtime 请求失败 (${response.status})`
      throw new Error(message)
    }
    return payload
  }
}

function isRuntimeEvent(value: unknown): value is RuntimeEvent {
  if (typeof value !== 'object' || value === null) return false
  const event = value as Record<string, unknown>
  return typeof event.seq === 'number' && typeof event.type === 'string'
    && typeof event.payload === 'object' && event.payload !== null
}

function readErrorMessage(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const error = (value as Record<string, unknown>).error
  if (typeof error !== 'object' || error === null) return undefined
  const message = (error as Record<string, unknown>).message
  return typeof message === 'string' ? message : undefined
}
