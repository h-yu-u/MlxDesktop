/** Authenticated transport boundary for the local Runtime. */

import { RuntimeEventStreamParser } from './sse'
import type { RuntimeConnection, RuntimeEvent } from './types'

export type { RuntimeConnection, RuntimeEvent } from './types'
export type { components } from './generated-schema'

export interface RuntimeClientOptions {
  onConnectionInvalid?: () => void
}

export class RuntimeClient {
  constructor(
    private readonly connection: RuntimeConnection,
    private readonly options: RuntimeClientOptions = {},
  ) {}

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

  async uploadImage(file: File): Promise<{ id: string; mimeType: string; originalName: string }> {
    const response = await this.fetch(
      `/internal/v1/attachments?filename=${encodeURIComponent(file.name)}`,
      { method: 'POST', body: file },
    )
    const payload: unknown = await response.json().catch(() => undefined)
    if (!response.ok) {
      throw new Error(readErrorMessage(payload) ?? `图片上传失败 (${response.status})`)
    }
    if (typeof payload !== 'object' || payload === null
      || typeof (payload as { id?: unknown }).id !== 'string') {
      throw new Error('Runtime 未返回附件 ID')
    }
    const item = payload as { id: string; mimeType?: string; originalName?: string }
    return {
      id: item.id,
      mimeType: item.mimeType ?? 'image/*',
      originalName: item.originalName ?? file.name,
    }
  }

  async downloadImageArtifact(id: string): Promise<Blob> {
    const response = await this.fetch(`/internal/v1/image-artifacts/${encodeURIComponent(id)}/content`)
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => undefined)
      throw new Error(readErrorMessage(payload) ?? `作品读取失败 (${response.status})`)
    }
    return response.blob()
  }

  async downloadDiagnosticBundle(): Promise<Blob> {
    const response = await this.fetch('/internal/v1/runtime/diagnostics/bundle')
    if (!response.ok) throw new Error(`诊断包下载失败 (${response.status})`)
    return response.blob()
  }

  async subscribe(
    onEvent: (event: RuntimeEvent) => void,
    signal: AbortSignal,
    after = 0,
  ): Promise<void> {
    const response = await this.fetch(`/internal/v1/events?after=${after}`, { signal })
    if (!response.ok || !response.body) throw new Error('无法连接 Runtime 事件流')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const parser = new RuntimeEventStreamParser()
    try {
      while (!signal.aborted) {
        const { value, done } = await reader.read()
        if (done) return
        for (const event of parser.push(decoder.decode(value, { stream: true }))) {
          onEvent(event)
        }
      }
    } finally {
      await reader.cancel().catch(() => undefined)
    }
  }

  private async request(path: string, init: RequestInit): Promise<unknown> {
    const response = await this.fetch(path, init)
    const payload: unknown = await response.json().catch(() => undefined)
    if (!response.ok) {
      const message = readErrorMessage(payload) ?? `Runtime 请求失败 (${response.status})`
      throw new Error(message)
    }
    return payload
  }

  private async fetch(path: string, init: RequestInit = {}): Promise<Response> {
    try {
      const response = await fetch(`${this.connection.baseUrl}${path}`, {
        ...init,
        headers: {
          Authorization: `Bearer ${this.connection.token}`,
          ...init.headers,
        },
      })
      if (response.status === 401) this.options.onConnectionInvalid?.()
      return response
    } catch (error) {
      this.options.onConnectionInvalid?.()
      throw error
    }
  }
}

function readErrorMessage(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const error = (value as Record<string, unknown>).error
  if (typeof error !== 'object' || error === null) return undefined
  const message = (error as Record<string, unknown>).message
  return typeof message === 'string' ? message : undefined
}
