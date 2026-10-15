export interface ChatAttachment {
  id: string
  mimeType: string
  originalName: string
}
export interface ChatSubmissionInput {
  conversationId: string
  content: string
  files: File[]
  modelId: string
  maxTokens: number
  temperature: number
}
export interface ChatSubmissionGateway {
  upload(file: File): Promise<ChatAttachment>
  sequence(): Promise<number>
  submit(
    id: string,
    input: {
      content: string
      model_id: string
      max_tokens: number
      temperature: number
      attachment_ids: string[]
      client_request_id: string
    },
  ): Promise<{ jobId: string }>
}
/** Owns submission exclusion and the durable retry identity, independently of Vue. */
export class SubmitChat {
  private running = false
  private retry?: {
    key: string
    files: File[]
    requestId: string
    attachments?: ChatAttachment[]
  }
  constructor(private readonly gateway: ChatSubmissionGateway) {}
  async run(input: ChatSubmissionInput) {
    if (this.running) return undefined
    this.running = true
    try {
      const content = input.content.trim() || '请描述图片内容。'
      const key = JSON.stringify({
        ...input,
        files: input.files.map((file) => [file.name, file.size, file.lastModified]),
      })
      if (
        this.retry?.key !== key ||
        this.retry.files.some((file, index) => file !== input.files[index])
      ) {
        this.retry = { key, files: [...input.files], requestId: crypto.randomUUID() }
      }
      const retry = this.retry
      retry.attachments ??= await Promise.all(input.files.map((file) => this.gateway.upload(file)))
      const after = await this.gateway.sequence()
      const result = await this.gateway.submit(input.conversationId, {
        content,
        model_id: input.modelId,
        max_tokens: input.maxTokens,
        temperature: input.temperature,
        attachment_ids: retry.attachments.map((item) => item.id),
        client_request_id: retry.requestId,
      })
      const attachments = retry.attachments
      this.retry = undefined
      return { jobId: result.jobId, after, content, attachments }
    } finally {
      this.running = false
    }
  }
}
