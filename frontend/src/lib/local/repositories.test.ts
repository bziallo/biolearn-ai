import { afterEach, describe, expect, it, vi } from 'vitest'

import { createRepositoryBundle } from './repositories'
import { LOCAL_DB_FLAG_KEY } from './featureFlag'

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.removeItem(LOCAL_DB_FLAG_KEY)
})

describe('repository factory', () => {
  it('keeps FastAPI as the default and maps its read models', async () => {
    localStorage.removeItem(LOCAL_DB_FLAG_KEY)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse([
          {
            id: 's1',
            name: '远程课程',
            description: '来自 FastAPI',
            color: null,
            icon: null,
            sort_order: 0,
            chapter_count: 1,
            created_at: '2026-10-22T10:00:00',
            updated_at: '2026-10-22T10:00:00',
          },
        ]),
      ),
    )

    const bundle = await createRepositoryBundle()
    expect(bundle.mode).toBe('remote')
    const courses = await bundle.courses.list()
    expect(courses).toHaveLength(1)
    expect(courses[0].name).toBe('远程课程')
    expect(courses[0].syncState).toBe('synced')
  })
})
