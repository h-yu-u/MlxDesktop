<script setup lang="ts">
import { NButton, NInput } from 'naive-ui'
import { ref, watch } from 'vue'

const props = defineProps<{ busy: boolean; imageLimit: number }>()
const emit = defineEmits<{ send: [value: string, files: File[]]; cancel: [] }>()
const draft = ref('')
const imageInput = ref<HTMLInputElement | null>(null)
const images = ref<File[]>([])

watch(() => props.imageLimit, (limit) => {
  images.value = limit > 0 ? images.value.slice(0, limit) : []
})

function submit(): void {
  const value = draft.value.trim()
  if (!value && !images.value.length) return
  emit('send', value, images.value)
  draft.value = ''
  images.value = []
}

function addImages(event: Event): void {
  const input = event.target as HTMLInputElement
  const chosen = Array.from(input.files ?? [])
  images.value = [...images.value, ...chosen].slice(0, props.imageLimit)
  input.value = ''
}
</script>

<template>
  <div class="composer">
    <NInput
      v-model:value="draft"
      type="textarea"
      :autosize="{ minRows: 2, maxRows: 6 }"
      placeholder="输入消息…（本地处理，不会发送到云端）"
      aria-label="消息内容"
      @keydown.enter.exact.prevent="submit"
    />
    <div class="composer-actions">
      <span style="color:#8790a0;font-size:12px">Enter 发送 · Shift + Enter 换行</span>
      <NButton
        v-if="imageLimit > 0"
        secondary
        :disabled="busy || images.length >= imageLimit"
        @click="imageInput?.click()"
      >
        添加图片 {{ images.length ? `(${images.length}/${imageLimit})` : '' }}
      </NButton>
      <input
        ref="imageInput"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        hidden
        @change="addImages"
      >
      <NButton
        v-if="busy"
        type="warning"
        @click="emit('cancel')"
      >
        停止生成
      </NButton>
      <NButton
        v-else
        type="primary"
        :disabled="!draft.trim() && !images.length"
        @click="submit"
      >
        发送
      </NButton>
    </div>
  </div>
</template>

<style scoped>
.composer-actions { display:flex; align-items:center; flex-wrap:wrap; gap:8px; }
</style>
