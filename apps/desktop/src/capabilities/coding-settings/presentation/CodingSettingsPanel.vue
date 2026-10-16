<script setup lang="ts">
import { onMounted } from 'vue'
import { NAlert, NButton, NCard, NFormItem, NInputNumber, NSelect } from 'naive-ui'
import { useCodingSettings } from '../store'
const coding = useCodingSettings()
onMounted(() => {
  void coding.load()
})
</script>
<template>
  <NCard title="Coding" style="margin-top: 16px">
    <NAlert v-if="coding.error" type="error">{{ coding.error }}</NAlert>
    <NFormItem label="默认 Coding 模型（与聊天独立）"
      ><NSelect
        v-model:value="coding.settings.defaultModelId"
        :options="coding.models"
        :disabled="coding.pending"
        aria-label="默认 Coding 模型"
    /></NFormItem>
    <NFormItem label="上下文预算（Token）"
      ><NInputNumber
        v-model:value="coding.settings.contextBudget"
        :min="4096"
        :max="32768"
        :step="4096"
        :disabled="coding.pending"
        aria-label="Coding 上下文预算"
    /></NFormItem>
    <NButton :loading="coding.pending" @click="coding.save">保存 Coding 设置</NButton>
  </NCard>
</template>
