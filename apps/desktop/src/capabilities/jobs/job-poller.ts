export class JobPoller {
  private timer?: ReturnType<typeof setTimeout>
  private epoch = 0
  schedule(run: () => Promise<void>): void {
    this.stop()
    const epoch = this.epoch
    this.timer = setTimeout(() => {
      this.timer = undefined
      if (epoch === this.epoch) void run()
    }, 750)
  }
  stop(): void {
    this.epoch += 1
    if (this.timer) clearTimeout(this.timer)
    this.timer = undefined
  }
}
