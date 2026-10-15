<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppProviders from './app/AppProviders.vue'
import StudioSidebar from './app/StudioSidebar.vue'
import { RuntimeStatusBanner as RuntimeStatus } from './capabilities/runtime'

const route = useRoute()
const showConversations = computed(() => route.path === '/chat')
</script>

<template>
  <AppProviders>
    <div class="app-shell" :class="{ 'has-chat-sidebar': showConversations }">
      <StudioSidebar :show-conversations="showConversations" />
      <main class="main-area">
        <header v-if="!showConversations" class="topbar">
          <span>你的本地 AI 工作台</span><RuntimeStatus />
        </header>
        <RouterView />
      </main>
    </div>
  </AppProviders>
</template>

<style scoped src="./App.styles.css"></style>
