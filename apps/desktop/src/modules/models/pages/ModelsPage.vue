<script setup lang="ts">
import { NButton, NCard, NEmpty, NSpin, NTag, useDialog, useMessage } from 'naive-ui'
import { onMounted, ref } from 'vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import HubModelPicker from '../components/HubModelPicker.vue'
import { useModelsStore } from '../stores/models.store'

const store = useModelsStore()
const message = useMessage()
const dialog = useDialog()
const activeAction = ref<string | null>(null)
onMounted(() => { void store.refresh() })

async function importModel(): Promise<void> {
  activeAction.value = 'import'
  try { if (await store.importFolder()) message.success('模型已加入模型库') }
  catch (error) { message.error(error instanceof Error ? error.message : '导入失败') }
  finally { activeAction.value = null }
}

async function actOnModel(action: 'load' | 'unregister', id: string): Promise<void> {
  activeAction.value = `${action}:${id}`
  try {
    await store[action](id)
    message.success(action === 'load' ? '模型已加载' : '已移除模型注册')
  } catch (error) { message.error(error instanceof Error ? error.message : '操作失败') }
  finally { activeAction.value = null }
}

function deleteFiles(modelId: string, name: string): void {
  dialog.warning({
    title: '删除本地模型文件',
    content: `确定删除“${name}”的模型文件吗？此操作不可撤销。`,
    positiveText: '删除文件', negativeText: '取消',
    onPositiveClick: async () => {
      activeAction.value = `delete:${modelId}`
      try { await store.deleteFiles(modelId); message.success('模型文件已删除') }
      catch (error) { message.error(error instanceof Error ? error.message : '删除失败'); return false }
      finally { activeAction.value = null }
    },
  })
}
</script>

<template>
  <section class="page-content models-page">
    <div class="models-heading">
      <div>
        <h1 class="page-title">
          模型库
        </h1><p class="page-subtitle">
          发现、下载和管理你的本地 AI 模型
        </p>
      </div>
      <NButton
        secondary
        :loading="activeAction === 'import'"
        :disabled="!!activeAction"
        @click="importModel"
      >
        <StudioIcon
          name="plus"
          :size="18"
        />导入本地模型
      </NButton>
    </div>
    <HubModelPicker />
    <div class="local-models-heading">
      <h2>本地模型 <span>{{ store.items.length }}</span></h2><NButton
        quaternary
        size="small"
        :loading="store.loading"
        @click="store.refresh"
      >
        刷新列表
      </NButton>
    </div>
    <div
      v-if="store.error"
      role="alert"
      class="model-library-error"
    >
      {{ store.error }}<NButton
        text
        type="primary"
        @click="store.refresh"
      >
        重试
      </NButton>
    </div>
    <NSpin :show="store.loading">
      <div
        v-if="store.items.length"
        class="grid-cards local-model-grid"
      >
        <NCard
          v-for="model in store.items"
          :key="model.id"
          size="small"
          class="local-model-card"
        >
          <div class="local-model-title">
            <div class="local-model-icon">
              <StudioIcon
                name="cube"
                :size="23"
              />
            </div><NTag
              size="small"
              :bordered="false"
              :type="model.state === 'loaded' ? 'success' : 'default'"
            >
              {{ model.source === 'builtin' ? '开发测试' : model.state === 'loaded' ? '已加载' : '本地模型' }}
            </NTag>
          </div>
          <h3>{{ model.displayName }}</h3>
          <div class="local-model-meta">
            <span>{{ model.engine }}</span><span>{{ model.task }}</span>
          </div>
          <p class="local-model-source">
            {{ model.source === 'huggingface' ? 'Hugging Face' : model.source === 'builtin' ? '内置引擎' : '本地导入' }}
          </p>
          <template #footer>
            <div class="local-model-actions">
              <NButton
                size="small"
                type="primary"
                :loading="activeAction === `load:${model.id}`"
                :disabled="!!activeAction"
                @click="actOnModel('load', model.id)"
              >
                加载模型
              </NButton>
              <NButton
                v-if="model.source !== 'builtin'"
                size="small"
                :disabled="!!activeAction"
                @click="actOnModel('unregister', model.id)"
              >
                移除注册
              </NButton>
              <NButton
                v-if="model.source !== 'builtin'"
                size="small"
                type="error"
                quaternary
                :disabled="!!activeAction"
                @click="deleteFiles(model.id, model.displayName)"
              >
                删除文件
              </NButton>
            </div>
          </template>
        </NCard>
      </div>
      <div
        v-else-if="!store.loading && !store.error"
        class="panel empty-state"
      >
        <NEmpty description="还没有本地模型">
          <template #extra>
            <span class="empty-model-hint">从上方下拉列表选择 MLX 模型，开始第一次下载</span>
          </template>
        </NEmpty>
      </div>
    </NSpin>
  </section>
</template>

<style scoped>
.models-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; }.models-heading .page-subtitle { margin-bottom: 0; }.models-heading .n-button :deep(.n-button__content) { gap: 8px; }
.local-models-heading { display: flex; justify-content: space-between; align-items: center; }.local-models-heading h2 { display: flex; align-items: center; gap: 10px; margin: 0; font-size: 17px; font-weight: 600; }.local-models-heading h2 span { display: grid; place-items: center; min-width: 24px; height: 22px; padding: 0 6px; background: #29354a; border-radius: 7px; color: #a2b2cb; font-size: 11px; }
.local-model-grid { margin-top: 17px; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); }.local-model-card { background: linear-gradient(135deg, #202a3c, #192331); border-radius: 12px; }.local-model-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.local-model-icon { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 11px; color: #9bb1ff; background: #34496c55; }
.local-model-card h3 { font-size: 15px; font-weight: 550; margin: 17px 0 10px; overflow-wrap: anywhere; }.local-model-meta { display: flex; flex-wrap: wrap; gap: 7px; }.local-model-meta span { font-size: 10px; color: #a2b4d0; padding: 3px 7px; border-radius: 5px; background: #2a3549; }.local-model-source { font-size: 11px; color: #7e90ae; margin: 13px 0 0; }
.local-model-actions { display: flex; flex-wrap: wrap; gap: 8px; }.model-library-error { display: flex; align-items: center; gap: 12px; color: #f6a6ae; font-size: 13px; padding: 12px 0; }.empty-model-hint { color: #91a2be; font-size: 12px; }
@media (max-width: 680px) { .models-heading { align-items: start; }.models-heading .n-button { font-size: 11px; padding: 0 10px; }.page-title { font-size: 23px; }.page-subtitle { font-size: 12px; }.local-model-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
