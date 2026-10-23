export function evaluateToolPolicy(input: {
  mode: 'analyze' | 'develop' | 'review'
  risk: string
  revoked?: boolean
}): { decision: 'allow' | 'ask' | 'deny'; code?: string } {
  if (input.revoked) return { decision: 'deny', code: 'CAPABILITY_REVOKED' }
  if (input.mode !== 'develop' && input.risk !== 'read')
    return { decision: 'deny', code: 'READ_ONLY_MODE' }
  return { decision: input.risk === 'read' ? 'allow' : 'ask' }
}
