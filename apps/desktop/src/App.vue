<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NNotificationProvider, NButton } from 'naive-ui'
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <NConfigProvider>
    <NMessageProvider>
      <NNotificationProvider>
        <div class="app-shell">
          <aside class="sidebar">
            <div class="brand">
              <span class="brand-mark">M</span><span>MLX Studio</span>
            </div>
            <nav
              class="nav-list"
              aria-label="主导航"
            >
              <RouterLink
                class="nav-link"
                to="/chat"
              >
                <span>◉</span>聊天
              </RouterLink>
              <RouterLink
                class="nav-link"
                to="/models"
              >
                <span>▤</span>模型库
              </RouterLink>
              <RouterLink
                class="nav-link"
                to="/image-studio"
              >
                <span>✦</span>图片创作
              </RouterLink>
              <RouterLink
                class="nav-link"
                to="/settings"
              >
                <span>⚙</span>设置
              </RouterLink>
            </nav>
            <div class="sidebar-bottom">
              <div class="connection-chip">
                <span class="status-dot" />本地运行 · 数据保存在此设备
              </div>
              <NButton
                block
                secondary
                @click="$router.push('/models')"
              >
                管理模型
              </NButton>
            </div>
          </aside>
          <main class="main-area">
            <header class="topbar">
              <span>Apple Silicon · 本地推理</span>
              <span class="connection-chip"><span class="status-dot" />Runtime 已就绪</span>
            </header>
            <RouterView />
          </main>
        </div>
      </NNotificationProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>
