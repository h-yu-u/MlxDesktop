import type { Provider, RunRuntime } from './ports.js'
import type { Mode } from '../domain/types.js'
import type { Selection } from '../extensions/domain/types.js'
import type { RpcParamsMap } from '../protocol/generated/types.js'
export interface Submission {
  sessionId: string
  submissionId: string
  text: string
  mode: Mode
  provider: Provider
  probe?: boolean
  queue?: boolean
  verifyOnly?: boolean
  verifyAfter?: boolean
  selection?: Selection
  runtime?: RunRuntime
  connectionSecrets?: RpcParamsMap['runs.submit']['connectionSecrets']
}
