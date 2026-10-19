<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { NAlert, NButton, NDrawer, NDrawerContent, NInput, NSelect, NSpace, NCard } from 'naive-ui'
import type { ExtensionSelection } from '@mlx-studio/api-client'
import { createAgentChat } from '../configuration'
import CapabilityPicker from './CapabilityPicker.vue'
import ArtifactLinks from './ArtifactLinks.vue'
const props = defineProps<{ text?: string; disabled?: boolean }>()
const state = createAgentChat(),
  open = ref(false),
  selection = ref<ExtensionSelection>({ skillIds: [], toolIds: [] })
async function show() {
  open.value = true
  if (!state.text.value) state.text.value = props.text ?? ''
  await state.load()
}
onUnmounted(state.dispose)
</script>
<template>
  <NButton size="small" :disabled="disabled" @click="show">工具助手</NButton>
  <NDrawer v-model:show="open" width="min(680px, 100vw)"
    ><NDrawerContent title="聊天 · 工具助手" closable>
      <NSpace vertical>
        <p>
          独立的工具会话，可使用明确选择的 MCP 与本地创作工具。最多 48 次工具调用、4
          次媒体生成，运行上限 20 分钟。
        </p>
        <NSpace
          ><NSelect
            :value="state.sessionId.value"
            :disabled="state.pending.value"
            style="width: 320px"
            :options="
              state.sessions.value.map((session) => ({ label: session.title, value: session.id }))
            "
            @update:value="state.open"
          /><NButton :disabled="state.pending.value || !!state.active.value" @click="state.create"
            >新建工具会话</NButton
          ></NSpace
        >
        <NSelect
          v-model:value="state.modelId.value"
          :options="state.models.value"
          :disabled="!!state.active.value || state.pending.value"
          placeholder="选择支持工具调用的文字模型"
        />
        <CapabilityPicker
          :scope="{ workspace: 'chat', kind: 'session', scopeId: 'agent-default' }"
          mode="develop"
          agent
          :disabled="!!state.active.value || state.pending.value"
          @change="selection = $event"
        />
        <NAlert v-if="state.error.value" type="error">{{ state.error.value }}</NAlert>
        <NAlert v-if="state.active.value" type="info"
          >任务状态：{{ state.active.value.status }}</NAlert
        >
        <NCard
          v-for="event in state.snapshot.value?.events.filter((event) =>
            [
              'run.started',
              'assistant.message',
              'tool.started',
              'tool.settled',
              'tool.finished',
              'skill.loaded',
            ].includes(event.type),
          )"
          :key="event.seq"
          size="small"
          :title="event.type"
        >
          <pre style="white-space: pre-wrap; margin: 0">{{ event.text }}</pre>
          <ArtifactLinks :data="event.data" />
        </NCard>
        <NCard
          v-for="approval in state.snapshot.value?.approvals.filter(
            (item) => item.status === 'pending',
          )"
          :key="approval.id"
          title="操作审批"
          size="small"
          ><p>{{ approval.command }}</p>
          <pre style="white-space: pre-wrap">{{
            JSON.stringify(approval.parameters, null, 2)
          }}</pre>
          <NSpace
            ><NButton :disabled="state.pending.value" @click="state.resolve(approval.id, false)"
              >拒绝</NButton
            ><NButton
              type="primary"
              :disabled="state.pending.value"
              @click="state.resolve(approval.id, true)"
              >仅允许这次</NButton
            ></NSpace
          ></NCard
        >
        <NInput
          v-model:value="state.text.value"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 8 }"
          placeholder="描述需要工具完成的任务"
          :disabled="state.pending.value"
          aria-label="工具助手任务"
        />
        <NSpace
          ><NButton v-if="state.active.value" @click="state.cancel">停止任务</NButton
          ><NButton
            v-else
            type="primary"
            :loading="state.pending.value"
            :disabled="
              !state.modelId.value || !state.text.value.trim() || !selection.toolIds.length
            "
            @click="state.send(selection)"
            >使用所选工具执行</NButton
          ></NSpace
        >
      </NSpace>
    </NDrawerContent></NDrawer
  >
</template>
