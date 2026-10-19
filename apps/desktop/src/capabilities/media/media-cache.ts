/** Bounded Object URL ownership. Disposed or evicted requests cannot revive entries. */
export class MediaCache {
  private epoch = 0
  private scope = new AbortController()
  private urls = new Map<string, string>()
  private pending = new Map<string, Promise<string | undefined>>()
  private generations = new Map<string, number>()
  constructor(
    private readonly load: (id: string, signal: AbortSignal) => Promise<Blob>,
    private readonly changed: () => void,
    private readonly limit = 48,
  ) {}
  snapshot(): Record<string, string> {
    return Object.fromEntries(this.urls)
  }
  get(id: string): Promise<string | undefined> {
    const existing = this.urls.get(id)
    if (existing) {
      this.urls.delete(id)
      this.urls.set(id, existing)
      return Promise.resolve(existing)
    }
    const pending = this.pending.get(id)
    if (pending) return pending
    const epoch = this.epoch
    const generation = this.generations.get(id) ?? 0
    const task = this.load(id, this.scope.signal)
      .then((blob) => {
        if (epoch !== this.epoch || generation !== (this.generations.get(id) ?? 0)) return undefined
        const url = URL.createObjectURL(blob)
        this.urls.set(id, url)
        while (this.urls.size > this.limit) {
          const first = this.urls.entries().next().value
          if (!first) break
          URL.revokeObjectURL(first[1])
          this.urls.delete(first[0])
        }
        this.changed()
        return url
      })
      .finally(() => {
        if (this.pending.get(id) === task) this.pending.delete(id)
      })
    this.pending.set(id, task)
    return task
  }
  evict(id: string): void {
    this.generations.set(id, (this.generations.get(id) ?? 0) + 1)
    const url = this.urls.get(id)
    if (url) URL.revokeObjectURL(url)
    this.urls.delete(id)
    this.pending.delete(id)
    this.changed()
  }
  dispose(): void {
    this.scope.abort()
    this.scope = new AbortController()
    this.epoch += 1
    for (const url of this.urls.values()) URL.revokeObjectURL(url)
    this.urls.clear()
    this.pending.clear()
    this.generations.clear()
    this.changed()
  }
}
