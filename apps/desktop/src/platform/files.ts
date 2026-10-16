import { open } from '@tauri-apps/plugin-dialog'

export async function pickModelDirectory(): Promise<string | null> {
  const path = await open({ directory: true, multiple: false, title: '选择模型目录' })
  return typeof path === 'string' ? path : null
}
export function exportBlob(blob: Blob, filename: string): void {
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
