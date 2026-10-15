import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const fixtures = [
  ['quoted domain import', { 'apps/desktop/src/modules/a/domain/model.ts': 'import "pinia"' }],
  [
    'cross feature alias in Vue',
    {
      'apps/desktop/src/modules/a/components/Panel.vue':
        '<script setup lang="ts">import type { X } from "@/modules/b/stores/state"</script>',
      'apps/desktop/src/modules/b/stores/state.ts': 'export type X = string',
    },
  ],
  [
    'barrel cycle',
    {
      'packages/api-client/src/index.ts': 'export * from "./client"',
      'packages/api-client/src/client.ts': 'export * from "./index"',
    },
  ],
  ['Python sqlite import', { 'services/runtime/src/example/domain/models.py': 'import sqlite3' }],
  [
    'Python adapter import',
    {
      'services/runtime/src/example/application/usecase.py':
        'from example.adapters.worker import Worker',
    },
  ],
  [
    'native import outside platform',
    { 'apps/desktop/src/shared/ui/native.ts': 'import { open } from "@tauri-apps/plugin-dialog"' },
  ],
]
for (const [name, files] of fixtures) {
  test(`rejects ${name}`, async () => {
    const root = await mkdtemp(join(tmpdir(), 'mlx-boundaries-'))
    try {
      for (const [path, content] of Object.entries(files)) {
        await mkdir(join(root, path, '..'), { recursive: true })
        await writeFile(join(root, path), content)
      }
      const result = spawnSync(
        process.execPath,
        [fileURLToPath(new URL('./check-boundaries.mjs', import.meta.url)), root],
        { encoding: 'utf8' },
      )
      assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`)
      assert.doesNotMatch(result.stderr, /SyntaxError|MODULE_NOT_FOUND/)
    } finally {
      await rm(root, { recursive: true, force: true })
    }
  })
}
