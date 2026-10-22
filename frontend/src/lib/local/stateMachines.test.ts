import { describe, expect, it } from 'vitest'

import {
  assertTransition,
  canTransition,
  FILE_TRANSITIONS,
  PARSE_TRANSITIONS,
  UPLOAD_TRANSITIONS,
} from './stateMachines'

describe('local state machines', () => {
  it('allows only declared file/parse transitions', () => {
    expect(canTransition(FILE_TRANSITIONS, 'copying', 'stored')).toBe(true)
    expect(canTransition(FILE_TRANSITIONS, 'selected', 'stored')).toBe(false)
    expect(canTransition(PARSE_TRANSITIONS, 'queued', 'parsing')).toBe(true)
    expect(canTransition(PARSE_TRANSITIONS, 'parsed', 'queued')).toBe(false)
  })

  it('does not allow uploaded to be re-queued or silently changed', () => {
    expect(canTransition(UPLOAD_TRANSITIONS, 'uploaded', 'queued')).toBe(false)
    expect(canTransition(UPLOAD_TRANSITIONS, 'needs_verification', 'queued')).toBe(
      true,
    )
    expect(() =>
      assertTransition(UPLOAD_TRANSITIONS, 'uploaded', 'queued', '上传任务'),
    ).toThrow(/非法状态转换/)
  })
})
