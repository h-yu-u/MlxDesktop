import { expect, it, vi } from 'vitest'
import { SubmitChat } from './submit-chat'

it('does not reuse uploaded bytes when a newly selected file has identical metadata', async () => {
  const upload = vi
    .fn()
    .mockResolvedValueOnce({ id: 'first', mimeType: 'image/png', originalName: 'image.png' })
    .mockResolvedValueOnce({ id: 'second', mimeType: 'image/png', originalName: 'image.png' })
  const submit = vi
    .fn()
    .mockRejectedValueOnce(new Error('response lost'))
    .mockResolvedValueOnce({ jobId: 'job' })
  const useCase = new SubmitChat({ upload, sequence: async () => 0, submit })
  const input = {
    conversationId: 'conversation',
    content: 'Describe this',
    modelId: 'vision',
    maxTokens: 64,
    temperature: 0,
    files: [new File(['a'], 'image.png', { lastModified: 1 })],
  }
  await expect(useCase.run(input)).rejects.toThrow('response lost')
  await useCase.run({
    ...input,
    files: [new File(['b'], 'image.png', { lastModified: 1 })],
  })
  expect(upload).toHaveBeenCalledTimes(2)
  expect(submit.mock.calls[1]?.[1].attachment_ids).toEqual(['second'])
  expect(submit.mock.calls[1]?.[1].client_request_id).not.toBe(
    submit.mock.calls[0]?.[1].client_request_id,
  )
})
