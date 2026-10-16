<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NInput, NSelect, NSpace } from 'naive-ui'
import { modeOptions, type CodingMode } from '../domain/status'
defineProps<{
  models: { label: string; value: string }[]
  modelId: string
  mode: CodingMode
  ready: boolean
  busy: boolean
  pending: boolean
  enabled: boolean
  currentSessionActive: boolean
}>()
const emit = defineEmits<{
  model: [id: string]
  mode: [mode: CodingMode]
  submit: [text: string, clear: () => void]
  steer: [text: string, clear: () => void]
  queue: [text: string, clear: () => void]
  stop: []
}>()
const text = ref('')
function submit(): void {
  if (text.value.trim())
    emit('submit', text.value, () => {
      text.value = ''
    })
}
</script>
<template>
  <div class="coding-composer">
    <NInput
      v-model:value="text"
      type="textarea"
      :autosize="{ minRows: 2, maxRows: 7 }"
      placeholder="描述需求，或补充当前任务（⌘/Ctrl + Enter 发送）"
      :input-props="{ 'aria-label': '开发任务' }"
      :disabled="!enabled || pending"
      @keydown.meta.enter.prevent="submit"
      @keydown.ctrl.enter.prevent="submit"
    />
    <NSpace align="center" justify="space-between">
      <NSpace
        ><NSelect
          :value="modelId"
          :options="models"
          :disabled="busy || pending"
          style="width: 220px"
          aria-label="Coding 模型"
          @update:value="emit('model', $event)" /><NSelect
          :value="mode"
          :options="modeOptions"
          :disabled="busy || pending"
          style="width: 135px"
          aria-label="开发模式"
          @update:value="emit('mode', $event)"
      /></NSpace>
      <NSpace
        ><NButton
          v-if="currentSessionActive"
          :disabled="pending || !text.trim()"
          @click="
            emit('steer', text, () => {
              text = ''
            })
          "
          >补充当前任务</NButton
        ><NButton
          v-if="busy"
          :disabled="pending || !ready || !text.trim()"
          @click="
            emit('queue', text, () => {
              text = ''
            })
          "
          >接下来再做</NButton
        ><NButton v-if="busy" :disabled="pending" @click="emit('stop')">停止任务</NButton
        ><NButton
          v-else
          type="primary"
          :disabled="!ready || !enabled || pending || !text.trim()"
          @click="submit"
          >发送</NButton
        ></NSpace
      >
    </NSpace>
    <small>{{
      mode === 'develop' ? '受管读写；执行命令需逐次审批' : '只读工具；不开放通用命令'
    }}</small>
  </div>
</template>
<style scoped>
.coding-composer {
  padding: 16px 24px;
  border-top: 1px solid var(--line);
  display: grid;
  gap: 12px;
}
small {
  color: var(--muted);
  font-size: 11px;
}
</style>
