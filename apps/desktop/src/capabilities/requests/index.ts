/** Abort reduces work; generation ownership keeps late replies from changing a new view. */
export class RequestScope {
  private generation = 0
  private abort = new AbortController()
  private disposed = false
  get owner(): number {
    return this.generation
  }
  get signal(): AbortSignal {
    return this.abort.signal
  }
  owns(owner: number): boolean {
    return !this.disposed && owner === this.generation
  }
  reset(): void {
    this.dispose()
    this.disposed = false
    this.abort = new AbortController()
  }
  dispose(): void {
    this.disposed = true
    this.generation++
    this.abort.abort()
  }
}
