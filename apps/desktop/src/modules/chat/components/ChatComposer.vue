<script setup lang="ts">
import { NButton, NInput, NTag, NTooltip } from 'naive-ui'
import { computed, ref, watch } from 'vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'

const props = defineProps<{
  busy: boolean
  generating?: boolean
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

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.isComposing || event.shiftKey || event.ctrlKey || event.metaKey || event.altKey) return
  event.preventDefault()
  submit()
}

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
    <div
      v-if="images.length"
      class="attachment-list"
    >
      <NTag
        v-for="(image, index) in images"
        :key="`${image.name}-${image.size}-${index}`"
        closable
        size="small"
        @close="removeImage(index)"
      >
        {{ image.name }}
      </NTag>
    </div>
    <NInput
      v-model:value="draftValue"
      type="textarea"
      :autosize="{ minRows: 2, maxRows: 6 }"
      placeholder="输入消息，开始与 AI 对话…"
      aria-label="消息内容"
      :bordered="false"
      @keydown="handleKeydown"
    />
    <div class="composer-actions">
      <div class="composer-tools">
        <NTooltip>
          <template #trigger>
            <span><NButton
              secondary
              class="attachment-add"
              aria-label="添加图片附件"
              :disabled="busy || imageLimit === 0 || images.length >= imageLimit"
              @click="imageInput?.click()"
            ><StudioIcon
              name="plus"
              :size="23"
            /></NButton></span>
          </template>
          {{ imageLimit ? '添加图片附件' : '请先选择支持图片输入的模型' }}
        </NTooltip>
        <NTooltip>
          <template #trigger>
            <span><NButton
              secondary
              :disabled="busy || imageLimit === 0 || images.length >= imageLimit"
              @click="imageInput?.click()"
            ><StudioIcon
              name="image"
              :size="16"
            />图片<span v-if="images.length"> ({{ images.length }}/{{ imageLimit }})</span></NButton></span>
          </template>
          {{ imageLimit ? `最多添加 ${imageLimit} 张图片` : '当前模型不支持图片输入' }}
        </NTooltip>
        <NTooltip>
          <template #trigger>
            <span><NButton
              secondary
              disabled
            ><StudioIcon
              name="paperclip"
              :size="16"
            />文件</NButton></span>
          </template>文件解析尚未开放
        </NTooltip>
        <NTooltip>
          <template #trigger>
            <span><NButton
              secondary
              disabled
            ><StudioIcon
              name="globe"
              :size="16"
            />联网</NButton></span>
          </template>联网检索尚未开放
        </NTooltip>
      </div>
      <input
        ref="imageInput"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        hidden
        @change="addImages"
      >
      <div class="composer-send">
        <span class="composer-hint">Enter 发送 · Shift + Enter 换行</span>
        <NButton
          v-if="generating ?? busy"
          type="warning"
          @click="emit('cancel')"
        >
          停止生成
        </NButton>
        <NButton
          v-else
          type="primary"
          class="send-button"
          :loading="busy"
          :disabled="busy || (!draft.trim() && !images.length)"
          @click="submit()"
        >
          <StudioIcon
            name="send"
            :size="21"
          />发送
        </NButton>
      </div>
    </div>
  </div>
</template>
