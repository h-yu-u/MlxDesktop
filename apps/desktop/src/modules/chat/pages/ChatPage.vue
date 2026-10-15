<script setup lang="ts">
import { NButton, NDrawer, NDrawerContent, NSelect, useDialog, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { RuntimeStatusBanner as RuntimeStatus } from '../../../capabilities/runtime'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import ChatComposer from '../components/ChatComposer.vue'
import ChatInspector from '../components/ChatInspector.vue'
import ChatMessageList from '../components/ChatMessageList.vue'
import { useRuntimeStore } from '../../../capabilities/runtime'
import { useChatStore } from '../stores/chat.store'

const store = useChatStore()
const runtime = useRuntimeStore()
const message = useMessage()
const dialog = useDialog()
const router = useRouter()
const { state, models, selectedModelId, busy, pending, maxTokens, temperature } = storeToRefs(store)
const draft = ref('')
const images = ref<File[]>([])
const showInspector = ref(false)
const clearing = ref(false)
const options = computed(() =>
  models.value.map((model) => ({ label: model.displayName, value: model.id })),
)
const selectedModel = computed(() =>
  models.value.find((model) => model.id === selectedModelId.value),
)
const imageLimit = computed(() =>
  selectedModel.value?.inputModalities.includes('image')
    ? selectedModel.value.multiImage
      ? 4
      : 1
    : 0,
)
onMounted(() => {
  void store.loadWorkspace()
})
onBeforeUnmount(() => store.dispose())

async function send(): Promise<void> {
  if (pending.value || busy.value) return
  try {
    if (await store.send(draft.value, images.value)) {
      draft.value = ''
      images.value = []
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : '发送失败')
  }
}

async function cancel(): Promise<void> {
  try {
    await store.cancel()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '停止生成失败')
  }
}

async function continueReply(): Promise<void> {
  if (pending.value || busy.value) return
  try {
    await store.send('请从上一个回答中断的位置继续，不要重复已经输出的内容。')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '继续回答失败')
  }
}

function clearConversation(): void {
  dialog.warning({
    title: '清空当前对话',
    content: '此操作会删除当前会话及其消息，无法恢复。',
    positiveText: '清空对话',
    negativeText: '取消',
    onPositiveClick: async () => {
      clearing.value = true
      try {
        await store.clearConversation()
      } catch (error) {
        message.error(error instanceof Error ? error.message : '清空失败')
      } finally {
        clearing.value = false
      }
    },
  })
}

function exportChat(): void {
  store.exportConversation()
  message.success('对话已导出为 Markdown')
}
</script>

<template>
  <section class="chat-workspace">
    <header class="chat-toolbar">
      <div class="toolbar-actions">
        <RuntimeStatus :busy="busy || pending" @reconnected="store.loadWorkspace" />
        <NButton
          quaternary
          circle
          aria-label="打开模型设置"
          :aria-expanded="showInspector"
          @click="showInspector = true"
        >
          <StudioIcon name="settings" :size="19" />
        </NButton>
      </div>
    </header>
    <section class="chat-stage" :class="{ 'is-new': !state.messages.length }" aria-label="对话">
      <ChatMessageList
        :messages="state.messages"
        :total-count="state.messages.length"
        :status="state.status"
        :error="state.error"
        @prompt="draft = $event"
        @image="router.push({ path: '/image-studio', query: { prompt: $event } })"
        @continue="continueReply"
      />
      <ChatComposer
        v-model:draft="draft"
        v-model:images="images"
        :busy="busy || pending"
        :generating="busy"
        :image-limit="imageLimit"
        @submit="send"
        @cancel="cancel"
      >
        <template #model>
          <div class="composer-model">
            <span class="model-status-dot" :class="{ 'model-status-offline': !models.length }" />
            <NSelect
              :value="selectedModel?.id ?? null"
              class="model-select"
              :options="options"
              :disabled="busy || pending"
              :loading="state.status === 'loading'"
              placeholder="选择本地模型"
              aria-label="当前模型"
              :consistent-menu-width="false"
              @update:value="selectedModelId = $event"
            />
          </div>
        </template>
      </ChatComposer>
    </section>
    <NDrawer v-model:show="showInspector" :width="360" placement="right">
      <NDrawerContent title="模型与会话" closable>
        <ChatInspector
          v-model:max-tokens="maxTokens"
          v-model:temperature="temperature"
          :selected-model="selectedModel"
          :runtime="runtime"
          :message-count="state.messages.length"
          :busy="busy || pending"
          :clearing="clearing"
          @reset="store.resetParameters"
          @clear="clearConversation"
          @export="exportChat"
        />
      </NDrawerContent>
    </NDrawer>
  </section>
</template>

<style scoped src="./ChatPage.styles.css"></style>
