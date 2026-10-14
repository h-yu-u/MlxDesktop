import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { components } from '@mlx-studio/api-client'
import { open } from '@tauri-apps/plugin-dialog'
import { runtimeClient } from '../../../shared/api/runtime'

export type HubModelOption = components['schemas']['HubModelOption']

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

  const catalog = ref<HubModelOption[]>([])
  const catalogQuery = ref('')
  const catalogLoading = ref(false)
  const catalogError = ref<string | null>(null)
  const selectedRepoId = ref<string | null>(null)
  const selectedHubModel = ref<HubModelOption | null>(null)
  const pullingRepoId = ref<string | null>(null)
  const downloadError = ref<string | null>(null)
  const lastDownloadedRepoId = ref<string | null>(null)
  let catalogRequest = 0

  async function searchCatalog(query = ''): Promise<void> {
    const request = ++catalogRequest
    catalogQuery.value = query.trim().slice(0, 100)
    catalogLoading.value = true
    catalogError.value = null
    try {
      const client = await runtimeClient()
      const result = await client.get(`/internal/v1/models/catalog?query=${encodeURIComponent(catalogQuery.value)}`)
      if (request === catalogRequest) catalog.value = mapCatalog(result)
    } catch (cause) {
      if (request !== catalogRequest) return
      catalog.value = []
      catalogError.value = cause instanceof Error ? cause.message : '读取 Hugging Face 模型失败'
    } finally {
      if (request === catalogRequest) catalogLoading.value = false
    }
  }

  function selectHubModel(repoId: string | null): void {
    selectedRepoId.value = repoId
    selectedHubModel.value = catalog.value.find((item) => item.repo_id === repoId) ?? null
    downloadError.value = null
  }

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

  async function importFolder(): Promise<boolean> {
    const path = await open({ directory: true, multiple: false, title: '选择模型目录' })
    if (!path) return false
    await (await runtimeClient()).post('/internal/v1/models/import', { path })
    await refresh()
    return true
  }

  async function pullModel(): Promise<boolean> {
    const repoId = selectedRepoId.value
    if (!repoId || !selectedHubModel.value || pullingRepoId.value) return false
    if (items.value.some((item) => item.source === 'huggingface' && item.displayName === repoId)) return false
    pullingRepoId.value = repoId
    downloadError.value = null
    lastDownloadedRepoId.value = null
    try {
      await (await runtimeClient()).post('/internal/v1/models/pull', { repo_id: repoId })
      lastDownloadedRepoId.value = repoId
      await refresh()
      return true
    } catch (cause) {
      downloadError.value = cause instanceof Error ? cause.message : '模型下载失败，请重试'
      return false
    } finally { pullingRepoId.value = null }
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

  return {
    items, loading, error, refresh, importFolder, pullModel, deleteFiles, load, unregister,
    catalog, catalogQuery, catalogLoading, catalogError, searchCatalog, selectHubModel,
    selectedRepoId, selectedHubModel, pullingRepoId, downloadError, lastDownloadedRepoId,
  }
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

function mapCatalog(value: unknown): HubModelOption[] {
  if (!Array.isArray(value)) throw new Error('模型目录响应格式不正确，请重试')
  return value.flatMap((item: unknown) => {
    if (typeof item !== 'object' || item === null) return []
    const fields = item as Record<string, unknown>
    if (typeof fields.repo_id !== 'string' || !fields.repo_id.includes('/')) return []
    return [{
      repo_id: fields.repo_id,
      downloads: typeof fields.downloads === 'number' ? fields.downloads : 0,
      likes: typeof fields.likes === 'number' ? fields.likes : 0,
      task: typeof fields.task === 'string' ? fields.task : null,
      updated_at: typeof fields.updated_at === 'string' ? fields.updated_at : null,
    }]
  })
}
