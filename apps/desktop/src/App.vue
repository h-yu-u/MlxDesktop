<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import AppProviders from './app/AppProviders.vue'
import StudioSidebar from './app/StudioSidebar.vue'
import RuntimeStatus from './app/RuntimeStatus.vue'

const route = useRoute()
</script>

<template>
  <AppProviders>
    <div class="app-shell">
      <StudioSidebar />
      <main class="main-area">
        <header
          v-if="route.path !== '/chat'"
          class="topbar"
        >
          <span>你的本地 AI 工作台</span><RuntimeStatus />
        </header>
        <RouterView />
      </main>
    </div>
  </AppProviders>
</template>
