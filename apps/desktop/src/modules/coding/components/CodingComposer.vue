<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NSelect, NSpace } from 'naive-ui'
import ComposerShell from '../../../shared/ui/ComposerShell.vue'
import { codingPrimary, type ComposerAction } from '../../../shared/ui/composer-policy'
import { modeOptions, type CodingMode } from '../domain/status'
const props = defineProps<{
  modelValue: string
  models: { label: string; value: string }[]
  modelId: string
  mode: CodingMode
  ready: boolean
  busy: boolean
  pending: boolean
  enabled: boolean
  currentSessionActive: boolean
  activeStatus?: string
}>()
const emit = defineEmits<{
  'update:modelValue': [text: string]
  model: [id: string]
  mode: [mode: CodingMode]
  submit: []
  steer: []
  queue: []
  stop: []
}>()
const primary = computed(() =>
  codingPrimary({
    text: props.modelValue,
    enabled: props.enabled,
    ready: props.ready,
    pending: props.pending,
    busy: props.busy,
    current: props.currentSessionActive,
    status: props.activeStatus,
  }),
)
function act(action: ComposerAction): void {
  if (action === 'cancel') emit('stop')
  else if (primary.value.enabled) {
    if (action === 'submit') emit('submit')
    if (action === 'queue') emit('queue')
    if (action === 'steer') emit('steer')
  }
}
</script>
<template>
  <ComposerShell
    class="coding-composer"
    :model-value="modelValue"
    :primary="primary"
    shortcut="modifier-enter"
    label="开发任务"
    placeholder="描述需求，或补充当前任务（⌘/Ctrl + Enter）"
    :input-disabled="!enabled"
    @update:model-value="emit('update:modelValue', $event)"
    @action="act"
  >
    <template #tools
      ><NSpace
        ><NSelect
          :value="modelId"
          :options="models"
          :disabled="busy || pending"
          style="width: 220px; max-width: 100%"
          aria-label="Coding 模型"
          @update:value="emit('model', $event)"
        /><NSelect
          :value="mode"
          :options="modeOptions"
          :disabled="busy || pending"
          style="width: 135px"
          aria-label="开发模式"
          @update:value="emit('mode', $event)"
        /><NButton
          v-if="busy"
          :disabled="pending || activeStatus === 'cancelling'"
          @click="emit('stop')"
          >停止任务</NButton
        ></NSpace
      ></template
    >
    <template #context><slot name="capabilities" /></template>
    <template #hint
      ><small>{{
        mode === 'develop' ? '受管读写；执行命令需逐次审批' : '只读工具；不开放通用命令'
      }}</small></template
    >
  </ComposerShell>
</template>
<style scoped>
.coding-composer {
  padding: 16px 24px;
  border-top: 1px solid var(--line);
}
small {
  color: var(--muted);
  font-size: 12px;
}
</style>
