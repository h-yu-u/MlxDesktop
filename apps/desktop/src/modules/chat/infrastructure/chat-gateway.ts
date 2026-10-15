import { createEndpoints, type ConversationPatch, type RuntimeClient } from '@mlx-studio/api-client'
import type { ChatSubmissionGateway } from '../application/submit-chat'

export function createChatGateway(provider: () => Promise<RuntimeClient>) {
  const endpoints = async () => createEndpoints(await provider())
  return {
    list: async () => (await endpoints()).conversations.list(),
    get: async (id: string, signal?: AbortSignal) =>
      (await endpoints()).conversations.get(id, signal),
    create: async (modelId: string) => (await endpoints()).conversations.create(modelId),
    update: async (id: string, patch: ConversationPatch) =>
      (await endpoints()).conversations.update(id, patch),
    delete: async (id: string) => (await endpoints()).conversations.delete(id),
    cancel: async (id: string, job: string) => (await endpoints()).conversations.cancel(id, job),
    upload: async (file: File) => (await provider()).uploadImage(file),
    sequence: async () => Number((await (await endpoints()).runtime.info()).event_sequence),
    submit: async (...args: Parameters<ChatSubmissionGateway['submit']>) =>
      (await endpoints()).conversations.submit(...args),
    job: async (id: string) => (await endpoints()).jobs.get(id),
  }
}
export type ChatGateway = ReturnType<typeof createChatGateway>
