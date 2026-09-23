<script setup lang="ts">
import { NButton, NCard, NInput, NInputNumber, useMessage } from 'naive-ui'
import { ref } from 'vue'
import { runtimeClient } from '../../../shared/api/runtime'

const prompt = ref('')
const width = ref(512)
const height = ref(512)
const steps = ref(20)
const busy = ref(false)
const message = useMessage()

async function generate(): Promise<void> {
  busy.value = true
  try {
    await (await runtimeClient()).post('/internal/v1/image-jobs', {
      prompt: prompt.value, model_id: 'no-image-model', width: width.value, height: height.value, steps: steps.value,
    })
  } catch (error) {
    message.warning(error instanceof Error ? error.message : '生图引擎尚不可用')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="page-content">
    <h1 class="page-title">
      图片创作
    </h1>
    <p class="page-subtitle">
      独立管理生图参数、任务与历史作品
    </p>
    <div
      class="chat-layout"
      style="grid-template-columns:minmax(0,1fr) 300px"
    >
      <NCard title="提示词">
        <NInput
          v-model:value="prompt"
          type="textarea"
          :autosize="{ minRows: 5, maxRows: 10 }"
          placeholder="描述想要生成的图片"
        />
        <template #footer>
          <NButton
            type="primary"
            :loading="busy"
            :disabled="!prompt.trim()"
            @click="generate"
          >
            生成图片
          </NButton>
        </template>
      </NCard>
      <NCard title="生成参数">
        <div class="parameter-list">
          <label>宽度 <NInputNumber
            v-model:value="width"
            :min="64"
            :max="2048"
            :step="64"
          /></label>
          <label>高度 <NInputNumber
            v-model:value="height"
            :min="64"
            :max="2048"
            :step="64"
          /></label>
          <label>Steps <NInputNumber
            v-model:value="steps"
            :min="1"
            :max="100"
          /></label>
          <span style="color:#81899a;font-size:13px">尚无已验证的图片生成模型。接入后会在此显示结果画廊和可复用参数。</span>
        </div>
      </NCard>
    </div>
  </section>
</template>

<style scoped>
.parameter-list { display:grid; gap:16px; }
.parameter-list label { display:grid; gap:7px; font-size:13px; }
@media (max-width: 900px) { .chat-layout { grid-template-columns:1fr !important; } }
</style>
