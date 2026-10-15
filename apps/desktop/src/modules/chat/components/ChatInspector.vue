<script setup lang="ts">
import { NButton, NCollapse, NCollapseItem, NSlider, NTooltip } from 'naive-ui'
import NumericParameterField from '../../../shared/ui/NumericParameterField.vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
interface SelectedModel {
  displayName: string
  engine: string
  inputModalities: string[]
  contextLength?: number | null
}
defineProps<{
  clearing: boolean
  busy: boolean
  messageCount: number
  selectedModel?: SelectedModel
  runtime: { error: string | null; info: Record<string, unknown>; uptime: string; diskFree: string }
}>()
const maxTokens = defineModel<number>('maxTokens', { default: 4096 })
const temperature = defineModel<number>('temperature', { default: 0.7 })
const emit = defineEmits<{ clear: []; export: []; reset: [] }>()
function reset(): void {
  emit('reset')
}
</script>

<template>
  <aside class="chat-inspector" aria-label="模型和会话设置">
    <section class="panel inspector-card model-settings">
      <div class="inspector-heading">
        <h2><StudioIcon name="settings" :size="23" />模型设置</h2>
        <NButton text size="tiny" :disabled="busy" @click="reset"> 重置 </NButton>
      </div>
      <NumericParameterField
        v-model="maxTokens"
        label="最大输出长度"
        input-id="max-tokens"
        :min="64"
        :max="8192"
        :step="64"
        :disabled="busy"
      />
      <NumericParameterField
        v-model="temperature"
        label="温度 (Temperature)"
        input-id="temperature"
        :min="0"
        :max="2"
        :step="0.1"
        :precision="1"
        :disabled="busy"
      />
      <NTooltip>
        <template #trigger>
          <div class="parameter-control unavailable-parameter">
            <div class="parameter-label">
              <span>Top P</span><span class="parameter-value">—</span>
            </div>
            <NSlider
              :value="0.9"
              :min="0"
              :max="1"
              :step="0.1"
              disabled
              aria-label="Top P 尚未支持"
            />
          </div>
        </template>
        当前 Runtime 尚未支持 Top P
      </NTooltip>
      <NTooltip>
        <template #trigger>
          <div class="parameter-control unavailable-parameter">
            <div class="parameter-label">
              <span>重复惩罚</span><span class="parameter-value">—</span>
            </div>
            <NSlider :value="1" :min="0" :max="2" disabled aria-label="重复惩罚尚未支持" />
          </div>
        </template>
        当前 Runtime 尚未支持重复惩罚
      </NTooltip>
      <NCollapse class="advanced-settings">
        <NCollapseItem title="高级参数" name="advanced">
          <p>引擎：{{ selectedModel?.engine ?? '—' }}</p>
          <p>输入：{{ selectedModel?.inputModalities.join(' · ') ?? '—' }}</p>
          <p class="muted">Top P 和重复惩罚暂未开放。</p>
        </NCollapseItem>
      </NCollapse>
    </section>
    <section class="panel inspector-card session-info">
      <div class="inspector-heading">
        <h2><StudioIcon name="info" :size="22" />会话信息</h2>
      </div>
      <dl>
        <div>
          <dt>模型名称</dt>
          <dd :title="selectedModel?.displayName">
            {{ selectedModel?.displayName ?? '未选择' }}
          </dd>
        </div>
        <div>
          <dt>运行时</dt>
          <dd>
            <span v-if="!runtime.error && runtime.info.state" class="status-dot" />{{
              runtime.error ? '未连接' : (runtime.info.state ?? '连接中')
            }}
          </dd>
        </div>
        <div>
          <dt>协议版本</dt>
          <dd>{{ runtime.info.protocol_version ?? '—' }}</dd>
        </div>
        <div>
          <dt>上下文长度</dt>
          <dd>{{ selectedModel?.contextLength?.toLocaleString() ?? '—' }}</dd>
        </div>
        <div>
          <dt>已用时长</dt>
          <dd>{{ runtime.uptime }}</dd>
        </div>
        <div>
          <dt>可用磁盘</dt>
          <dd>{{ runtime.diskFree }}</dd>
        </div>
      </dl>
    </section>
    <section class="panel inspector-actions">
      <NButton
        secondary
        :loading="clearing"
        :disabled="busy || !messageCount"
        @click="$emit('clear')"
      >
        <StudioIcon name="trash" :size="17" />清空对话
      </NButton>
      <NButton secondary :disabled="busy || !messageCount" @click="$emit('export')">
        <StudioIcon name="download" :size="17" />导出对话
      </NButton>
    </section>
  </aside>
</template>

<style scoped src="./ChatInspector.styles.css"></style>
