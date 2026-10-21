import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import type {
  ChapterDetail,
  ChapterNode,
  Subject,
} from '../lib/api'
import { SubjectDetailPage } from './SubjectDetailPage'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const subject: Subject = {
  id: 's1',
  name: '细胞生物学',
  description: '探索细胞结构与功能。',
  color: '#a78bfa',
  icon: '🧫',
  sort_order: 0,
  chapter_count: 3,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
}

const tree: ChapterNode[] = [
  {
    id: 'root',
    subject_id: 's1',
    parent_id: null,
    name: '细胞膜',
    description: '细胞边界。',
    sort_order: 0,
    created_at: '2026-10-19T10:00:00',
    updated_at: '2026-10-19T10:00:00',
    children: [
      {
        id: 'child',
        subject_id: 's1',
        parent_id: 'root',
        name: '膜运输',
        description: '物质跨膜运输。',
        sort_order: 0,
        created_at: '2026-10-19T10:00:00',
        updated_at: '2026-10-19T10:00:00',
        children: [
          {
            id: 'grandchild',
            subject_id: 's1',
            parent_id: 'child',
            name: '主动运输',
            description: '依赖能量。',
            sort_order: 0,
            created_at: '2026-10-19T10:00:00',
            updated_at: '2026-10-19T10:00:00',
            children: [],
          },
        ],
      },
    ],
  },
]

const detail: ChapterDetail = {
  ...tree[0].children[0],
  subject: {
    id: 's1',
    name: '细胞生物学',
    color: '#a78bfa',
    icon: '🧫',
  },
  parent: { id: 'root', name: '细胞膜' },
  path: [{ id: 'root', name: '细胞膜' }],
  descendant_count: 1,
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SubjectDetailPage', () => {
  it('renders a three-level chapter tree and loads chapter detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse(tree))
        }
        if (url.endsWith('/subjects/s1')) {
          return Promise.resolve(jsonResponse(subject))
        }
        if (url.endsWith('/chapters/child')) {
          return Promise.resolve(jsonResponse(detail))
        }
        return Promise.resolve(
          jsonResponse({ detail: { message: 'not found' } }, 404),
        )
      }),
    )

    render(
      <MemoryRouter initialEntries={['/subjects/s1']}>
        <ToastProvider>
          <Routes>
            <Route
              path="/subjects/:subjectId"
              element={<SubjectDetailPage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    )

    expect(
      await screen.findByRole('heading', { name: '细胞生物学' }),
    ).toBeInTheDocument()
    expect(screen.getByText('细胞膜')).toBeInTheDocument()
    expect(screen.getByText('膜运输')).toBeInTheDocument()
    expect(screen.getByText('主动运输')).toBeInTheDocument()

    fireEvent.click(screen.getByText('膜运输').closest('button')!)

    expect(await screen.findByText('物质跨膜运输。')).toBeInTheDocument()
    expect(screen.getByText('1 个')).toBeInTheDocument()
  })
})
