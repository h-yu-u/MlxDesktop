import { ref } from 'vue'
import type { CodingSettings, ModelSummary } from '@mlx-studio/api-client'
export interface CodingSettingsGateway {
  load(): Promise<CodingSettings>
  save(value: CodingSettings): Promise<CodingSettings>
  models(): Promise<ModelSummary[]>
}
export function createCodingSettingsController(gateway: CodingSettingsGateway) {
  const settings = ref<CodingSettings>({
      id: 'coding',
      defaultModelId: '',
      contextBudget: 32768,
      maxRepairRounds: 2,
    }),
    models = ref<{ label: string; value: string }[]>([]),
    pending = ref(false),
    error = ref<string | null>(null)
  async function run(action: () => Promise<void>): Promise<void> {
    pending.value = true
    error.value = null
    try {
      await action()
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : 'Coding 设置请求失败'
    } finally {
      pending.value = false
    }
  }
  async function load(): Promise<void> {
    await run(async () => {
      const [value, items] = await Promise.all([gateway.load(), gateway.models()])
      settings.value = value
      models.value = items
        .filter((item) => item.outputModalities.includes('text'))
        .map((item) => ({ label: item.displayName, value: item.id }))
    })
  }
  async function save(): Promise<void> {
    await run(async () => {
      settings.value = await gateway.save(settings.value)
    })
  }
  return { settings, models, pending, error, load, save }
}
