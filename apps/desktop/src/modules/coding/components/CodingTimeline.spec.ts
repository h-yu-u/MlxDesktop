import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import type { CodingRun } from '../application/ports'
import CodingTimeline from './CodingTimeline.vue'
it('shows the actionable Runtime cause of a failed model task', () => {
  const run: CodingRun = {
    id: 'r',
    sessionId: 's',
    submissionId: 'one',
    text: 'build library',
    modelId: 'local',
    mode: 'develop',
    status: 'failed',
    phase: 'exploring',
    verification: 'not_run',
    error: 'TOOL_JSON_INVALID',
    createdAt: '',
    baseline: '',
    fingerprint: null,
    maxRepairRounds: 2,
  }
  const wrapper = mount(CodingTimeline, {
    props: {
      runs: [run],
      events: [
        {
          seq: 1,
          sessionId: 's',
          runId: 'r',
          type: 'assistant.message',
          text: '',
          data: { stopReason: 'error', error: 'TOOL_JSON_INVALID' },
        },
      ],
    },
  })
  expect(wrapper.text()).toContain('模型返回的 JSON 工具调用无效')
  expect(wrapper.find('details').text()).toContain('TOOL_JSON_INVALID')
  expect(wrapper.text()).not.toContain('MODEL_INFERENCE_FAILED')
})
