import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import { PracticePage } from './PracticePage'

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
  name: '蛋白质一级结构',
  chapter_id: 'c1',
  document_id: 'd1',
  source_page: 5,
  source_slide: 2,
  source_locator: '第 5 页',
  review_status: 'approved',
}

const singleQuestion = {
  id: 'q1',
  type: 'single_choice',
  stem: '蛋白质一级结构由什么决定？',
  options: [
    { key: 'A', text: '氨基酸序列' },
    { key: 'B', text: '空间结构' },
  ],
  difficulty: 'easy',
  chapter_id: 'c1',
  knowledge_points: [knowledge],
}

const shortQuestion = {
  id: 'q2',
  type: 'short_answer',
  stem: '简述蛋白质一级结构。',
  options: [],
  difficulty: 'medium',
  chapter_id: 'c1',
  knowledge_points: [knowledge],
}

const session = {
  id: 'ps1',
  subject_id: 's1',
  subject_name: '生物化学',
  chapter_id: 'c1',
  chapter_name: '蛋白质',
  status: 'in_progress',
  total_questions: 2,
  answered_count: 0,
  correct_count: 0,
  pending_manual_count: 0,
  score: null,
  started_at: '2026-10-19T10:00:00',
  finished_at: null,
  questions: [singleQuestion, shortQuestion],
}

function resultAnswer(
  id: string,
  question: typeof singleQuestion | typeof shortQuestion,
  overrides: Record<string, unknown> = {},
) {
  return {
    id,
    question: {
      ...question,
      subject_id: 's1',
      subject_name: '生物化学',
      chapter_name: '蛋白质',
      source_document_id: 'd1',
      source_document_name: '蛋白质讲义',
      generation_job_id: null,
      duplicate_of_id: null,
      duplicate_reason: null,
      answer: question.id === 'q1' ? { choices: ['A'] } : { text: '氨基酸序列。' },
      grading_rule: { mode: 'choice_exact' },
      explanation: '解析内容。',
      status: 'approved',
      origin: 'manual',
      source_locator: '第 5 页',
      ai_provider: '',
      ai_model: '',
      confidence: null,
      review_note: null,
      score: 1,
      reviewed_at: '2026-10-19T10:00:00',
      published_at: '2026-10-19T10:00:00',
      created_at: '2026-10-19T10:00:00',
      updated_at: '2026-10-19T10:00:00',
    },
    user_answer: question.id === 'q1' ? { choices: ['A'] } : { text: '氨基酸序列' },
    is_correct: question.id === 'q1' ? true : null,
    score: question.id === 'q1' ? 1 : null,
    max_score: 1,
    feedback: question.id === 'q1' ? '回答正确' : '等待人工评分',
    graded_by: question.id === 'q1' ? 'auto' : 'pending',
    answered_at: '2026-10-19T10:00:00',
    ...overrides,
  }
}

const result = {
  session: {
    ...session,
    status: 'completed',
    answered_count: 2,
    correct_count: 1,
    pending_manual_count: 1,
    score: null,
    finished_at: '2026-10-19T10:00:10',
  },
  answers: [
    resultAnswer('a1', singleQuestion),
    resultAnswer('a2', shortQuestion),
  ],
}

const gradedResult = {
  ...result,
  session: {
    ...result.session,
    correct_count: 2,
    pending_manual_count: 0,
    score: 100,
  },
  answers: [
    result.answers[0],
    resultAnswer('a2', shortQuestion, {
      is_correct: true,
      score: 1,
      feedback: '人工确认',
      graded_by: 'manual',
    }),
  ],
}

function renderPage() {
  return render(
    <ToastProvider>
      <PracticePage />
    </ToastProvider>,
  )
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('PracticePage', () => {
  it('starts a session, submits answers, and manually grades a short answer', async () => {
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
        if (url.includes('/practice/wrong-questions')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.endsWith('/practice/sessions') && init?.method === 'POST') {
          return Promise.resolve(jsonResponse(session))
        }
        if (url.includes('/practice/sessions/ps1/submit')) {
          return Promise.resolve(jsonResponse(result))
        }
        if (url.includes('/practice/answers/a2/grade')) {
          return Promise.resolve(jsonResponse(gradedResult))
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }, 404))
      }),
    )

    renderPage()
    await screen.findByText('开始一组练习')
    fireEvent.click(screen.getByRole('button', { name: '开始练习' }))
    expect(await screen.findByText('蛋白质一级结构由什么决定？')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('radio')[0])
    fireEvent.change(
      screen.getByPlaceholderText('写下你的答案，提交后由人工评分'),
      { target: { value: '氨基酸序列' } },
    )
    fireEvent.click(screen.getByRole('button', { name: '提交答案' }))

    expect(
      await screen.findByRole('heading', { name: '等待人工评分' }),
    ).toBeInTheDocument()
    expect(await screen.findByText('空间结构')).toBeInTheDocument()
    expect(screen.getAllByText('正确答案').length).toBeGreaterThan(0)
    expect(screen.getByText('你的选择')).toBeInTheDocument()

    fireEvent.change(screen.getByRole('spinbutton'), {
      target: { value: '0.9' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存评分' }))
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === 'POST' &&
            call.url.includes('/practice/answers/a2/grade') &&
            call.body.includes('0.9'),
        ),
      ).toBe(true),
    )
    expect(await screen.findByText('得分 100')).toBeInTheDocument()
  })
})
