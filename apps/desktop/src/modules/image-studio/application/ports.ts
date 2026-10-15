import type { ImageArtifact, ImageJob, ImageRequest } from '../domain/image-state'
export interface ImageGateway {
  listJobs(signal?: AbortSignal): Promise<ImageJob[]>
  history(offset: number, signal?: AbortSignal): Promise<ImageArtifact[]>
  generate(request: ImageRequest): Promise<ImageJob>
  job(id: string, signal?: AbortSignal): Promise<ImageJob>
  cancel(id: string): Promise<unknown>
  image(id: string, signal?: AbortSignal): Promise<Blob>
  upload(file: File): Promise<{ id: string; originalName: string }>
  attachment(id: string, signal?: AbortSignal): Promise<Blob>
}
