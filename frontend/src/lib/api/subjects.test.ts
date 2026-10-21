import { afterEach, describe, expect, it, vi } from 'vitest'

import { API_BASE_URL } from './client'
import {
  createSubject,
  deleteSubject,
  type Subject,
} from './subjects'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('subjects API', () => {
  it('posts JSON when creating a subject', async () => {
    const created: Subject = {
      id: 's1',
      name: '免疫学',
      description: '',
      color: null,
      icon: null,
      sort_order: 0,
      chapter_count: 0,
      created_at: '2026-10-19T10:00:00',
      updated_at: '2026-10-19T10:00:00',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(created, 201))
    vi.stubGlobal('fetch', fetchMock)

    await expect(createSubject({ name: '免疫学' })).resolves.toEqual(created)

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`${API_BASE_URL}/subjects`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ name: '免疫学' })
  })

  it('sends cascade confirmation and accepts a 204 response', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(deleteSubject('s1', true)).resolves.toBeUndefined()

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/subjects/s1?cascade=true`,
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})
