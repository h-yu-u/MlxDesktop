<script setup lang="ts">
import { NButton, NInput, useMessage } from 'naive-ui'
import { useIntervalFn } from '@vueuse/core'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../modules/chat/stores/chat.store'
import StudioIcon from '../shared/components/StudioIcon.vue'
import { useRuntimeStore } from '../shared/stores/runtime.store'

const chat = useChatStore()
const runtime = useRuntimeStore()
const router = useRouter()
const message = useMessage()
const query = ref('')
const showSearch = ref(false)
const { pending } = storeToRefs(chat)
const visibleConversations = computed(() => chat.conversations.filter(
  (item) => item.title.toLowerCase().includes(query.value.toLowerCase()),
).slice(0, showSearch.value ? undefined : 7))
const links = [
  { to: '/chat', icon: 'chat', label: '聊天' },
  { to: '/models', icon: 'cube', label: '模型库' },
  { to: '/image-studio', icon: 'image', label: '图片创作' },
  { to: '/settings', icon: 'settings', label: '设置' },
]

onMounted(() => { void chat.loadWorkspace(); void runtime.refresh() })
useIntervalFn(() => { void runtime.refresh() }, 15000)

async function navigateConversation(id?: string): Promise<void> {
  if (chat.busy || pending.value) return
  pending.value = true
  try {
    if (id) await chat.openConversation(id)
    else await chat.newConversation()
    await router.push('/chat')
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '无法打开对话')
  } finally { pending.value = false }
}
</script>

<template>
  <aside class="sidebar">
    <div
      class="sidebar-window-space"
      data-tauri-drag-region
    />
    <RouterLink
      to="/chat"
      class="brand"
    >
      <span class="brand-mark">M</span>
      <span class="brand-copy"><strong>MLX Studio</strong><small>Your Local AI Playground</small></span>
    </RouterLink>
    <nav
      class="nav-list"
      aria-label="主导航"
    >
      <RouterLink
        v-for="link in links"
        :key="link.to"
        class="nav-link"
        :to="link.to"
      >
        <StudioIcon
          :name="link.icon"
          :size="23"
        />{{ link.label }}
      </RouterLink>
    </nav>
    <section
      class="workspace-nav"
      aria-label="工作区"
    >
      <div class="workspace-heading">
        <span>工作区</span>
        <NButton
          quaternary
          circle
          size="small"
          aria-label="新建对话"
          :disabled="chat.busy || pending"
          @click="navigateConversation()"
        >
          <StudioIcon
            name="plus"
            :size="17"
          />
        </NButton>
      </div>
      <NInput
        v-if="showSearch"
        v-model:value="query"
        placeholder="搜索全部对话"
        size="small"
        clearable
        aria-label="搜索全部对话"
      />
      <div class="conversation-nav">
        <NButton
          v-if="!chat.conversations.length"
          quaternary
          class="conversation-link"
          :disabled="chat.busy || pending"
          @click="navigateConversation()"
        >
          <StudioIcon
            name="chat"
            :size="17"
          />新的对话
        </NButton>
        <button
          v-for="item in visibleConversations"
          :key="item.id"
          class="conversation-link"
          :aria-current="chat.conversationId === item.id ? 'true' : undefined"
          :disabled="chat.busy || pending"
          @click="navigateConversation(item.id)"
        >
          <StudioIcon
            name="chat"
            :size="17"
          /><span>{{ item.title }}</span>
        </button>
        <p
          v-if="showSearch && !visibleConversations.length"
          class="sidebar-empty"
        >
          没有匹配的对话
        </p>
      </div>
      <NButton
        quaternary
        class="all-conversations"
        @click="showSearch = !showSearch; query = ''"
      >
        <StudioIcon
          name="search"
          :size="17"
        />{{ showSearch ? '收起全部对话' : '查看全部对话' }}
      </NButton>
    </section>
    <div class="sidebar-bottom panel">
      <div class="device-label">
        <StudioIcon
          name="monitor"
          :size="22"
        /><span>本地运行 · Apple Silicon</span>
      </div>
      <div class="resource-row">
        <span>可用磁盘</span><span>{{ runtime.diskFree }}</span>
      </div>
      <div class="resource-track">
        <span />
      </div>
      <div class="resource-row">
        <span>Runtime 峰值内存</span><span>{{ runtime.memory }}</span>
      </div>
      <p class="device-footnote">
        你的数据，始终留在你的设备上
      </p>
    </div>
  </aside>
</template>
