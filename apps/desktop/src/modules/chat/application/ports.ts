import type { Conversation, ConversationPatch, JobSnapshot } from '@mlx-studio/api-client'
import type { ChatSubmissionGateway } from './submit-chat'
/** Read-only query models are shared contracts; submission rules remain independent. */
export interface ChatGateway extends ChatSubmissionGateway {
  list(): Promise<Conversation[]>
  get(id: string, signal?: AbortSignal): Promise<Conversation>
  create(modelId: string): Promise<Conversation>
  update(id: string, patch: ConversationPatch): Promise<Conversation>
  delete(id: string): Promise<unknown>
  cancel(id: string, job: string): Promise<unknown>
  job(id: string): Promise<JobSnapshot>
}
