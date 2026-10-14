import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { runtimeClient } from '../api/runtime'

export const useRuntimeStore = defineStore('runtime-overview', () => {
  const info = ref<Record<string, unknown>>({})
  const metrics = ref<Record<string, unknown>>({})
  const error = ref<string | null>(null)
  const loading = ref(false)
  const diskFree = computed(() => formatBytes(metrics.value.disk_free_bytes))
  const memory = computed(() => formatBytes(metrics.value.process_max_rss_bytes))
  const uptime = computed(() => typeof metrics.value.uptime_seconds === 'number'
    ? `${metrics.value.uptime_seconds.toFixed(1)} 秒` : '—')

  async function refresh(): Promise<void> {
    if (loading.value) return
    loading.value = true
    try {
      const client = await runtimeClient()
      const [nextInfo, nextMetrics] = await Promise.all([
        client.get('/internal/v1/runtime/info'),
        client.get('/internal/v1/runtime/metrics'),
      ])
      info.value = toRecord(nextInfo)
      metrics.value = toRecord(nextMetrics)
      error.value = null
    } catch (cause) {
      info.value = {}
      metrics.value = {}
      error.value = cause instanceof Error ? cause.message : '无法读取 Runtime 状态'
    } finally { loading.value = false }
  }

  return { info, metrics, error, loading, diskFree, memory, uptime, refresh }
})

function toRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {}
}

function formatBytes(value: unknown): string {
  if (typeof value !== 'number') return '—'
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`
  return `${(value / 1024 ** 3).toFixed(1)} GB`
}
