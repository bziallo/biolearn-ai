import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import type {
  ChapterNode,
  DocumentSummary,
  KnowledgePoint,
  Question,
  Subject,
} from '../lib/api'
import { clearOfflineCache, writeOfflineCache } from '../lib/offline/cache'
import { SubjectKnowledgePage } from './SubjectKnowledgePage'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const subject1: Subject = {
  id: 's1',
  name: '生物化学',
  description: '蛋白质与代谢。',
  color: null,
  icon: null,
  sort_order: 0,
  chapter_count: 1,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
}

const subject2: Subject = {
  ...subject1,
  id: 's2',
  name: '微生物学',
  description: '微生物与免疫。',
}

const tree: ChapterNode[] = [
  {
    id: 'c1',
    subject_id: 's1',
    parent_id: null,
    name: '蛋白质',
    description: '',
    sort_order: 0,
    created_at: '2026-10-19T10:00:00',
    updated_at: '2026-10-19T10:00:00',
    children: [],
  },
]

const document: DocumentSummary = {
  id: 'd1',
  subject_id: 's1',
  chapter_id: 'c1',
  chapter_name: '蛋白质',
  name: '蛋白质讲义',
  content_title: null,
  original_filename: 'protein.pdf',
  mime_type: 'application/pdf',
  extension: '.pdf',
  size_bytes: 1024,
  sha256: 'a'.repeat(64),
  status: 'parsed',
  parse_error: null,
  parse_warnings: null,
  page_count: 3,
  slide_count: null,
  chunk_count: 4,
  knowledge_point_count: 1,
  approved_count: 1,
  duplicate: false,
  uploaded_at: '2026-10-19T10:00:00',
  parsed_at: '2026-10-19T10:01:00',
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:01:00',
}

const point: KnowledgePoint = {
  id: 'p1',
  subject_id: 's1',
  chapter_id: 'c1',
  document_id: 'd1',
  parent_id: null,
  name: '蛋白质四级结构',
  type: 'structure',
  explanation: '多个亚基通过非共价键组装。',
  core_points: ['亚基', '非共价键'],
  conditions: null,
  source_quote: '四级结构由多个亚基组成。',
  source_quote_verified: true,
  source_page: 2,
  source_page_end: null,
  source_slide: null,
  source_locator: '第 2 页',
  source_chunk_id: null,
  importance: null,
  prerequisites: [],
  external_id: null,
  confidence: 0.9,
  review_note: null,
  needs_review: false,
  origin: 'ai',
  review_status: 'approved',
  duplicate_of_id: null,
  reviewed_at: '2026-10-19T10:02:00',
  published_at: '2026-10-19T10:02:00',
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:02:00',
}

const question = {
  id: 'q1',
  subject_id: 's1',
  subject_name: '生物化学',
  chapter_id: 'c1',
  chapter_name: '蛋白质',
  stem: '蛋白质四级结构由什么组成？',
  type: 'single_choice',
  status: 'approved',
  difficulty: 'easy',
  origin: 'ai',
  options: [],
  answer: {},
  grading_rule: {},
  explanation: '',
  knowledge_points: [],
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
  reviewed_at: null,
  published_at: null,
} as unknown as Question

