<script setup lang="ts">
import { NButton, NCollapse, NCollapseItem, NInputNumber, NSlider, NTooltip } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import { useRuntimeStore } from '../../../shared/stores/runtime.store'
import { useChatStore } from '../stores/chat.store'

const store = useChatStore()
const runtime = useRuntimeStore()
const { models, selectedModelId, maxTokens, temperature, state } = storeToRefs(store)
const busy = computed(() => store.busy || store.pending)
const selectedModel = computed(() => models.value.find((model) => model.id === selectedModelId.value))
defineProps<{ clearing: boolean }>()
defineEmits<{ clear: []; export: [] }>()
function reset(): void { maxTokens.value = 512; temperature.value = 0.7 }
</script>

<template>
  <aside
    class="chat-inspector"
    aria-label="模型和会话设置"
  >
    <section class="panel inspector-card model-settings">
      <div class="inspector-heading">
        <h2>
          <StudioIcon
            name="settings"
            :size="23"
          />模型设置
        </h2><NButton
          text
          size="tiny"
          :disabled="busy"
          @click="reset"
        >
          重置
        </NButton>
      </div>
      <div class="parameter-control">
        <div class="parameter-label">
          <label for="max-tokens">最大输出长度</label><NInputNumber
            :value="maxTokens"
            :min="64"
            :max="2048"
            :step="64"
            :show-button="false"
            :disabled="busy"
            :input-props="{ id: 'max-tokens', 'aria-label': '最大输出长度' }"
            @update:value="maxTokens = $event ?? 512"
          />
        </div>
        <NSlider
          v-model:value="maxTokens"
          :min="64"
          :max="2048"
          :step="64"
          :disabled="busy"
          aria-label="最大输出长度"
        />
      </div>
      <div class="parameter-control">
        <div class="parameter-label">
          <label for="temperature">温度 <span>(Temperature)</span></label><NInputNumber
            :value="temperature"
            :min="0"
            :max="2"
            :step="0.1"
            :precision="1"
            :show-button="false"
            :disabled="busy"
            :input-props="{ id: 'temperature', 'aria-label': '温度' }"
            @update:value="temperature = $event ?? 0.7"
          />
        </div>
        <NSlider
          v-model:value="temperature"
          :min="0"
          :max="2"
          :step="0.1"
          :disabled="busy"
          aria-label="温度"
        />
      </div>
      <NTooltip>
        <template #trigger>
          <div class="parameter-control unavailable-parameter">
            <div class="parameter-label">
              <span>Top P</span><span class="parameter-value">—</span>
            </div><NSlider
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
            </div><NSlider
              :value="1"
              :min="0"
              :max="2"
              disabled
              aria-label="重复惩罚尚未支持"
            />
          </div>
        </template>
        当前 Runtime 尚未支持重复惩罚
      </NTooltip>
      <NCollapse class="advanced-settings">
        <NCollapseItem
          title="高级参数"
          name="advanced"
        >
          <p>引擎：{{ selectedModel?.engine ?? '—' }}</p><p>输入：{{ selectedModel?.inputModalities.join(' · ') ?? '—' }}</p><p class="muted">
            Top P 和重复惩罚暂未开放。
          </p>
        </NCollapseItem>
      </NCollapse>
    </section>
    <section class="panel inspector-card session-info">
      <div class="inspector-heading">
        <h2>
          <StudioIcon
            name="info"
            :size="22"
          />会话信息
        </h2>
      </div>
      <dl>
        <div>
          <dt>模型名称</dt><dd :title="selectedModel?.displayName">
            {{ selectedModel?.displayName ?? '未选择' }}
          </dd>
        </div>
        <div>
          <dt>运行时</dt><dd>
            <span
              v-if="!runtime.error && runtime.info.state"
              class="status-dot"
            />{{ runtime.error ? '未连接' : runtime.info.state ?? '连接中' }}
          </dd>
        </div>
        <div><dt>协议版本</dt><dd>{{ runtime.info.protocol_version ?? '—' }}</dd></div>
        <div><dt>上下文长度</dt><dd>{{ selectedModel?.contextLength?.toLocaleString() ?? '—' }}</dd></div>
        <div><dt>已用时长</dt><dd>{{ runtime.uptime }}</dd></div>
        <div><dt>可用磁盘</dt><dd>{{ runtime.diskFree }}</dd></div>
      </dl>
    </section>
    <section class="panel inspector-actions">
      <NButton
        secondary
        :loading="clearing"
        :disabled="busy || !state.messages.length"
        @click="$emit('clear')"
      >
        <StudioIcon
          name="trash"
          :size="17"
        />清空对话
      </NButton>
      <NButton
        secondary
        :disabled="busy || !state.messages.length"
        @click="$emit('export')"
      >
        <StudioIcon
          name="download"
          :size="17"
        />导出对话
      </NButton>
    </section>
  </aside>
</template>
