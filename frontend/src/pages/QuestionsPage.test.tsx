import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import { QuestionsPage } from './QuestionsPage'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const subject = {
  id: 's1',
  name: '生物化学',
  description: '',
  color: null,
  icon: null,
  sort_order: 0,
  chapter_count: 1,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
}

const chapter = {
  id: 'c1',
  subject_id: 's1',
  parent_id: null,
  name: '蛋白质',
  description: '',
  sort_order: 0,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
  children: [],
}

const knowledge = {
  id: 'k1',
  subject_id: 's1',
  chapter_id: 'c1',
  document_id: 'd1',
  parent_id: null,
  name: '蛋白质一级结构',
  type: 'structure',
  explanation: '氨基酸序列。',
  core_points: [],
  conditions: null,
  source_quote: null,
  source_quote_verified: true,
  source_page: 5,
  source_page_end: null,
  source_slide: 2,
  source_locator: '第 5 页',
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
  reviewed_at: '2026-10-19T10:00:00',
  published_at: '2026-10-19T10:00:00',
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
}

const baseQuestion = {
  id: 'q1',
  subject_id: 's1',
  subject_name: '生物化学',
  chapter_id: 'c1',
  chapter_name: '蛋白质',
  source_document_id: 'd1',
  source_document_name: '蛋白质讲义',
  generation_job_id: null,
  duplicate_of_id: null,
  duplicate_reason: null,
  type: 'single_choice',
  stem: '蛋白质一级结构由什么决定？',
  options: [
    { key: 'A', text: '氨基酸序列' },
    { key: 'B', text: '空间结构' },
  ],
  answer: { choices: ['A'] },
  grading_rule: { mode: 'choice_exact' },
  explanation: '一级结构是氨基酸序列。',
  difficulty: 'easy',
  status: 'pending',
  origin: 'ai',
  source_locator: '第 5 页',
  ai_provider: 'test',
  ai_model: 'test',
  confidence: 0.9,
  review_note: null,
  score: 1,
  knowledge_points: [
    {
      id: 'k1',
      name: '蛋白质一级结构',
      chapter_id: 'c1',
      document_id: 'd1',
      source_page: 5,
      source_slide: 2,
      source_locator: '第 5 页',
      review_status: 'approved',
    },
  ],
  reviewed_at: null,
  published_at: null,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
}

function listResponse(questions = [baseQuestion], total = 1) {
  return {
    questions,
    total,
    stats: {
      total,
      pending: questions.filter((item) => item.status === 'pending').length,
      approved: questions.filter((item) => item.status === 'approved').length,
      rejected: 0,
      needs_revision: 0,
    },
  }
}

function renderPage() {
  return render(
    <ToastProvider>
      <QuestionsPage />
    </ToastProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('QuestionsPage', () => {
  it('loads real questions, filters, and reviews a question', async () => {
    const calls: Array<{ url: string; method: string; body: string }> = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        calls.push({
          url,
          method: init?.method ?? 'GET',
          body: String(init?.body ?? ''),
        })
        if (url.endsWith('/subjects')) {
          return Promise.resolve(jsonResponse([subject]))
        }
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse([chapter]))
        }
        if (url.includes('/knowledge-points')) {
          return Promise.resolve(
            jsonResponse({
              points: [knowledge],
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
        if (url.includes('/questions/q1/review')) {
          return Promise.resolve(
            jsonResponse({ ...baseQuestion, status: 'approved' }),
          )
        }
        if (url.includes('/questions')) {
          return Promise.resolve(jsonResponse(listResponse()))
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }, 404))
      }),
    )

    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'AI 出题' }))
    expect(await screen.findByText('从已审核知识点出题')).toBeInTheDocument()
    expect(await screen.findByText('蛋白质一级结构由什么决定？')).toBeInTheDocument()

    fireEvent.click(
      await screen.findByRole('button', { name: '全选当前范围' }),
    )
    expect(await screen.findByText('已选 1/1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '清空' }))
    expect(await screen.findByText('已选 0/1')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('搜索可选知识点'), {
      target: { value: '一级结构' },
    })
    fireEvent.click(screen.getByRole('button', { name: '全选筛选结果' }))
    expect(await screen.findByText('已选 1/1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '反选' }))
    expect(await screen.findByText('已选 0/1')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('状态'), {
      target: { value: 'pending' },
    })
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === 'GET' &&
            call.url.includes('/questions?') &&
            call.url.includes('status=pending'),
        ),
      ).toBe(true),
    )

    fireEvent.click(screen.getByRole('button', { name: '查看' }))
    expect(await screen.findByRole('heading', { name: '蛋白质一级结构由什么决定？' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '通过' }))
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === 'POST' &&
            call.url.endsWith('/questions/q1/review') &&
            call.body.includes('"approved"'),
        ),
      ).toBe(true),
    )
  })
})
