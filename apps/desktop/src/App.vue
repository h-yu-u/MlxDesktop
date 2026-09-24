<script setup lang="ts">
import { NButton, NTooltip } from 'naive-ui'
import { computed } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import AppProviders from './app/AppProviders.vue'
import {
  restartRuntimeProcess,
  runtimeConnectionError,
  runtimeConnectionStatus,
} from './shared/api/runtime'

const runtimeText = computed(() => ({
  starting: 'Runtime 启动中',
  ready: 'Runtime 已就绪',
  failed: 'Runtime 连接失败',
})[runtimeConnectionStatus.value])

function retryRuntime(): void {
  void restartRuntimeProcess().catch(() => undefined)
}
</script>

<template>
  <AppProviders>
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-mark">M</span><span>MLX Studio</span>
        </div>
        <nav class="nav-list" aria-label="主导航">
          <RouterLink class="nav-link" to="/chat"><span>◉</span>聊天</RouterLink>
          <RouterLink class="nav-link" to="/models"><span>▤</span>模型库</RouterLink>
          <RouterLink class="nav-link" to="/image-studio"><span>✦</span>图片创作</RouterLink>
          <RouterLink class="nav-link" to="/settings"><span>⚙</span>设置</RouterLink>
        </nav>
        <div class="sidebar-bottom">
          <div class="connection-chip">
            <span class="status-dot" />本地运行 · 数据保存在此设备
          </div>
          <NButton block secondary @click="$router.push('/models')">管理模型</NButton>
        </div>
      </aside>
      <main class="main-area">
        <header class="topbar">
          <span>Apple Silicon · 本地推理</span>
          <div class="runtime-summary">
            <NTooltip :disabled="!runtimeConnectionError">
              <template #trigger>
                <span class="connection-chip">
                  <span class="status-dot" :class="`status-${runtimeConnectionStatus}`" />
                  {{ runtimeText }}
                </span>
              </template>
              {{ runtimeConnectionError }}
            </NTooltip>
            <NButton
              v-if="runtimeConnectionStatus === 'failed'"
              size="tiny"
              secondary
              @click="retryRuntime"
            >重试</NButton>
          </div>
        </header>
        <RouterView />
      </main>
    </div>
  </AppProviders>
</template>

<style scoped>
.runtime-summary { display: flex; align-items: center; gap: 8px; }
.status-starting { background: #d79a2b; }
.status-failed { background: #c24148; }
</style>