function mockFetch(options: { failNetwork?: boolean } = {}) {
  return vi.fn((input: RequestInfo | URL) => {
    if (options.failNetwork) {
      return Promise.reject(new TypeError('network down'))
    }
    const url = String(input)
    if (url.endsWith('/subjects/s1/chapters')) {
      return Promise.resolve(jsonResponse(tree))
    }
    if (url.endsWith('/subjects/s2/chapters')) {
      return Promise.resolve(jsonResponse([]))
    }
    if (url.endsWith('/subjects/s1')) {
      return Promise.resolve(jsonResponse(subject1))
    }
    if (url.endsWith('/subjects/s2')) {
      return Promise.resolve(jsonResponse(subject2))
    }
    if (url.includes('/documents?') && url.includes('subject_id=s1')) {
      return Promise.resolve(jsonResponse([document]))
    }
    if (url.includes('/documents?') && url.includes('subject_id=s2')) {
      return Promise.resolve(jsonResponse([]))
    }
    if (url.includes('/knowledge-points?') && url.includes('subject_id=s1')) {
      return Promise.resolve(
        jsonResponse({
          points: [point],
          stats: {
            total: 1,
            pending: 0,
            approved: 1,
            needs_revision: 0,
            ignored: 0,
            needs_review: 0,
            duplicates: 0,
            failed_jobs: 0,
          },
          total: 1,
        }),
      )
    }
    if (url.includes('/knowledge-points?') && url.includes('subject_id=s2')) {
      return Promise.resolve(
        jsonResponse({
          points: [],
          stats: {
            total: 0,
            pending: 0,
            approved: 0,
            needs_revision: 0,
            ignored: 0,
            needs_review: 0,
            duplicates: 0,
            failed_jobs: 0,
          },
          total: 0,
        }),
      )
    }
    if (url.includes('/questions?') && url.includes('subject_id=s1')) {
      return Promise.resolve(
        jsonResponse({
          questions: [question],
          total: 1,
          stats: { total: 1, pending: 0, approved: 1, rejected: 0, needs_revision: 0 },
        }),
      )
    }
    if (url.includes('/questions?') && url.includes('subject_id=s2')) {
      return Promise.resolve(
        jsonResponse({
          questions: [],
          total: 0,
          stats: { total: 0, pending: 0, approved: 0, rejected: 0, needs_revision: 0 },
        }),
      )
    }
    return Promise.resolve(jsonResponse({ detail: { message: 'not found' } }, 404))
  })
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/subjects/s1/knowledge']}>
      <ToastProvider>
        <Routes>
          <Route
            path="/subjects/:subjectId/knowledge"
            element={<SubjectKnowledgePage />}
          />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  )
}

beforeEach(async () => {
  await clearOfflineCache()
})

afterEach(async () => {
  vi.unstubAllGlobals()
  await clearOfflineCache()
})

describe('SubjectKnowledgePage', () => {
  it('loads real course, material, knowledge point and question data', async () => {
    vi.stubGlobal('fetch', mockFetch())
    renderPage()

    expect(await screen.findByRole('heading', { name: '生物化学' })).toBeInTheDocument()
    expect(screen.getByText('蛋白质讲义')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /蛋白质四级结构/ }),
    ).toBeInTheDocument()
    expect(screen.getByText('蛋白质四级结构由什么组成？')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '导入课件' })).toHaveAttribute(
      'href',
      '/import?subject=s1',
    )

    fireEvent.click(screen.getByRole('button', { name: /蛋白质四级结构/ }))
    expect(screen.getByText('多个亚基通过非共价键组装。')).toBeInTheDocument()
    expect(screen.getByText('核心要点')).toBeInTheDocument()
  })

  it('switches course data without showing the previous course', async () => {
    vi.stubGlobal('fetch', mockFetch())
    render(
      <MemoryRouter initialEntries={['/subjects/s1/knowledge']}>
        <ToastProvider>
          <Link to="/subjects/s2/knowledge">切换到微生物学</Link>
          <Routes>
            <Route
              path="/subjects/:subjectId/knowledge"
              element={<SubjectKnowledgePage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '生物化学' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: '切换到微生物学' }))

    expect(await screen.findByRole('heading', { name: '微生物学' })).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.queryByText('蛋白质讲义')).not.toBeInTheDocument()
      expect(screen.queryByText('蛋白质四级结构')).not.toBeInTheDocument()
    })
  })

  it('shows cached data and an explicit offline notice when the backend is unreachable', async () => {
    await writeOfflineCache('subject-knowledge:s1', {
      subject: subject1,
      chapters: tree,
      documents: [document],
      points: [point],
      questions: [question],
      savedAt: '2026-10-19T10:05:00',
    })
    vi.stubGlobal('fetch', mockFetch({ failNetwork: true }))
    renderPage()

    expect(await screen.findByText(/当前显示离线缓存/)).toBeInTheDocument()
    expect(screen.getByText('蛋白质讲义')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /蛋白质四级结构/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '刷新' })).toBeEnabled()
  })
})
