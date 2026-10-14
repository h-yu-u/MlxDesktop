<script setup lang="ts">
import { NAlert, NButton, NInput, NInputNumber, NSelect } from 'naive-ui'
import { computed } from 'vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import type { ModelView } from '../../models/stores/models.store'
import type { ImageDraft } from '../domain/image-state'

const props = defineProps<{ form: ImageDraft; models: ModelView[]; locked: boolean; submitting: boolean }>()
const emit = defineEmits<{ 'update:form': [value: ImageDraft]; generate: [] }>()
const options = computed(() => props.models.map((model) => ({ label: model.source === 'builtin' ? '开发测试模型 · 模拟图片' : model.displayName, value: model.id })))
const simulated = computed(() => props.models.find((model) => model.id === props.form.modelId)?.source === 'builtin')
const sizes = [{ label: '1:1', width: 512, height: 512 }, { label: '4:3', width: 768, height: 576 }, { label: '16:9', width: 1024, height: 576 }, { label: '9:16', width: 576, height: 1024 }]
function update<K extends keyof ImageDraft>(key: K, value: ImageDraft[K]): void { emit('update:form', { ...props.form, [key]: value }) }
function setSize(width: number, height: number): void { emit('update:form', { ...props.form, width, height }) }
</script>

<template>
  <section
    class="panel image-controls"
    aria-label="图片生成参数"
  >
    <div class="control-title">
      <StudioIcon
        name="settings"
        :size="20"
      /><h2>创作设置</h2>
    </div>
    <label for="image-model">生图模型</label>
    <NSelect
      :value="form.modelId"
      :options="options"
      :disabled="locked"
      :input-props="{ id: 'image-model', 'aria-label': '生图模型' }"
      placeholder="选择本地生图模型"
      @update:value="update('modelId', $event)"
    />
    <RouterLink
      to="/models"
      class="model-library-link"
    >
      前往模型库下载或导入 <StudioIcon
        name="arrow"
        :size="14"
      />
    </RouterLink>
    <NAlert
      v-if="simulated"
      type="info"
      :show-icon="false"
      class="simulation-notice"
    >
      开发测试模式：输出模拟图片，用于验证生成和历史流程。
    </NAlert>
    <label for="image-prompt">描述你的画面</label>
    <NInput
      :value="form.prompt"
      type="textarea"
      :autosize="{ minRows: 5, maxRows: 9 }"
      :maxlength="10000"
      :disabled="locked"
      :input-props="{ id: 'image-prompt', 'aria-label': '图片提示词' }"
      placeholder="例如：日落时分的山间湖泊，柔和的粉紫色天空，电影感构图…"
      @update:value="update('prompt', $event)"
    />
    <div class="control-label">
      画面比例
    </div>
    <div class="image-size-presets">
      <NButton
        v-for="size in sizes"
        :key="size.label"
        size="small"
        :type="form.width === size.width && form.height === size.height ? 'primary' : 'default'"
        :secondary="true"
        :disabled="locked"
        :aria-pressed="form.width === size.width && form.height === size.height"
        @click="setSize(size.width, size.height)"
      >
        {{ size.label }}
      </NButton>
    </div>
    <div class="dimension-fields">
      <div>
        <label for="image-width">宽度</label><NInputNumber
          :value="form.width"
          :min="64"
          :max="2048"
          :step="64"
          :disabled="locked"
          :input-props="{ id: 'image-width', 'aria-label': '图片宽度' }"
          @update:value="update('width', $event ?? 512)"
        />
      </div><div>
        <label for="image-height">高度</label><NInputNumber
          :value="form.height"
          :min="64"
          :max="2048"
          :step="64"
          :disabled="locked"
          :input-props="{ id: 'image-height', 'aria-label': '图片高度' }"
          @update:value="update('height', $event ?? 512)"
        />
      </div>
    </div>
    <label for="image-steps">生成步数</label>
    <NInputNumber
      :value="form.steps"
      :min="1"
      :max="100"
      :disabled="locked"
      :input-props="{ id: 'image-steps', 'aria-label': '生成步数' }"
      @update:value="update('steps', $event ?? 20)"
    />
    <div class="seed-heading">
      <label for="image-seed">Seed</label><NButton
        text
        size="tiny"
        :disabled="locked"
        @click="update('seed', null)"
      >
        随机
      </NButton>
    </div>
    <NInputNumber
      :value="form.seed"
      :min="0"
      :max="4294967295"
      :show-button="false"
      :disabled="locked"
      :input-props="{ id: 'image-seed', 'aria-label': '图片 Seed' }"
      placeholder="留空使用随机 Seed"
      @update:value="update('seed', $event)"
    />
    <NButton
      class="generate-image-button"
      type="primary"
      block
      :loading="submitting"
      :disabled="locked || !form.modelId || !form.prompt.trim()"
      @click="emit('generate')"
    >
      <StudioIcon
        name="bolt"
        :size="19"
      />{{ submitting ? '提交任务' : '生成图片' }}
    </NButton>
    <p class="image-save-hint">
      完成后自动保存图片与参数，可随时从作品历史中找回。
    </p>
  </section>
</template>

<style scoped>
.image-controls { padding: 21px; display: flex; flex-direction: column; gap: 10px; }.control-title { display: flex; align-items: center; gap: 10px; color: #9fb2ff; margin-bottom: 8px; }.control-title h2 { color: #eef2fc; font-size: 15px; margin: 0; font-weight: 600; }
.image-controls label, .control-label { font-size: 12px; color: #b7c6dd; margin-top: 7px; }.model-library-link { display: flex; align-items: center; gap: 7px; font-size: 11px; color: #94a7f3; text-decoration: none; }.simulation-notice { margin: 4px 0; font-size: 11px; }
.image-size-presets { display: grid; grid-template-columns: repeat(4, 1fr); gap: 7px; }.image-size-presets .n-button { padding: 0; }.dimension-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }.dimension-fields > div { display: grid; gap: 8px; min-width: 0; }.seed-heading { display: flex; align-items: center; justify-content: space-between; }.seed-heading label { margin: 0; }
.generate-image-button { margin-top: 12px; height: 44px; }.generate-image-button :deep(.n-button__content) { gap: 8px; }.image-save-hint { margin: 0; color: #7f93b0; font-size: 10px; line-height: 1.7; }
</style>
