import { afterEach, describe, expect, it, vi } from 'vitest'

import { API_BASE_URL, apiRequest } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiRequest', () => {
  it('calls the versioned API and parses JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest<{ ok: boolean }>('/health')).resolves.toEqual({
      ok: true,
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`${API_BASE_URL}/health`)
    expect((init.headers as Headers).get('Accept')).toBe('application/json')
  })

  it('raises ApiError with the HTTP status for failed responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(null, { status: 503 })),
    )

    await expect(apiRequest('/health')).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
    })
  })

  it('uses the structured backend message for API errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              code: 'subject_has_chapters',
              message: '该学科下仍有 2 个章节',
            },
          }),
          { status: 409 },
        ),
      ),
    )

    await expect(apiRequest('/subjects/s1')).rejects.toMatchObject({
      status: 409,
      message: '该学科下仍有 2 个章节',
    })
  })
})
