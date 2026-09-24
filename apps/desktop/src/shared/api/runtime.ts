import { RuntimeClient, type RuntimeConnection } from '@mlx-studio/api-client'
import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import { readonly, ref } from 'vue'

export type RuntimeConnectionStatus = 'starting' | 'ready' | 'failed'

interface RuntimeStatusEvent {
  status: RuntimeConnectionStatus
  generation: number
  message?: string | null
}

let client: RuntimeClient | undefined
let connection: RuntimeConnection | undefined
let connecting: Promise<RuntimeClient> | undefined
let listenerReady: Promise<UnlistenFn | undefined> | undefined

const status = ref<RuntimeConnectionStatus>('starting')
const error = ref<string | null>(null)

export const runtimeConnectionStatus = readonly(status)
export const runtimeConnectionError = readonly(error)

export async function runtimeClient(): Promise<RuntimeClient> {
  if (client) return client
  if (connecting) return connecting
  connecting = connect().finally(() => { connecting = undefined })
  return connecting
}

export async function restartRuntimeProcess(): Promise<RuntimeClient> {
  if (!isTauri()) throw new Error('浏览器调试模式无法重启桌面 Runtime')
  invalidate('正在重启 Runtime', 'starting')
  await invoke('restart_runtime_process')
  return runtimeClient()
}

export function currentConnection(): RuntimeConnection | undefined {
  return connection
}

async function connect(): Promise<RuntimeClient> {
  await ensureRuntimeListener()
  status.value = 'starting'
  error.value = null
  try {
    const next = isTauri()
      ? await invoke<RuntimeConnection>('runtime_connection')
      : browserConnection()
    if (next.protocolVersion !== 1) {
      throw new Error(`Runtime 协议版本不兼容：${next.protocolVersion}`)
    }
    connection = next
    client = new RuntimeClient(next, {
      onConnectionInvalid: () => invalidate('Runtime 连接已失效'),
    })
    status.value = 'ready'
    return client
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : 'Runtime 连接失败'
    invalidate(message)
    throw cause
  }
}

async function ensureRuntimeListener(): Promise<void> {
  if (!isTauri()) return
  if (!listenerReady) {
    listenerReady = listen<RuntimeStatusEvent>('runtime-status', ({ payload }) => {
      if (!payload || typeof payload !== 'object') return
      if (payload.status === 'failed') {
        invalidate(payload.message ?? 'Runtime 已退出')
        return
      }
      if (payload.status === 'starting') {
        invalidate(null, 'starting')
        return
      }
      if (connection?.generation !== undefined
        && connection.generation !== payload.generation) {
        client = undefined
        connection = undefined
      }
      status.value = 'ready'
      error.value = null
    }).catch(() => undefined)
  }
  await listenerReady
}

function browserConnection(): RuntimeConnection {
  const baseUrl = import.meta.env.VITE_RUNTIME_URL
  const token = import.meta.env.VITE_RUNTIME_TOKEN
  if (!baseUrl || !token) {
    throw new Error('请从桌面应用启动，或配置本地开发 Runtime 地址')
  }
  return { baseUrl, token, protocolVersion: 1, generation: 1 }
}

function invalidate(
  message: string | null,
  nextStatus: RuntimeConnectionStatus = 'failed',
): void {
  client = undefined
  connection = undefined
  status.value = nextStatus
  error.value = message
}

function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}
