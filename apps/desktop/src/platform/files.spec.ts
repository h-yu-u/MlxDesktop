import { afterEach, describe, expect, it, vi } from 'vitest'
import { invoke, isTauri } from '@tauri-apps/api/core'
import { exportBlob } from './files'
vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), isTauri: vi.fn() }))
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }))
afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
describe('file export platform boundary', () => {
  it('uses binary IPC and a suggested name without accepting a destination path', async () => {
    vi.mocked(isTauri).mockReturnValue(true)
    const raw = new Uint8Array([1, 2, 3]).buffer
    class TestBlob extends Blob {
      override arrayBuffer() {
        return Promise.resolve(raw)
      }
    }
    await exportBlob(new TestBlob(['abc']), 'sample.wav')
    expect(invoke).toHaveBeenCalledWith('export_blob', raw, {
      headers: { 'x-mlx-export-name': 'sample.wav' },
    })
  })
  it('propagates native saving errors so controllers can retain error and loading state', async () => {
    vi.mocked(isTauri).mockReturnValue(true)
    vi.mocked(invoke).mockRejectedValueOnce(new Error('EXPORT_WRITE_FAILED'))
    class TestBlob extends Blob {
      override arrayBuffer() {
        return Promise.resolve(new ArrayBuffer(3))
      }
    }
    await expect(exportBlob(new TestBlob(['abc']), 'sample.wav')).rejects.toThrow(
      'EXPORT_WRITE_FAILED',
    )
  })
  it('keeps ordinary downloads in browser mode and releases the object URL', async () => {
    vi.mocked(isTauri).mockReturnValue(false)
    const create = vi.fn(() => 'blob:test'),
      revoke = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await exportBlob(new Blob(['abc']), 'sample.wav')
    expect(click).toHaveBeenCalledOnce()
    expect(revoke).toHaveBeenCalledWith('blob:test')
  })
})
