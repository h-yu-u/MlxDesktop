import { defineStore } from 'pinia'
import { ref } from 'vue'
import { open } from '@tauri-apps/plugin-dialog'
import { runtimeClient } from '../../../shared/api/runtime'

export interface ModelView {
  id: string
  displayName: string
  source: string
  engine: string
  task: string
  state: string
  localPath: string
}

export const useModelsStore = defineStore('models', () => {
  const items = ref<ModelView[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      items.value = mapModels(await (await runtimeClient()).get('/internal/v1/models'))
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '读取模型列表失败'
    } finally {
      loading.value = false
    }
  }

  async function importFolder(): Promise<void> {
    const path = await open({ directory: true, multiple: false, title: '选择模型目录' })
    if (!path) return
    await (await runtimeClient()).post('/internal/v1/models/import', { path })
    await refresh()
  }

  async function pullModel(repoId: string): Promise<void> {
    await (await runtimeClient()).post('/internal/v1/models/pull', { repo_id: repoId })
    await refresh()
  }

  async function deleteFiles(id: string): Promise<void> {
    await (await runtimeClient()).delete(
      `/internal/v1/models/${encodeURIComponent(id)}/files?confirm=true`,
    )
    await refresh()
  }

  async function load(id: string): Promise<void> {
    await (await runtimeClient()).post(`/internal/v1/models/${encodeURIComponent(id)}/load`)
    await refresh()
  }

  async function unregister(id: string): Promise<void> {
    await (await runtimeClient()).delete(`/internal/v1/models/${encodeURIComponent(id)}/registration`)
    await refresh()
  }

  return { items, loading, error, refresh, importFolder, pullModel, deleteFiles, load, unregister }
})

function mapModels(value: unknown): ModelView[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (typeof item !== 'object' || item === null) return []
    const fields = item as Record<string, unknown>
    if (typeof fields.id !== 'string') return []
    return [{
      id: fields.id,
      displayName: typeof fields.displayName === 'string' ? fields.displayName : 'Unknown model',
      source: typeof fields.source === 'string' ? fields.source : 'unknown',
      engine: typeof fields.engine === 'string' ? fields.engine : 'unknown',
      task: typeof fields.task === 'string' ? fields.task : 'unknown',
      state: typeof fields.state === 'string' ? fields.state : 'available',
      localPath: typeof fields.localPath === 'string' ? fields.localPath : '',
    }]
  })
}
