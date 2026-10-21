import { beforeEach, describe, expect, it } from 'vitest'

import {
  currentRuntimeBaseUrl,
  describeConnection,
  getAccessToken,
  resolveApiBaseUrl,
  setAccessToken,
  setRuntimeBaseUrl,
} from './connection'

beforeEach(() => {
  window.localStorage.clear()
})

describe('connection settings', () => {
  it('prefers a saved runtime URL over the build-time value', () => {
    setRuntimeBaseUrl('http://10.0.0.5:8000/api/v1/')

    expect(currentRuntimeBaseUrl()).toBe('http://10.0.0.5:8000/api/v1')
    expect(resolveApiBaseUrl()).toBe('http://10.0.0.5:8000/api/v1')
    expect(describeConnection()).toMatchObject({
      baseUrl: 'http://10.0.0.5:8000/api/v1',
      configured: true,
      source: 'runtime',
    })
  })

  it('falls back to the same origin in a browser', () => {
    const resolved = resolveApiBaseUrl()
    expect(resolved === '' || resolved.endsWith('/api/v1')).toBe(true)
    expect(describeConnection().environment).toBe('browser')
  })

  it('stores the access token locally and trims it', () => {
    setAccessToken('  secret-token  ')
    expect(getAccessToken()).toBe('secret-token')

    setAccessToken('')
    expect(getAccessToken()).toBe('')
  })

  it('clears the runtime URL when an empty value is saved', () => {
    setRuntimeBaseUrl('http://10.0.0.5:8000/api/v1')
    setRuntimeBaseUrl('')
    expect(currentRuntimeBaseUrl()).toBe('')
  })
})
