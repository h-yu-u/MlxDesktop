import { readFile, readdir } from 'node:fs/promises'
import { join } from 'node:path'

const violations = []

async function visit(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) await visit(path)
    else if (/\.(ts|vue|py)$/.test(entry.name)) await inspect(path)
  }
}

async function inspect(path) {
  const source = await readFile(path, 'utf8')
  if (path.startsWith('apps/desktop/src/') && /\bfetch\s*\(/.test(source)) {
    violations.push(`${path}: UI must call the API client, not fetch directly`)
  }
  if (path.includes('/domain/') && /from\s+(?:vue|fastapi|pydantic|mlx|tauri|sqlite3)/i.test(source)) {
    violations.push(`${path}: domain layer imports an infrastructure or UI dependency`)
  }
  if (path.startsWith('apps/desktop/src/') && /mlx_lm|mlx_vlm|mflux/i.test(source)) {
    violations.push(`${path}: frontend contains model engine details`)
  }
}

await Promise.all([
  visit('apps/desktop/src'),
  visit('services/runtime/src/mlx_studio_runtime/domain'),
])
if (violations.length) {
  process.stderr.write(`${violations.join('\n')}\n`)
  process.exitCode = 1
} else {
  process.stdout.write('Dependency boundary checks passed.\n')
}
