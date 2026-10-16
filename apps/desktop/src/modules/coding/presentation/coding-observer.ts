import type { RuntimeClient } from '@mlx-studio/api-client'
/** Coding has its own persistent sequence, independent of inference Job events. */
export function observeCoding(
  client: () => Promise<RuntimeClient>,
  after: number,
  refresh: () => Promise<number>,
  fail: (error: unknown) => void,
): () => void {
  const abort = new AbortController()
  let sequence = after,
    syncing: Promise<void> | undefined,
    dirty = false
  const sync = (): Promise<void> => {
    dirty = true
    if (syncing) return syncing
    syncing = (async () => {
      while (dirty && !abort.signal.aborted) {
        dirty = false
        sequence = Math.max(sequence, await refresh())
      }
    })().finally(() => {
      syncing = undefined
    })
    return syncing
  }
  void (async () => {
    while (!abort.signal.aborted) {
      try {
        await sync()
        const connection = await client()
        if (abort.signal.aborted) return
        await connection.subscribeCoding(
          (event) => {
            if (event.seq <= sequence) return
            // Snapshot is authoritative, including sequence gaps and other sessions' changes.
            void sync().catch(fail)
          },
          abort.signal,
          sequence,
        )
      } catch (error) {
        if (!abort.signal.aborted) fail(error)
      }
      if (!abort.signal.aborted)
        await new Promise<void>((resolve) => {
          const done = (): void => {
            clearTimeout(timer)
            abort.signal.removeEventListener('abort', done)
            resolve()
          }
          const timer = setTimeout(done, 1000)
          abort.signal.addEventListener('abort', done, { once: true })
        })
    }
  })()
  return () => abort.abort()
}
