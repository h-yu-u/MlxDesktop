<script setup lang="ts">
import { NButton, NTooltip, useMessage } from 'naive-ui'
import { computed, ref } from 'vue'
import { restartRuntimeProcess, runtimeConnectionError, runtimeConnectionStatus } from '../shared/api/runtime'
import { useRuntimeStore } from '../shared/stores/runtime.store'
import { useChatStore } from '../modules/chat/stores/chat.store'
import StudioIcon from '../shared/components/StudioIcon.vue'

const runtime = useRuntimeStore()
const chat = useChatStore()
const message = useMessage()
const retrying = ref(false)
const status = computed(() => runtime.error ? 'failed' : runtimeConnectionStatus.value)
const text = computed(() => ({ starting: 'Runtime 启动中', ready: 'Runtime 运行中', failed: 'Runtime 未连接' })[status.value])
async function retry(): Promise<void> {
  retrying.value = true
  try {
    if ('__TAURI_INTERNALS__' in window) await restartRuntimeProcess()
    await runtime.refresh()
    await chat.loadWorkspace()
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '重试失败')
  } finally { retrying.value = false }
}
</script>

<template>
  <div class="runtime-summary">
    <NTooltip>
      <template #trigger>
        <NButton
          class="runtime-badge"
          :class="`runtime-${status}`"
          secondary
          :loading="retrying"
          :disabled="status === 'starting' || chat.busy || chat.pending"
          @click="status === 'failed' ? retry() : $router.push('/settings')"
        >
          <span
            class="status-dot"
            :class="`status-${status}`"
          />{{ text }}<StudioIcon
            name="chevron"
            :size="16"
          />
        </NButton>
      </template>
      {{ runtime.error || runtimeConnectionError || '查看本地 Runtime 状态' }}
    </NTooltip>
  </div>
</template>
