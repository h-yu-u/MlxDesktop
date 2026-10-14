<script setup lang="ts">
import { NButton, NDropdown, NDrawer, NDrawerContent, NEmpty, NInput, NSelect, NSpin, useDialog, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { useMediaQuery } from '@vueuse/core'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import RuntimeStatus from '../../../app/RuntimeStatus.vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import ChatComposer from '../components/ChatComposer.vue'
import ChatInspector from '../components/ChatInspector.vue'
import ChatWelcome from '../components/ChatWelcome.vue'
import MessageBubble from '../components/MessageBubble.vue'
import { exportConversation } from '../services/export-conversation'
import { useChatStore } from '../stores/chat.store'

const store = useChatStore()
const message = useMessage()
const dialog = useDialog()
const router = useRouter()
const { state, models, conversations, conversationId, selectedModelId, busy, pending } = storeToRefs(store)
const draft = ref('')
const images = ref<File[]>([])
const compact = useMediaQuery('(max-width: 1050px)')
const showInspector = ref(false)
const clearing = ref(false)
const showSearch = ref(false)
const search = ref('')
const messageList = ref<HTMLElement | null>(null)
const options = computed(() => models.value.map((model) => ({ label: model.displayName, value: model.id })))
const selectedModel = computed(() => models.value.find((model) => model.id === selectedModelId.value))
const imageLimit = computed(() => selectedModel.value?.inputModalities.includes('image')
  ? (selectedModel.value.multiImage ? 4 : 1) : 0)
const visibleMessages = computed(() => state.value.messages.filter(
  (item) => item.content.toLowerCase().includes(search.value.toLowerCase()),
))
onMounted(() => { if (state.value.status !== 'loading' && !busy.value && !pending.value) void store.loadWorkspace() })
const menuOptions = [{ label: '管理本地模型', key: 'models' }, { label: '重置生成参数', key: 'reset' }]
watch(() => state.value.messages.map((item) => item.content).join(''), async () => {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
})

async function send(): Promise<void> {
  if (pending.value || busy.value) return
  pending.value = true
  try {
    if (await store.send(draft.value, images.value)) { draft.value = ''; images.value = [] }
  } catch (error) {
    message.error(error instanceof Error ? error.message : '发送失败')
  } finally { pending.value = false }
}

async function cancel(): Promise<void> {
  try { await store.cancel() }
  catch (error) { message.error(error instanceof Error ? error.message : '停止生成失败') }
}

async function newConversation(): Promise<void> {
  pending.value = true
  try {
    await store.newConversation()
    search.value = ''
  } catch (error) { message.error(error instanceof Error ? error.message : '新建对话失败') }
  finally { pending.value = false }
}

function clearConversation(): void {
  dialog.warning({
    title: '清空当前对话', content: '此操作会删除当前会话及其消息，无法恢复。',
    positiveText: '清空对话', negativeText: '取消',
    onPositiveClick: async () => {
      clearing.value = true
      pending.value = true
      try { await store.clearConversation(); search.value = '' }
      catch (error) { message.error(error instanceof Error ? error.message : '清空失败') }
      finally { clearing.value = false; pending.value = false }
    },
  })
}

function exportChat(): void {
  const title = conversations.value.find((item) => item.id === conversationId.value)?.title ?? '本地对话'
  exportConversation(title, state.value.messages)
  message.success('对话已导出为 Markdown')
}

function selectMenu(key: string): void {
  if (key === 'models') void router.push('/models')
  else { store.maxTokens = 512; store.temperature = 0.7 }
}
</script>

<template>
  <section class="chat-workspace">
    <header class="chat-toolbar panel">
      <span
        class="model-status-dot"
        :class="{ 'model-status-offline': !models.length }"
      />
      <NSelect
        :value="selectedModel?.id ?? null"
        class="model-select"
        :options="options"
        :disabled="busy || pending"
        :loading="state.status === 'loading'"
        placeholder="选择本地模型"
        aria-label="当前模型"
        @update:value="selectedModelId = $event"
      />
      <div
        v-if="selectedModel"
        class="model-tags"
      >
        <span>{{ selectedModel.engine === 'fake' ? 'DEV' : selectedModel.engine }}</span><span>{{ imageLimit ? '多模态' : '文本生成' }}</span>
      </div>
      <div class="toolbar-actions">
        <NButton
          v-if="compact"
          secondary
          aria-label="打开模型设置"
          @click="showInspector = true"
        >
          <StudioIcon
            name="settings"
            :size="18"
          />
        </NButton>
        <NButton
          secondary
          aria-label="新对话"
          :disabled="busy || pending"
          @click="newConversation"
        >
          <StudioIcon
            name="plus"
            :size="17"
          /><span class="new-chat-label">新对话</span>
        </NButton>
        <NDropdown
          :options="menuOptions"
          :disabled="busy || pending"
          @select="selectMenu"
        >
          <NButton
            secondary
            aria-label="更多操作"
            :disabled="busy || pending"
          >
            <StudioIcon name="more" />
          </NButton>
        </NDropdown>
        <NButton
          secondary
          aria-label="搜索当前对话"
          :aria-expanded="showSearch"
          @click="showSearch = !showSearch; search = ''"
        >
          <StudioIcon
            name="search"
            :size="18"
          />
        </NButton>
      </div>
    </header>
    <RuntimeStatus />
    <section
      class="chat-stage"
      aria-label="对话"
    >
      <NInput
        v-if="showSearch"
        v-model:value="search"
        class="message-search"
        placeholder="搜索当前对话中的内容"
        clearable
        aria-label="搜索消息"
      />
      <div
        ref="messageList"
        class="message-list"
        :class="{ 'is-empty': !state.messages.length }"
        aria-live="polite"
      >
        <div
          v-if="state.status === 'loading'"
          class="chat-loading"
        >
          <NSpin size="medium" /><span>正在读取本地工作区…</span>
        </div>
        <ChatWelcome
          v-else-if="!state.messages.length"
          @prompt="draft = $event"
          @image="router.push({ path: '/image-studio', query: { prompt: $event } })"
        />
        <MessageBubble
          v-for="item in visibleMessages"
          :key="item.id"
          :message="item"
        />
        <NEmpty
          v-if="state.messages.length && !visibleMessages.length"
          description="没有找到匹配的消息"
        />
        <p
          v-if="state.error"
          role="alert"
          class="error-text"
        >
          {{ state.error }}
        </p>
      </div>
      <ChatComposer
        v-model:draft="draft"
        v-model:images="images"
        :busy="busy || pending"
        :generating="busy"
        :image-limit="imageLimit"
        @submit="send"
        @cancel="cancel"
      />
    </section>
    <ChatInspector
      v-if="!compact"
      :clearing="clearing"
      @clear="clearConversation"
      @export="exportChat"
    />
    <NDrawer
      v-model:show="showInspector"
      :width="310"
      placement="right"
    >
      <NDrawerContent
        title="模型与会话"
        closable
      >
        <ChatInspector
          :clearing="clearing"
          @clear="clearConversation"
          @export="exportChat"
        />
      </NDrawerContent>
    </NDrawer>
  </section>
</template>
