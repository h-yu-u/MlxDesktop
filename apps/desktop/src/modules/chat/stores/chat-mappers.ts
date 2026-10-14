import type { ChatMessage } from '../domain/chat-state'

export interface ModelOption {
  id: string
  displayName: string
  engine: string
  inputModalities: string[]
  multiImage: boolean
  contextLength?: number
  state?: string
}

export interface ConversationOption {
  id: string
  title: string
  modelId: string | null
}

export function readModels(value: unknown): ModelOption[] {
  if (!Array.isArray(value)) return []
  return value.filter((item) => stringArrayField(item, 'outputModalities').includes('text')).map((item) => ({
    id: stringField(item, 'id') ?? '',
    displayName: stringField(item, 'displayName') ?? 'Unknown model',
    engine: stringField(item, 'engine') ?? 'unknown',
    inputModalities: stringArrayField(item, 'inputModalities'),
    multiImage: nestedBooleanField(item, 'capabilities', 'multiImage'),
    state: stringField(item, 'state'),
    contextLength: numberField(item, 'contextLength'),
  })).filter((item) => item.id)
}

export function readConversations(value: unknown): ConversationOption[] {
  return Array.isArray(value) ? value.map(readConversation) : []
}

export function readConversation(value: unknown): ConversationOption {
  return {
    id: stringField(value, 'id') ?? '',
    title: stringField(value, 'title') ?? 'Untitled',
    modelId: stringField(value, 'modelId') ?? null,
  }
}

export function readMessages(value: unknown): ChatMessage[] {
  return arrayField(value, 'messages').map((item) => ({
    id: stringField(item, 'id') ?? crypto.randomUUID(),
    role: stringField(item, 'role') === 'user' ? 'user' : 'assistant',
    content: stringField(item, 'content') ?? '',
    state: 'complete',
    attachments: readAttachments(item),
  }))
}

export function stringField(value: unknown, key: string): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const field = (value as Record<string, unknown>)[key]
  return typeof field === 'string' ? field : undefined
}

export function numberField(value: unknown, key: string): number | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const field = (value as Record<string, unknown>)[key]
  return typeof field === 'number' ? field : undefined
}

function readAttachments(
  value: unknown,
): Array<{ id: string; originalName: string; mimeType: string }> {
  return arrayField(value, 'attachments').flatMap((item) => {
    const id = stringField(item, 'id')
    if (!id) return []
    return [{
      id,
      originalName: stringField(item, 'originalName') ?? '图片',
      mimeType: stringField(item, 'mimeType') ?? 'image/*',
    }]
  })
}

function arrayField(value: unknown, key: string): unknown[] {
  if (typeof value !== 'object' || value === null) return []
  const field = (value as Record<string, unknown>)[key]
  return Array.isArray(field) ? field : []
}

function stringArrayField(value: unknown, key: string): string[] {
  return arrayField(value, key).filter((item): item is string => typeof item === 'string')
}

function nestedBooleanField(value: unknown, parentKey: string, key: string): boolean {
  if (typeof value !== 'object' || value === null) return false
  const parent = (value as Record<string, unknown>)[parentKey]
  if (typeof parent !== 'object' || parent === null) return false
  return (parent as Record<string, unknown>)[key] === true
}
