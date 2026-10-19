import { invoke, isTauri } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'

export async function pickModelDirectory(): Promise<string | null> {
  const path = await open({ directory: true, multiple: false, title: '选择模型目录' })
  return typeof path === 'string' ? path : null
}
export async function exportBlob(blob: Blob, filename: string): Promise<void> {
  if (isTauri()) {
    if (blob.size > 64 * 1024 * 1024) throw new Error('Export exceeds 64 MiB')
    await invoke<boolean>('export_blob', await blob.arrayBuffer(), {
      headers: { 'x-mlx-export-name': filename },
    })
    return
  }
  const url = URL.createObjectURL(blob)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function pickProjectDirectory(): Promise<string | null> {
  const path = await open({ directory: true, multiple: false, title: '选择开发项目' })
  return typeof path === 'string' ? path : null
}

export async function pickSkillDirectory(): Promise<string | null> {
  const path = await open({ directory: true, multiple: false, title: '选择包含 SKILL.md 的目录' })
  return typeof path === 'string' ? path : null
}
