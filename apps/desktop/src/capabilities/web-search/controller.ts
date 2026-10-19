import { ref } from 'vue'
import type { WebSettings, WebSettingsUpdate } from '@mlx-studio/api-client'

export interface WebSearchGateway {
  get(): Promise<WebSettings>
  save(value: WebSettingsUpdate): Promise<WebSettings>
  test(id: string, revision: number): Promise<WebSettings>
}
export function createWebSearchController(gateway: WebSearchGateway) {
  const settings = ref<WebSettings | null>(null),
    pending = ref(false),
    error = ref('')
  async function run(action: () => Promise<WebSettings>): Promise<boolean> {
    if (pending.value) return false
    pending.value = true
    error.value = ''
    try {
      settings.value = await action()
      return true
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : '联网设置请求失败'
      return false
    } finally {
      pending.value = false
    }
  }
  return {
    settings,
    pending,
    error,
    load: () => run(gateway.get),
    save: (value: WebSettingsUpdate) => run(() => gateway.save(value)),
    test: () =>
      settings.value
        ? run(() => gateway.test(settings.value!.id, settings.value!.revision))
        : Promise.resolve(false),
  }
}
