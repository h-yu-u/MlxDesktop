<script setup lang="ts">
import { NButton, NEmpty, NSelect, NSlider, NSpin, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref } from 'vue'
import ChatComposer from '../components/ChatComposer.vue'
import MessageBubble from '../components/MessageBubble.vue'
import { useChatStore } from '../stores/chat.store'

const store = useChatStore()
const message = useMessage()
const {
  state,
  models,
  conversations,
  conversationId,
  selectedModelId,
  maxTokens,
  temperature,
  busy,
} = storeToRefs(store)
const draft = ref('')
const images = ref<File[]>([])
const options = computed(() => models.value.map((model) => ({
  label: model.displayName,
  value: model.id,
})))
const selectedModel = computed(() => models.value.find(
  (model) => model.id === selectedModelId.value,
))
const imageLimit = computed(() => selectedModel.value?.inputModalities.includes('image')
  ? (selectedModel.value.multiImage ? 4 : 1)
  : 0)

onMounted(() => { void store.loadWorkspace() })

async function send(): Promise<void> {
  try {
    const accepted = await store.send(draft.value, images.value)
    if (accepted) {
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
</script>

<template>
  <section class="page-content">
    <div class="page-heading">
      <div>
        <h1 class="page-title">本地聊天</h1>
        <p class="page-subtitle">选择一个本地模型，开始私密对话</p>
      </div>
      <NButton secondary @click="store.newConversation">新建对话</NButton>
    </div>
    <div class="chat-layout">
      <section class="panel chat-panel" aria-label="对话">
        <div class="message-list" aria-live="polite">
          <NSpin v-if="state.status === 'loading'" size="small" />
          <NEmpty v-else-if="!state.messages.length" description="开始一次本地对话" />
          <MessageBubble v-for="item in state.messages" :key="item.id" :message="item" />
          <p v-if="state.error" role="alert" class="error-text">{{ state.error }}</p>
        </div>
        <ChatComposer
          v-model:draft="draft"
          v-model:images="images"
          :busy="busy"
          :image-limit="imageLimit"
          @submit="send"
          @cancel="cancel"
        />
      </section>
      <aside class="panel side-panel">
        <strong>当前模型</strong>
        <NSelect v-model:value="selectedModelId" :options="options" placeholder="选择模型" />
        <div>
          <div class="parameter-label"><span>最大输出</span><span>{{ maxTokens }}</span></div>
          <NSlider v-model:value="maxTokens" :min="64" :max="2048" :step="64" />
        </div>
        <div>
          <div class="parameter-label">
            <span>温度</span><span>{{ temperature.toFixed(1) }}</span>
          </div>
          <NSlider v-model:value="temperature" :min="0" :max="2" :step="0.1" />
        </div>
        <div class="recent-conversations">
          <strong>最近对话</strong>
          <button
            v-for="item in conversations.slice(0, 8)"
            :key="item.id"
            class="conversation-link"
            :aria-current="conversationId === item.id"
            @click="store.openConversation(item.id)"
          >{{ item.title }}</button>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.page-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.error-text { color: #c24148; }
.parameter-label { display: flex; justify-content: space-between; font-size: 13px; }
.recent-conversations { border-top: 1px solid #eceef3; padding-top: 12px; }
.recent-conversations strong { font-size: 13px; }
.conversation-link { display:block;width:100%;text-align:left;border:0;background:transparent;padding:8px 0;color:#71798a;cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.conversation-link[aria-current="true"] { color:#4f46e5;font-weight:600; }
</style>
