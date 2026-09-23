<script setup lang="ts">
import { NButton, NCard, NDescriptions, NDescriptionsItem, NSpin, useMessage } from 'naive-ui'
import { onMounted, ref } from 'vue'
import { runtimeClient } from '../../../shared/api/runtime'

const info = ref<Record<string, unknown>>({})
const metrics = ref<Record<string, unknown>>({})
const loading = ref(true)
const message = useMessage()

async function refresh(): Promise<void> {
  loading.value = true
  try {
    const client = await runtimeClient()
    info.value = toRecord(await client.get('/internal/v1/runtime/info'))
    metrics.value = toRecord(await client.get('/internal/v1/runtime/metrics'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : '无法连接 Runtime')
  } finally { loading.value = false }
}

async function restart(): Promise<void> {
  try { await (await runtimeClient()).post('/internal/v1/runtime/restart-worker'); await refresh() }
  catch (error) { message.error(error instanceof Error ? error.message : '重启失败') }
}

async function downloadDiagnostics(): Promise<void> {
  try {
    const bundle = await (await runtimeClient()).downloadDiagnosticBundle()
    const url = URL.createObjectURL(bundle)
    const link = document.createElement('a')
    link.href = url
    link.download = 'mlx-studio-diagnostics.zip'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) { message.error(error instanceof Error ? error.message : '诊断包下载失败') }
}

onMounted(() => { void refresh() })
function toRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {}
}
function formatBytes(value: unknown): string {
  if (typeof value !== 'number') return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let amount = value
  let unit = 0
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit += 1 }
  return `${amount.toFixed(1)} ${units[unit]}`
}
</script>

<template>
  <section class="page-content">
    <h1 class="page-title">
      设置
    </h1><p class="page-subtitle">
      Runtime 状态、资源和本地数据
    </p>
    <NSpin :show="loading">
      <NCard title="Runtime">
        <NDescriptions
          :column="1"
          label-placement="left"
        >
          <NDescriptionsItem label="状态">
            {{ info.state ?? '未知' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="协议版本">
            {{ info.protocol_version ?? '—' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="当前模型">
            {{ info.active_model_id ?? '未加载' }}
          </NDescriptionsItem>
          <NDescriptionsItem label="运行时长">
            {{ metrics.uptime_seconds ?? 0 }} 秒
          </NDescriptionsItem>
          <NDescriptionsItem label="可用磁盘">
            {{ formatBytes(metrics.disk_free_bytes) }}
          </NDescriptionsItem>
        </NDescriptions>
        <template #footer>
          <NButton
            secondary
            @click="refresh"
          >
            刷新
          </NButton><NButton
            style="margin-left:8px"
            @click="restart"
          >
            重启 Worker
          </NButton><NButton
            style="margin-left:8px"
            @click="downloadDiagnostics"
          >
            导出脱敏诊断包
          </NButton>
        </template>
      </NCard>
    </NSpin>
    <NCard
      title="隐私与数据"
      style="margin-top:16px"
    >
      <p>会话和生成文件保存在本机。日志默认不记录完整提示词、模型输出或附件内容。</p>
      <p>本地兼容 API 默认关闭，仅监听回环地址并使用独立令牌。</p>
    </NCard>
  </section>
</template>
