export function saveImageBlob(blob: Blob, id: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `mlx-studio-${id}.png`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
