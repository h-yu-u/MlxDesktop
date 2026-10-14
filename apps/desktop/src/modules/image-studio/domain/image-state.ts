import type { components } from '@mlx-studio/api-client'

export type ImageArtifact = components['schemas']['ImageArtifactView']
export type ImageJob = components['schemas']['ImageJobView']
export type ImageRequest = components['schemas']['ImageJobRequest']
export interface ImageDraft {
  modelId: string | null
  prompt: string
  width: number
  height: number
  steps: number
  seed: number | null
}
const states = ['queued', 'preparing', 'running', 'cancelling', 'succeeded', 'failed', 'cancelled'] as const
export function isTerminal(job: ImageJob): boolean {
  return ['succeeded', 'failed', 'cancelled'].includes(job.state)
}
export function buildImageRequest(draft: ImageDraft): ImageRequest {
  if (!draft.modelId) throw new Error('请先选择生图模型')
  if (!draft.prompt.trim() || draft.prompt.length > 10000) throw new Error('请输入不超过 10,000 字的提示词')
  if ([draft.width, draft.height].some((value) => !Number.isInteger(value) || value < 64 || value > 2048 || value % 16)) {
    throw new Error('宽高须在 64–2048 之间，且为 16 的倍数')
  }
  if (!Number.isInteger(draft.steps) || draft.steps < 1 || draft.steps > 100) throw new Error('步数须在 1–100 之间')
  if (draft.seed !== null && (!Number.isInteger(draft.seed) || draft.seed < 0 || draft.seed > 4294967295)) {
    throw new Error('Seed 须为 0–4294967295 的整数，留空则随机生成')
  }
  return { model_id: draft.modelId, prompt: draft.prompt.trim(), width: draft.width, height: draft.height, steps: draft.steps, seed: draft.seed }
}
export function readArtifact(value: unknown): ImageArtifact {
  const item = record(value)
  return { ...snapshot(item), id: text(item, 'id'), job_id: text(item, 'job_id'), created_at: integer(item, 'created_at') }
}
export function readJob(value: unknown): ImageJob {
  const item = record(value)
  const state = states.find((state) => state === item.state)
  if (!state) throw new Error('图片任务状态无效')
  return { ...snapshot(item), id: text(item, 'id'), created_at: integer(item, 'created_at'), state,
    progress: integer(item, 'progress'), error_code: nullableText(item, 'error_code'), artifact_id: nullableText(item, 'artifact_id') }
}
export function readList<T>(value: unknown, read: (item: unknown) => T): T[] {
  if (!Array.isArray(value)) throw new Error('图片工作区响应格式无效')
  return value.map(read)
}
export function imageJobError(code: string | null): string {
  const messages: Record<string, string> = {
    MODEL_LOAD_FAILED: '生图模型加载失败，请确认对应引擎已安装、模型文件完整且格式受支持。',
    RUNTIME_RESTARTED: '应用重启中断了此次生成，可以复用参数重新生成。',
    RUNTIME_SHUTDOWN: '应用关闭中断了此次生成，可以复用参数重新生成。',
    IMAGE_GENERATION_FAILED: '图片生成失败，请检查模型与参数后重试。',
  }
  return messages[code ?? ''] ?? '图片生成失败，请检查模型与参数后重试。'
}
function record(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null) throw new Error('图片数据格式无效')
  return value as Record<string, unknown>
}
function snapshot(item: Record<string, unknown>): Omit<ImageArtifact, 'id' | 'job_id' | 'created_at'> {
  if (typeof item.simulated !== 'boolean') throw new Error('图片元数据格式无效')
  return { model_id: text(item, 'model_id'), model_name: text(item, 'model_name'), prompt: text(item, 'prompt'),
    width: integer(item, 'width'), height: integer(item, 'height'), steps: integer(item, 'steps'), seed: integer(item, 'seed'), simulated: item.simulated }
}
function text(item: Record<string, unknown>, key: string): string {
  const value = item[key]
  if (typeof value !== 'string') throw new Error('图片元数据格式无效')
  return value
}
function nullableText(item: Record<string, unknown>, key: string): string | null {
  return item[key] === null ? null : text(item, key)
}
function integer(item: Record<string, unknown>, key: string): number {
  const value = item[key]
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error('图片参数格式无效')
  return value
}
