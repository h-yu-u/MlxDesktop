<script setup lang="ts">
import { NButton, NInput, NTag } from 'naive-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  busy: boolean
  imageLimit: number
  draft: string
  images: File[]
}>()
const emit = defineEmits<{
  'update:draft': [value: string]
  'update:images': [value: File[]]
  submit: []
  cancel: []
}>()

const imageInput = ref<HTMLInputElement | null>(null)
const draftValue = computed({
  get: () => props.draft,
  set: (value: string) => emit('update:draft', value),
})

watch(() => props.imageLimit, (limit) => {
  const next = limit > 0 ? props.images.slice(0, limit) : []
  if (next.length !== props.images.length) emit('update:images', next)
})

function submit(): void {
  if (props.busy || (!props.draft.trim() && !props.images.length)) return
  emit('submit')
}

function addImages(event: Event): void {
  const input = event.target as HTMLInputElement
  const chosen = Array.from(input.files ?? [])
  emit('update:images', [...props.images, ...chosen].slice(0, props.imageLimit))
  input.value = ''
}

function removeImage(index: number): void {
  emit('update:images', props.images.filter((_, current) => current !== index))
}
</script>

<template>
  <div class="composer">
    <div v-if="images.length" class="attachment-list">
      <NTag
        v-for="(image, index) in images"
        :key="`${image.name}-${image.size}-${index}`"
        closable
        size="small"
        @close="removeImage(index)"
      >{{ image.name }}</NTag>
    </div>
    <NInput
      v-model:value="draftValue"
      type="textarea"
      :autosize="{ minRows: 2, maxRows: 6 }"
      placeholder="输入消息…（本地处理，不会发送到云端）"
      aria-label="消息内容"
      @keydown.enter.exact.prevent="submit"
    />
    <div class="composer-actions">
      <span class="composer-hint">Enter 发送 · Shift + Enter 换行</span>
      <NButton
        v-if="imageLimit > 0"
        secondary
        :disabled="busy || images.length >= imageLimit"
        @click="imageInput?.click()"
      >添加图片 {{ images.length ? `(${images.length}/${imageLimit})` : '' }}</NButton>
      <input
        ref="imageInput"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        hidden
        @change="addImages"
      >
      <NButton v-if="busy" type="warning" @click="emit('cancel')">停止生成</NButton>
      <NButton
        v-else
        type="primary"
        :disabled="!draft.trim() && !images.length"
        @click="submit"
      >发送</NButton>
    </div>
  </div>
</template>

<style scoped>
.attachment-list { display: flex; flex-wrap: wrap; gap: 6px; }
.composer-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.composer-hint { color: #8790a0; font-size: 12px; }
</style>
