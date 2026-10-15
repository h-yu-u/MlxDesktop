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

watch(
  () => props.imageLimit,
  (limit) => {
    const next = limit > 0 ? props.images.slice(0, limit) : []
    if (next.length !== props.images.length) emit('update:images', next)
  },
)

function handleKeydown(event: KeyboardEvent): void {
  if (
    event.key !== 'Enter' ||
    event.isComposing ||
    event.shiftKey ||
    event.ctrlKey ||
    event.metaKey ||
    event.altKey
  )
    return
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
  emit(
    'update:images',
    props.images.filter((_, current) => current !== index),
  )
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
      >
        {{ image.name }}
      </NTag>
    </div>
    <NInput
      v-model:value="draftValue"
      type="textarea"
      :autosize="{ minRows: 2, maxRows: 6 }"
      placeholder="给 MLX Studio 发送消息"
      aria-label="消息内容"
      :bordered="false"
      @keydown="handleKeydown"
    />
    <div class="composer-actions">
      <div class="composer-tools">
        <NTooltip>
          <template #trigger>
            <span
              ><NButton
                quaternary
                circle
                class="attachment-add"
                aria-label="添加图片附件"
                :disabled="busy || imageLimit === 0 || images.length >= imageLimit"
                @click="imageInput?.click()"
                ><StudioIcon name="plus" :size="23" /></NButton
            ></span>
          </template>
          {{ imageLimit ? '添加图片附件' : '请先选择支持图片输入的模型' }}
        </NTooltip>
        <NTooltip>
          <template #trigger>
            <span
              ><NButton
                quaternary
                class="image-attachment"
                :disabled="busy || imageLimit === 0 || images.length >= imageLimit"
                @click="imageInput?.click()"
                ><StudioIcon name="image" :size="16" />图片<span v-if="images.length">
                  ({{ images.length }}/{{ imageLimit }})</span
                ></NButton
              ></span
            >
          </template>
          {{ imageLimit ? `最多添加 ${imageLimit} 张图片` : '当前模型不支持图片输入' }}
        </NTooltip>
      </div>
      <input
        ref="imageInput"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        hidden
        @change="addImages"
      />
      <div class="composer-send">
        <slot name="model" />
        <NButton v-if="generating ?? busy" type="warning" @click="emit('cancel')">
          停止生成
        </NButton>
        <NButton
          v-else
          type="primary"
          circle
          aria-label="发送"
          title="发送 · Enter"
          class="send-button"
          :loading="busy"
          :disabled="busy || (!draft.trim() && !images.length)"
          @click="submit()"
        >
          <StudioIcon name="up" :size="20" /><span class="send-label">发送</span>
        </NButton>
      </div>
    </div>
  </div>
</template>

<style scoped src="./ChatComposer.styles.css"></style>
