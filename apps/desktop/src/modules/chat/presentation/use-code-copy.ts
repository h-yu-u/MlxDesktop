import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { useTimeoutFn } from '@vueuse/core'
import { copyText } from '../../../platform/clipboard'

/** Delegation survives streamed HTML replacement without adding listeners per code block. */
export function useCodeCopy(root: Ref<HTMLElement | null>, html: Readonly<Ref<string>>) {
  const active = ref(-1)
  const status = ref<'idle' | 'copying' | 'copied' | 'failed'>('idle')
  let alive = true
  onScopeDispose(() => {
    alive = false
  })
  const { start, stop } = useTimeoutFn(
    () => {
      status.value = 'idle'
    },
    1800,
    { immediate: false },
  )

  watch(
    [root, html, active, status],
    () => {
      root.value?.querySelectorAll<HTMLButtonElement>('.code-copy').forEach((button, index) => {
        const state = index === active.value ? status.value : 'idle'
        const label = {
          idle: '复制',
          copying: '复制中…',
          copied: '已复制',
          failed: '复制失败，重试',
        }[state]
        button.textContent = label
        button.disabled = state === 'copying'
        button.setAttribute('aria-label', state === 'idle' ? '复制代码' : label)
        button.setAttribute('aria-live', 'polite')
      })
    },
    { flush: 'post', immediate: true },
  )

  async function handleCopy(event: MouseEvent): Promise<void> {
    if (!(event.target instanceof Element) || status.value === 'copying') return
    const button = event.target.closest<HTMLButtonElement>('button.code-copy')
    if (!button || !root.value?.contains(button)) return
    const code = button.closest('.code-block')?.querySelector('pre > code')
    if (!code) return
    stop()
    active.value = [...root.value.querySelectorAll('.code-copy')].indexOf(button)
    status.value = 'copying'
    try {
      await copyText(code.textContent ?? '')
      if (alive) status.value = 'copied'
    } catch {
      if (alive) status.value = 'failed'
    }
    if (alive) start()
  }
  return { handleCopy }
}
