<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { NButton, NPopover, NSelect, NSpace, NAlert, NInput } from 'naive-ui'
import type { ExtensionScope, ExtensionSelection } from '@mlx-studio/api-client'
import { useModelDirectory } from '../../models'
import { createCapabilitySelection } from '../configuration'
const props = defineProps<{
  scope: ExtensionScope
  mode?: 'analyze' | 'develop' | 'review'
  disabled?: boolean
  agent?: boolean
}>()
const emit = defineEmits<{ change: [selection: ExtensionSelection] }>()
const directory = useModelDirectory()
const imageModels = computed(() =>
  directory.items
    .filter((model) => model.outputModalities.includes('image'))
    .map((model) => ({ label: model.displayName, value: model.id })),
)
const speechModels = computed(() =>
  directory.items
    .filter((model) => model.outputModalities.includes('audio'))
    .map((model) => ({ label: model.displayName, value: model.id })),
)
const media = computed(() => state.selection.value.mediaBindings ?? {})
function setSpeechMode(value: 'preset' | 'clone'): void {
  media.value.speechMode = value
  if (value === 'preset') media.value.voiceId = undefined
  else media.value.speaker = undefined
}
const state = createCapabilitySelection(),
  open = ref(false)
let generation = 0
watch(
  () => props.scope,
  (scope) => {
    const owner = ++generation
    void state.load(scope).then(() => {
      if (owner === generation && state.catalog.value && !state.error.value)
        emit('change', {
          skillIds: [...state.selection.value.skillIds],
          toolIds: [...state.selection.value.toolIds],
          ...(state.selection.value.mediaBindings
            ? { mediaBindings: { ...state.selection.value.mediaBindings } }
            : {}),
        })
    })
  },
  { immediate: true, deep: true },
)
async function apply(): Promise<void> {
  if (await state.resolve(props.mode, props.agent)) {
    emit('change', {
      skillIds: [...state.selection.value.skillIds],
      toolIds: [...state.selection.value.toolIds],
      ...(state.selection.value.mediaBindings
        ? { mediaBindings: { ...state.selection.value.mediaBindings } }
        : {}),
    })
    open.value = false
  }
}
onUnmounted(state.dispose)
</script>
<template>
  <NPopover v-model:show="open" trigger="click" placement="top-start">
    <template #trigger
      ><NButton size="small" :disabled="disabled"
        >技能与工具（{{
          state.selection.value.skillIds.length + state.selection.value.toolIds.length
        }}）</NButton
      ></template
    >
    <NSpace vertical style="width: 340px">
      <NAlert v-if="state.error.value" type="error">{{ state.error.value }}</NAlert>
      <label
        >技能<NSelect
          v-model:value="state.selection.value.skillIds"
          multiple
          :loading="state.pending.value"
          :options="
            state.skills.value.map((skill) => ({
              label: skill.name + (skill.enabled ? '' : '（已停用）'),
              value: skill.id,
              disabled: !skill.enabled,
            }))
          "
          placeholder="选择本次技能"
      /></label>
      <template v-if="scope.workspace === 'coding' || agent">
        <label
          >工具<NSelect
            v-model:value="state.selection.value.toolIds"
            multiple
            :options="[
              ...state.tools.value.map((tool) => ({
                label: tool.label,
                value: tool.id,
                disabled: tool.disabled || (mode !== 'develop' && tool.risk !== 'read'),
              })),
              ...(state.catalog.value?.builtinTools ?? []).map((tool) => ({
                label: tool.originalName === 'image_generate' ? '本地图片生成' : '本地语音合成',
                value: tool.id,
                disabled: mode !== 'develop',
              })),
            ]"
            placeholder="选择已授权工具"
        /></label>
        <label v-if="state.selection.value.toolIds.includes('builtin:image_generate')"
          >图片模型<NSelect
            v-model:value="media.imageModelId"
            :options="imageModels"
            placeholder="选择已安装图片模型"
        /></label>
        <template v-if="state.selection.value.toolIds.includes('builtin:image_generate')">
          <label
            >图片模式<NSelect
              v-model:value="media.imageMode"
              :options="[
                { label: '文字生成', value: 'generate' },
                { label: '编辑参考图', value: 'edit' },
                { label: '局部重绘', value: 'inpaint' },
              ]"
          /></label>
          <label v-if="media.imageMode === 'edit' || media.imageMode === 'inpaint'"
            >受管参考图 ID<NSelect
              v-model:value="media.imageReferenceIds"
              multiple
              tag
              filterable
              :options="[]"
              placeholder="选择已导入的参考图 ID"
          /></label>
          <label v-if="media.imageMode === 'inpaint'"
            >受管遮罩 ID<NInput v-model:value="media.imageMaskId"
          /></label>
        </template>
        <template v-if="state.selection.value.toolIds.includes('builtin:speech_generate')">
          <label
            >语音模型<NSelect v-model:value="media.speechModelId" :options="speechModels"
          /></label>
          <label
            >语音模式<NSelect
              :value="media.speechMode"
              :options="[
                { label: '预设音色', value: 'preset' },
                { label: '已保存参考音色', value: 'clone' },
              ]"
              @update:value="setSpeechMode"
          /></label>
          <label v-if="media.speechMode === 'preset'"
            >Speaker<NInput v-model:value="media.speaker" placeholder="模型支持的 speaker 名称"
          /></label>
          <label v-else-if="media.speechMode === 'clone'"
            >音色 ID<NInput v-model:value="media.voiceId" placeholder="语音创作音色库中的已授权 ID"
          /></label>
        </template>
      </template>
      <small>仅支持技能指令与参考资源；脚本执行未接入。配置更新下次任务生效。</small>
      <small v-if="state.preview.value"
        >工具 {{ state.preview.value.totalToolCount }} / 16 · 预计上下文
        {{ state.preview.value.estimatedContextTokens }} tokens</small
      >
      <NSpace
        ><NButton size="small" @click="state.saveDefault"
          >保存为{{ scope.kind === 'project' ? '项目' : '工作区' }}默认</NButton
        ><NButton size="small" type="primary" @click="apply">应用本次选择</NButton></NSpace
      >
      <RouterLink to="/settings/extensions/skills">管理扩展能力</RouterLink>
    </NSpace>
  </NPopover>
</template>
