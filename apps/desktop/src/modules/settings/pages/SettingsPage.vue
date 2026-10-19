<script setup lang="ts">
import { NButton, NCard, NDescriptions, NDescriptionsItem, NSpin, useMessage } from 'naive-ui'
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRuntimeStore } from '../../../capabilities/runtime'
import { CodingSettingsPanel } from '../../../capabilities/coding-settings'
import { WebSearchSettings } from '../../../capabilities/web-search'
import PageHeader from '../../../shared/ui/PageHeader.vue'
const runtime = useRuntimeStore()
const { info, loading } = storeToRefs(runtime)
const message = useMessage()
async function refresh(): Promise<void> {
  await runtime.refresh()
  if (runtime.error) message.error(runtime.error)
}
async function restart(): Promise<void> {
  try {
    await runtime.restart()
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '重启失败')
  }
}
async function downloadDiagnostics(): Promise<void> {
  try {
    await runtime.downloadDiagnostics()
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '导出失败')
  }
}
onMounted(() => {
  void refresh()
})
</script>

<template>
  <section class="page-content">
    <PageHeader title="设置" subtitle="Runtime 状态、资源和本地数据" />
    <NSpin :show="loading">
      <NCard title="Runtime">
        <NDescriptions :column="1" label-placement="left">
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
            {{ runtime.uptime }}
          </NDescriptionsItem>
          <NDescriptionsItem label="可用磁盘">
            {{ runtime.diskFree }}
          </NDescriptionsItem>
          <NDescriptionsItem label="系统内存（已用 / 总量）">
            {{ runtime.systemMemory }}
          </NDescriptionsItem>
          <NDescriptionsItem label="内存使用率">
            {{ runtime.memoryPercent === null ? '—' : `${runtime.memoryPercent.toFixed(1)}%` }}
          </NDescriptionsItem>
          <NDescriptionsItem label="推理进程内存">
            {{ runtime.workerMemory }}
          </NDescriptionsItem>
        </NDescriptions>
        <template #footer>
          <NButton secondary @click="refresh"> 刷新 </NButton
          ><NButton style="margin-left: 8px" @click="restart"> 重启 Worker </NButton
          ><NButton style="margin-left: 8px" @click="downloadDiagnostics"> 导出脱敏诊断包 </NButton>
        </template>
      </NCard>
    </NSpin>
    <NCard title="扩展能力" style="margin-top: 16px">
      <p>统一管理 Skills、MCP 服务与内置工具。</p>
      <RouterLink to="/settings/extensions/skills">打开扩展设置</RouterLink>
    </NCard>
    <CodingSettingsPanel />
    <WebSearchSettings />
    <NCard title="隐私与数据" style="margin-top: 16px">
      <p>会话和生成文件保存在本机。日志默认不记录完整提示词、模型输出或附件内容。</p>
      <p>本地兼容 API 默认关闭，仅监听回环地址并使用独立令牌。</p>
    </NCard>
  </section>
</template>
