export interface Settings {
  id: string
  defaultModelId: string
  contextBudget: number
  maxRepairRounds: number
}
export const defaultSettings: Settings = {
  id: 'coding',
  defaultModelId: '',
  contextBudget: 32768,
  maxRepairRounds: 2,
}
export function validateSettings(value: Record<string, unknown>): Settings {
  const { defaultModelId, contextBudget, maxRepairRounds } = value
  if (
    typeof defaultModelId !== 'string' ||
    defaultModelId.length > 128 ||
    typeof contextBudget !== 'number' ||
    !Number.isInteger(contextBudget) ||
    contextBudget < 4096 ||
    contextBudget > 32768 ||
    typeof maxRepairRounds !== 'number' ||
    !Number.isInteger(maxRepairRounds) ||
    maxRepairRounds < 0 ||
    maxRepairRounds > 2
  )
    throw new Error('INVALID_SETTINGS')
  return { id: 'coding', defaultModelId, contextBudget, maxRepairRounds }
}
