import type { Run, Verification } from './types.js'

/** Only the frozen explicit plan can produce a verification result. */
export function verificationStatus(
  run: Run,
  checks: readonly Verification[],
  fingerprint: string,
): Run['verification'] {
  const commands = run.verificationCommands ?? []
  if (!commands.length) return 'not_run'
  const attempts = checks.filter(
    (check) => check.purpose === 'verification' && check.runId === run.id,
  )
  if (!attempts.length) return 'not_run'
  const latest = commands.map((command) => attempts.findLast((check) => check.command === command))
  if (latest.some((check) => !check || check.stale || check.fingerprint !== fingerprint))
    return 'partial'
  return latest.every((check) => check?.exitCode === 0) ? 'passed' : 'failed'
}
