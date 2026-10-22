import { afterEach, describe, expect, it } from 'vitest'

import {
  LOCAL_DB_FLAG_KEY,
  isLocalDbEnabled,
  localDbFlagSource,
  setLocalDbEnabled,
} from './featureFlag'
import { canonicalJson, checksumFor } from './exportFormat'

afterEach(() => {
  localStorage.removeItem(LOCAL_DB_FLAG_KEY)
})

describe('local DB feature flag', () => {
  it('defaults to remote and can be toggled at runtime', () => {
    localStorage.removeItem(LOCAL_DB_FLAG_KEY)
    expect(isLocalDbEnabled()).toBe(false)
    expect(localDbFlagSource()).not.toBe('runtime')

    setLocalDbEnabled(true)
    expect(isLocalDbEnabled()).toBe(true)
    expect(localDbFlagSource()).toBe('runtime')

    setLocalDbEnabled(false)
    expect(isLocalDbEnabled()).toBe(false)
  })

  it('canonical JSON and checksum are stable across key order', async () => {
    const left = canonicalJson({ b: 2, a: { d: 4, c: 3 } })
    const right = canonicalJson({ a: { c: 3, d: 4 }, b: 2 })
    expect(left).toBe(right)
    const checksum = await checksumFor(2, true, {
      courses: [],
      chapters: [],
      documents: [],
      knowledgePoints: [],
      questions: [],
      practiceSessions: [],
      practiceAnswers: [],
    })
    expect(checksum).toMatch(/^[a-f0-9]{64}$/)
  })
})
