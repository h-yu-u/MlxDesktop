import { invoke } from '@tauri-apps/api/core'
import { RuntimeClient, type RuntimeConnection } from '@mlx-studio/api-client'

let client: RuntimeClient | undefined
let connection: RuntimeConnection | undefined

export async function runtimeClient(): Promise<RuntimeClient> {
  if (client) return client
  if (typeof window === 'undefined') throw new Error('Runtime is unavailable')
  if ('__TAURI_INTERNALS__' in window) {
    connection = await invoke<RuntimeConnection>('runtime_connection')
  } else {
    const baseUrl = import.meta.env.VITE_RUNTIME_URL
    const token = import.meta.env.VITE_RUNTIME_TOKEN
    if (!baseUrl || !token) throw new Error('请从桌面应用启动，或配置本地开发 Runtime 地址')
    connection = { baseUrl, token, protocolVersion: 1 }
  }
  client = new RuntimeClient(connection)
  return client
}

export function currentConnection(): RuntimeConnection | undefined {
  return connection
}
