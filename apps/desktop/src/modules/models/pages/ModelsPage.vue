<script setup lang="ts">
import { NButton, NCard, NEmpty, NInput, NSpin, useDialog, useMessage } from 'naive-ui'
import { onMounted, ref } from 'vue'
import { useModelsStore } from '../stores/models.store'

const store = useModelsStore()
const message = useMessage()
const dialog = useDialog()
const repoId = ref('')
const pulling = ref(false)
onMounted(() => { void store.refresh() })

async function importModel(): Promise<void> {
  try { await store.importFolder(); message.success('模型已加入模型库') } catch (error) {
    message.error(error instanceof Error ? error.message : '导入失败')
  }
}

async function pullModel(): Promise<void> {
  if (!repoId.value.trim() || pulling.value) return
  pulling.value = true
  try {
    await store.pullModel(repoId.value.trim())
    repoId.value = ''
    message.success('模型下载完成并已登记')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '模型下载失败')
  } finally {
    pulling.value = false
  }
}

function deleteFiles(modelId: string, name: string): void {
  dialog.warning({
    title: '删除本地模型文件',
    content: `确定删除“${name}”的模型文件吗？此操作不可撤销。`,
    positiveText: '删除文件',
    negativeText: '取消',
    onPositiveClick: async () => {
      try { await store.deleteFiles(modelId); message.success('模型文件已删除') } catch (error) {
        message.error(error instanceof Error ? error.message : '删除失败')
      }
    },
  })
}
</script>

<template>
  <section class="page-content">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px">
      <div>
        <h1 class="page-title">
          模型库
        </h1><p class="page-subtitle">
          扫描本地模型的静态元数据，不会执行模型目录中的代码
        </p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end">
        <NInput
          v-model:value="repoId"
          placeholder="Hugging Face 仓库 ID"
          style="width:240px"
          @keydown.enter="pullModel"
        />
        <NButton
          :loading="pulling"
          :disabled="!repoId.trim()"
          @click="pullModel"
        >
          下载模型
        </NButton>
        <NButton
          type="primary"
          @click="importModel"
        >
          导入模型文件夹
        </NButton>
      </div>
    </div>
    <p
      v-if="store.error"
      role="alert"
      style="color:#c24148"
    >
      {{ store.error }}
    </p>
    <NSpin :show="store.loading">
      <div
        v-if="store.items.length"
        class="grid-cards"
      >
        <NCard
          v-for="model in store.items"
          :key="model.id"
          :title="model.displayName"
          size="small"
        >
          <div style="display:grid;gap:8px;color:#757d8d;font-size:13px">
            <span>{{ model.engine }} · {{ model.task }}</span>
            <span>{{ model.state }} · {{ model.source }}</span>
          </div>
          <template #footer>
            <div style="display:flex;gap:8px">
              <NButton
                size="small"
                type="primary"
                @click="store.load(model.id)"
              >
                加载
              </NButton>
              <NButton
                v-if="model.source !== 'builtin'"
                size="small"
                @click="store.unregister(model.id)"
              >
                移除注册
              </NButton>
              <NButton
                v-if="model.source !== 'builtin'"
                size="small"
                type="error"
                @click="deleteFiles(model.id, model.displayName)"
              >
                删除文件
              </NButton>
            </div>
          </template>
        </NCard>
      </div>
      <div
        v-else
        class="panel empty-state"
      >
        <NEmpty description="模型库为空" />
      </div>
    </NSpin>
  </section>
</template>
