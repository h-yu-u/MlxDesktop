<script setup lang="ts">
import { NButton, NEmpty, NImage, NProgress, NSkeleton, NSpin, NTag } from 'naive-ui'
import { computed } from 'vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import { isTerminal, type ImageArtifact, type ImageJob } from '../domain/image-state'

const props = defineProps<{ artifact: ImageArtifact | null; url?: string; imageError?: string; job: ImageJob | null; submitting: boolean; cancelling: boolean; saving: boolean; syncError: string | null }>()
defineEmits<{ cancel: []; save: []; reuse: []; retryImage: []; reconnect: [] }>()
const active = computed(() => props.submitting || (!!props.job && !isTerminal(props.job)))
const stateText = computed(() => props.submitting ? '正在提交任务' : ({ queued: '等待生成', preparing: '准备模型', running: '正在生成图片', cancelling: '正在取消', succeeded: '生成完成', failed: '生成失败', cancelled: '已取消生成' })[props.job?.state ?? 'queued'])
</script>

<template>
  <section
    class="panel image-preview"
    aria-label="图片预览与任务状态"
  >
    <div class="preview-heading">
      <h2>
        <StudioIcon
          name="image"
          :size="20"
        />{{ active ? '当前任务' : '作品预览' }}
      </h2><NTag
        v-if="artifact && !active"
        size="small"
        :bordered="false"
        :type="artifact.simulated ? 'warning' : 'success'"
      >
        {{ artifact.simulated ? '模拟输出' : '已自动保存' }}
      </NTag>
    </div>
    <div
      v-if="active"
      class="image-generation-state"
      aria-live="polite"
    >
      <NSpin
        v-if="!syncError"
        size="large"
      />
      <StudioIcon
        v-else
        name="info"
        :size="40"
      />
      <h3>{{ syncError ? '任务状态同步中断' : stateText }}</h3>
      <p>{{ syncError ? '本地任务可能仍在运行，重新连接后可继续查看结果。' : job?.state === 'queued' ? '正在等待当前推理任务结束' : '你可以切换页面，完成后会自动加入作品历史。' }}</p>
      <NProgress
        v-if="job && !isTerminal(job) && !syncError"
        type="line"
        :percentage="job.progress"
        :show-indicator="true"
        :processing="job.state === 'running'"
      />
      <div class="generation-buttons">
        <NButton
          v-if="syncError"
          type="primary"
          secondary
          @click="$emit('reconnect')"
        >
          重新同步
        </NButton><NButton
          v-if="job && !isTerminal(job)"
          secondary
          :loading="cancelling"
          :disabled="cancelling || job.state === 'cancelling'"
          @click="$emit('cancel')"
        >
          取消生成
        </NButton>
      </div>
    </div>
    <template v-else-if="artifact">
      <div class="generated-image-stage">
        <NImage
          v-if="url"
          :src="url"
          :alt="artifact.simulated ? '开发测试生成的模拟图像' : artifact.prompt"
          object-fit="contain"
          :img-props="{ style: 'max-width:100%;max-height:430px;object-fit:contain' }"
        />
        <div
          v-else-if="imageError"
          class="preview-image-error"
        >
          <NEmpty :description="imageError" /><NButton
            secondary
            @click="$emit('retryImage')"
          >
            重新读取图片
          </NButton>
        </div>
        <NSkeleton
          v-else
          width="100%"
          height="340px"
          :sharp="false"
        />
      </div>
      <div class="artifact-details">
        <div class="artifact-model">
          {{ artifact.model_name }}
        </div><p class="artifact-prompt">
          {{ artifact.prompt }}
        </p><div class="artifact-parameters">
          <span>{{ artifact.width }} × {{ artifact.height }}</span><span>{{ artifact.steps }} 步</span><span>Seed {{ artifact.seed }}</span><span>{{ new Date(artifact.created_at * 1000).toLocaleString('zh-CN', { hour12: false }) }}</span>
        </div>
      </div>
      <div class="preview-actions">
        <NButton
          secondary
          :disabled="active"
          @click="$emit('reuse')"
        >
          <StudioIcon
            name="plus"
            :size="16"
          />复用参数
        </NButton><NButton
          type="primary"
          :loading="saving"
          :disabled="!url || saving"
          @click="$emit('save')"
        >
          <StudioIcon
            name="download"
            :size="17"
          />保存图片
        </NButton>
      </div>
    </template>
    <div
      v-else
      class="preview-empty"
    >
      <div class="empty-image-icon">
        <StudioIcon
          name="image"
          :size="44"
        />
      </div><h3>{{ job?.state === 'cancelled' || job?.state === 'failed' ? stateText : '把你的想象，变成画面' }}</h3><p>在左侧描述你的创意，生成的作品会显示在这里。</p><span>本地创作 · 自动留存 · 参数可复用</span>
    </div>
  </section>
</template>

<style scoped>
.image-preview { min-width: 0; padding: 21px; display: flex; flex-direction: column; }.preview-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }.preview-heading h2 { display: flex; align-items: center; gap: 10px; font-size: 15px; margin: 0; font-weight: 600; }.preview-heading svg { color: #a1b5ff; }
.preview-empty, .image-generation-state { flex: 1; min-height: 460px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 24px; }.empty-image-icon { width: 90px; height: 90px; display: grid; place-items: center; border-radius: 25px; color: #8296ed; background: linear-gradient(135deg, #7260b62b, #305f9e24); border: 1px solid #405273; margin-bottom: 22px; }
.preview-empty h3, .image-generation-state h3 { margin: 0 0 10px; font-size: 21px; font-weight: 550; }.preview-empty p, .image-generation-state p { color: #98aac8; font-size: 13px; line-height: 1.8; margin: 0 0 20px; }.preview-empty > span { color: #6d82a3; font-size: 11px; }.image-generation-state .n-spin, .image-generation-state > svg { margin-bottom: 25px; }.image-generation-state .n-progress { width: min(360px, 100%); margin: 4px 0 25px; }.generation-buttons { display: flex; gap: 10px; }
.generated-image-stage { min-height: 300px; flex: 1; display: flex; align-items: center; justify-content: center; padding: 12px; border: 1px solid #2b3b53; border-radius: 11px; background: #101827; overflow: hidden; }.generated-image-stage .n-image { display: flex; max-width: 100%; }.preview-image-error { display: grid; justify-items: center; gap: 18px; padding: 24px; }
.artifact-details { padding: 18px 0; }.artifact-model { font-size: 12px; color: #a4b6db; overflow-wrap: anywhere; }.artifact-prompt { margin: 8px 0 13px; color: #d4deee; font-size: 13px; line-height: 1.8; white-space: pre-wrap; max-height: 110px; overflow: auto; }.artifact-parameters { display: flex; flex-wrap: wrap; gap: 8px 16px; color: #8095b5; font-size: 11px; }.preview-actions { display: flex; justify-content: flex-end; gap: 10px; border-top: 1px solid #2b3950; padding-top: 16px; }.preview-actions :deep(.n-button__content) { gap: 7px; }
@media (max-width: 680px) { .image-preview { padding: 17px; }.preview-empty, .image-generation-state { min-height: 280px; padding: 16px; }.preview-empty h3 { font-size: 18px; }.generated-image-stage { min-height: 220px; padding: 5px; } }
</style>
