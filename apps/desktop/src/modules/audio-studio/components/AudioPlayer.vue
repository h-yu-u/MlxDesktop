<script setup lang="ts">
import { NAlert, NButton, NCard, NEmpty, NSpace, NTag } from 'naive-ui'
import type { AudioArtifact, AudioJob } from '../application/ports'
defineProps<{
  artifact: AudioArtifact | null
  url?: string
  job: AudioJob | null
  busy: boolean
  cancelling: boolean
  saving: boolean
  syncError: string | null
}>()
const emit = defineEmits<{ cancel: []; save: []; reuse: []; retry: []; reconnect: [] }>()
const states: Record<string, string> = {
  queued: '排队中',
  preparing: '加载模型中',
  running: '生成中',
  cancelling: '取消中',
  cancelled: '已取消',
  succeeded: '已完成',
  failed: '生成失败',
}
</script>
<template>
  <NCard title="试听与导出" :bordered="false">
    <NSpace vertical :size="18">
      <div v-if="job" role="status" aria-live="polite">
        <NTag :type="busy ? 'info' : job.state === 'failed' ? 'error' : 'default'">{{
          states[job.state]
        }}</NTag>
        <NButton
          v-if="busy"
          secondary
          size="small"
          :loading="cancelling"
          :disabled="cancelling"
          @click="emit('cancel')"
          >取消生成</NButton
        >
      </div>
      <NAlert v-if="syncError" type="warning"
        >任务同步中断：{{ syncError }}
        <NButton text @click="emit('reconnect')">重新连接</NButton></NAlert
      >
      <template v-if="artifact">
        <NTag v-if="artifact.simulated" type="warning">开发测试音</NTag>
        <div class="waveform" aria-hidden="true">
          <span
            v-for="(peak, index) in artifact.peaks"
            :key="index"
            :style="{ height: `${Math.max(4, peak * 100)}%` }"
          />
        </div>
        <audio
          v-if="url"
          :key="url"
          :src="url"
          controls
          preload="metadata"
          aria-label="生成作品试听"
        />
        <NButton v-else @click="emit('retry')">加载音频</NButton>
        <p class="audio-metadata">
          {{ artifact.duration_seconds.toFixed(1) }} 秒 ·
          {{ (artifact.sample_rate / 1000).toFixed(1) }} kHz · WAV
        </p>
        <p class="audio-text">{{ artifact.text }}</p>
        <NSpace>
          <NButton type="primary" :loading="saving" @click="emit('save')">导出 WAV</NButton>
          <NButton :disabled="busy" @click="emit('reuse')">复用参数</NButton>
        </NSpace>
      </template>
      <NEmpty
        v-else
        :description="busy ? '音频生成后会在这里显示' : '输入文字，开始创作第一段语音'"
      />
    </NSpace>
  </NCard>
</template>
<style scoped>
.waveform {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 100px;
  padding: 14px 0;
}
.waveform span {
  flex: 1;
  border-radius: 3px;
  background: var(--accent, #a3baab);
  min-width: 1px;
}
audio {
  width: 100%;
}
.audio-metadata {
  color: var(--text-muted);
  font-size: 12px;
}
.audio-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 180px;
  overflow-y: auto;
}
</style>
