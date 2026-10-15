<script setup lang="ts">
import { NButton, NInput, NModal, useDialog, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { Conversation } from '@mlx-studio/api-client'
import ConversationListItem from '../modules/chat/components/ConversationListItem.vue'
import { visibleConversations as selectConversations } from '../modules/chat/domain/conversation-list'
import { useChatStore } from '../modules/chat/stores/chat.store'
import StudioIcon from '../shared/components/StudioIcon.vue'

const props = defineProps<{ showConversations: boolean }>()
const chat = useChatStore()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const renameOpen = ref(false)
const renameTarget = ref<Conversation | null>(null)
const renameTitle = ref('')
const query = ref('')
const showSearch = ref(false)
const navigating = ref(false)
const { pending } = storeToRefs(chat)
const visibleConversations = computed(() =>
  selectConversations(chat.conversations, query.value, showSearch.value ? undefined : 30),
)
const links = [
  { to: '/chat', icon: 'chat', label: '聊天' },
  { to: '/models', icon: 'cube', label: '模型库' },
  { to: '/image-studio', icon: 'image', label: '图片创作' },
  { to: '/settings', icon: 'settings', label: '设置' },
]

watch(
  () => props.showConversations,
  (visible) => {
    if (visible) void chat.loadWorkspace()
    else renameOpen.value = false
  },
  { immediate: true },
)

async function navigateConversation(id?: string): Promise<void> {
  if (chat.busy || pending.value || navigating.value) return
  navigating.value = true
  try {
    if (id) await chat.openConversation(id)
    else await chat.newConversation()
    await router.push('/chat')
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '无法打开对话')
  } finally {
    navigating.value = false
  }
}
function openRename(item: Conversation): void {
  renameTarget.value = item
  renameTitle.value = item.title
  renameOpen.value = true
}
async function saveRename(): Promise<boolean> {
  if (!renameTarget.value || chat.busy || pending.value) return false
  try {
    await chat.renameConversation(renameTarget.value.id, renameTitle.value)
    return true
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '重命名失败')
    return false
  }
}
function confirmDelete(item: Conversation): void {
  dialog.warning({
    title: '删除对话',
    content: `确定删除「${item.title}」及其全部消息？此操作无法恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      if (chat.busy || pending.value) return false
      try {
        await chat.deleteConversation(item.id)
      } catch (cause) {
        message.error(cause instanceof Error ? cause.message : '删除失败')
        return false
      }
    },
  })
}
async function togglePin(id: string): Promise<void> {
  try {
    await chat.toggleConversationPin(id)
  } catch (cause) {
    message.error(cause instanceof Error ? cause.message : '置顶操作失败')
  }
}
function toggleSearch(): void {
  showSearch.value = !showSearch.value
  query.value = ''
}
</script>

<template>
  <aside class="sidebar" :class="{ 'sidebar-chat': showConversations }">
    <nav class="icon-rail" aria-label="主导航">
      <RouterLink to="/chat" class="rail-brand" aria-label="MLX Studio 首页">M</RouterLink>
      <RouterLink
        v-for="link in links"
        :key="link.to"
        class="rail-link"
        :to="link.to"
        :title="link.label"
        :aria-label="link.label"
        ><StudioIcon :name="link.icon" :size="21"
      /></RouterLink>
    </nav>
    <div v-if="showConversations" class="sidebar-content">
      <div class="sidebar-heading">
        <RouterLink to="/chat" class="brand"
          >MLX Studio<StudioIcon name="down" :size="15"
        /></RouterLink>
        <NButton
          quaternary
          circle
          size="small"
          aria-label="搜索历史对话"
          :aria-expanded="showSearch"
          @click="toggleSearch"
        >
          <StudioIcon name="search" :size="19" />
        </NButton>
      </div>
      <NButton
        quaternary
        class="new-conversation"
        :disabled="chat.busy || pending || navigating"
        @click="navigateConversation()"
      >
        <StudioIcon name="compose" :size="20" />新对话
      </NButton>
      <section class="workspace-nav" aria-label="最近对话">
        <div class="workspace-heading">
          <span>最近对话</span>
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
            :disabled="chat.busy || pending || navigating"
            @click="navigateConversation()"
          >
            <StudioIcon name="chat" :size="17" />新的对话
          </NButton>
          <ConversationListItem
            v-for="item in visibleConversations"
            :key="item.id"
            :conversation="item"
            :active="chat.conversationId === item.id"
            :disabled="chat.busy || pending || navigating"
            @open="navigateConversation(item.id)"
            @rename="openRename(item)"
            @remove="confirmDelete(item)"
            @pin="togglePin(item.id)"
          />
          <p v-if="showSearch && !visibleConversations.length" class="sidebar-empty">
            没有匹配的对话
          </p>
        </div>
      </section>
      <RouterLink to="/settings" class="sidebar-bottom">
        <span><strong>本地工作空间</strong></span>
      </RouterLink>
    </div>
    <NModal
      v-if="showConversations"
      v-model:show="renameOpen"
      preset="dialog"
      title="重命名对话"
      positive-text="保存"
      negative-text="取消"
      :loading="pending"
      :positive-button-props="{ disabled: chat.busy || pending || !renameTitle.trim() }"
      @positive-click="saveRename"
    >
      <NInput
        v-model:value="renameTitle"
        placeholder="输入对话名称"
        aria-label="对话名称"
        :maxlength="160"
        :disabled="pending"
        autofocus
        show-count
      />
    </NModal>
  </aside>
</template>

<style scoped src="./StudioSidebar.styles.css"></style>
