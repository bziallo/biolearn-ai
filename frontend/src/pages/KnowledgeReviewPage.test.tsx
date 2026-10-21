import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import { KnowledgeReviewPage } from './KnowledgeReviewPage'

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

const point = {
  id: 'p1',
  subject_id: 's1',
  chapter_id: null,
  document_id: 'd1',
  parent_id: null,
  name: '蛋白质一级结构',
  type: 'structure',
  explanation: '蛋白质的一级结构是氨基酸的线性排列顺序。',
  core_points: ['氨基酸序列'],
  conditions: null,
  source_quote: '蛋白质由氨基酸通过肽键连接。',
  source_quote_verified: true,
  source_page: 1,
  source_page_end: 1,
  source_slide: null,
  source_locator: '第 1 页',
  source_chunk_id: 'c1',
  confidence: 0.92,
  review_note: null,
  needs_review: false,
  origin: 'ai',
  review_status: 'pending',
  duplicate_of_id: null,
  reviewed_at: null,
  published_at: null,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
  children: [],
}

const runningJob = {
  id: 'j1',
  document_id: 'd1',
  status: 'extracting',
  stage: '提取第 1/2 块',
  progress: 25,
  error: null,
  cancel_requested: false,
  attempts: 1,
  provider: 'openai-compatible',
  model: 'test-model',
  total_chunks: 2,
  processed_chunks: 1,
  extracted_count: 2,
  merged_count: 0,
  duplicate_count: 0,
  created_at: '2026-10-19T10:00:00',
  started_at: '2026-10-19T10:00:01',
  finished_at: null,
  updated_at: '2026-10-19T10:00:02',
}

const documentDetail = {
  id: 'd1',
  subject_id: 's1',
  chapter_id: null,
  chapter_name: null,
  name: '蛋白质讲义',
  content_title: '蛋白质',
  original_filename: 'protein.md',
  mime_type: 'text/markdown',
  extension: '.md',
  size_bytes: 2048,
  sha256: 'a'.repeat(64),
  status: 'parsed',
  parse_error: null,
  parse_warnings: null,
  page_count: null,
  slide_count: null,
  chunk_count: 1,
  knowledge_point_count: 0,
  approved_count: 0,
  uploaded_at: '2026-10-19T10:00:00',
  parsed_at: '2026-10-19T10:01:00',
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:01:00',
  chunks: [],
  latest_job: runningJob,
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('KnowledgeReviewPage', () => {
  it('loads the review tree, stats, detail and source evidence', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/documents/d1/knowledge-points')) {
          return Promise.resolve(
            jsonResponse({
              document: {
                id: 'd1',
                name: '蛋白质讲义',
                status: 'parsed',
                chunk_count: 1,
              },
              stats: {
                total: 1,
                pending: 1,
                approved: 0,
                needs_revision: 0,
                ignored: 0,
                needs_review: 0,
                duplicates: 0,
                failed_jobs: 0,
              },
              points: [point],
              latest_job: null,
            }),
          )
        }
        if (url.endsWith('/documents/d1')) {
          return Promise.resolve(
            jsonResponse({
              id: 'd1',
              subject_id: 's1',
              chapter_id: null,
              chapter_name: null,
              name: '蛋白质讲义',
              content_title: '蛋白质',
              original_filename: 'protein.md',
              mime_type: 'text/markdown',
              extension: '.md',
              size_bytes: 2048,
              sha256: 'a'.repeat(64),
              status: 'parsed',
              parse_error: null,
              parse_warnings: null,
              page_count: null,
              slide_count: null,
              chunk_count: 1,
              knowledge_point_count: 1,
              approved_count: 0,
              uploaded_at: '2026-10-19T10:00:00',
              parsed_at: '2026-10-19T10:01:00',
              created_at: '2026-10-19T10:00:00',
              updated_at: '2026-10-19T10:01:00',
              chunks: [],
              latest_job: null,
            }),
          )
        }
        if (url.endsWith('/ai/status')) {
          return Promise.resolve(
            jsonResponse({
              configured: false,
              provider: 'openai-compatible',
              model: '',
              api_base: '',
              key_configured: false,
              source: 'unconfigured',
              message: 'AI 未配置。请在 .env 中设置模型参数。',
            }),
          )
        }
        if (url.endsWith('/knowledge-points/p1')) {
          return Promise.resolve(
            jsonResponse({
              ...point,
              document_name: '蛋白质讲义',
              subject_name: '生物化学',
              chapter_name: null,
              source_chunk_content: '蛋白质由氨基酸通过肽键连接。',
              source_chunk_heading: '蛋白质',
            }),
          )
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }))
      }),
    )

    render(
      <MemoryRouter initialEntries={['/documents/d1/review']}>
        <ToastProvider>
          <Routes>
            <Route
              path="/documents/:documentId/review"
              element={<KnowledgeReviewPage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByText('蛋白质讲义')).toBeInTheDocument()
    expect(screen.getByText('AI 未配置')).toBeInTheDocument()
    expect(screen.getAllByText('蛋白质一级结构').length).toBeGreaterThan(0)
    expect(
      await screen.findByText('蛋白质的一级结构是氨基酸的线性排列顺序。'),
    ).toBeInTheDocument()
    expect(
      screen.getAllByText('蛋白质由氨基酸通过肽键连接。').length,
    ).toBeGreaterThan(0)
    expect(screen.getByText('✓ 原文匹配')).toBeInTheDocument()
  })

  it('requests a stop for a running extraction and shows cancelling state', async () => {    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.endsWith('/knowledge-jobs/j1/cancel')) {
          expect(init?.method).toBe('POST')
          return Promise.resolve(
            jsonResponse({
              ...runningJob,
              status: 'cancelling',
              stage: '正在停止，等待当前模型请求结束',
              cancel_requested: true,
            }),
          )
        }
        if (url.endsWith('/knowledge-jobs/j1')) {
          return Promise.resolve(jsonResponse(runningJob))
        }
        if (url.endsWith('/documents/d1/knowledge-points')) {
          return Promise.resolve(
            jsonResponse({
              document: {
                id: 'd1',
                name: '蛋白质讲义',
                status: 'parsed',
                chunk_count: 1,
              },
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
              points: [],
              latest_job: runningJob,
            }),
          )
        }
        if (url.endsWith('/documents/d1')) {
          return Promise.resolve(jsonResponse(documentDetail))
        }
        if (url.endsWith('/ai/status')) {
          return Promise.resolve(
            jsonResponse({
              configured: true,
              provider: 'openai-compatible',
              model: 'test-model',
              api_base: 'http://ai.test/v1',
              key_configured: true,
              source: 'runtime',
              message: 'AI 已配置',
            }),
          )
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }))
      }),
    )

    render(
      <MemoryRouter initialEntries={['/documents/d1/review']}>
        <ToastProvider>
          <Routes>
            <Route
              path="/documents/:documentId/review"
              element={<KnowledgeReviewPage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    )

    const stopButton = await screen.findByRole('button', {
      name: '停止 AI 识别',
    })
    fireEvent.click(stopButton)
    expect(
      await screen.findByRole('button', { name: '正在停止…' }),
    ).toBeInTheDocument()
  })

  it('asks for confirmation before re-extracting an existing chapter', async () => {
    let extractCalled = false
    const completedJob = {
      ...runningJob,
      status: 'completed',
      stage: '知识点草稿已生成',
      progress: 100,
      processed_chunks: 66,
      extracted_count: 39,
      merged_count: 39,
      finished_at: '2026-10-19T10:10:00',
    }

    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/documents/d1/extract')) {
          extractCalled = true
          return Promise.resolve(jsonResponse(completedJob))
        }
        if (url.endsWith('/documents/d1/knowledge-points')) {
          return Promise.resolve(
            jsonResponse({
              document: {
                id: 'd1',
                name: '蛋白质讲义',
                status: 'parsed',
                chunk_count: 1,
              },
              stats: {
                total: 1,
                pending: 1,
                approved: 0,
                needs_revision: 0,
                ignored: 0,
                needs_review: 0,
                duplicates: 0,
                failed_jobs: 0,
              },
              points: [point],
              latest_job: completedJob,
            }),
          )
        }
        if (url.endsWith('/documents/d1')) {
          return Promise.resolve(
            jsonResponse({
              ...documentDetail,
              knowledge_point_count: 1,
              latest_job: completedJob,
            }),
          )
        }
        if (url.endsWith('/ai/status')) {
          return Promise.resolve(
            jsonResponse({
              configured: true,
              provider: 'openai-compatible',
              model: 'test-model',
              api_base: 'http://ai.test/v1',
              key_configured: true,
              source: 'runtime',
              message: 'AI 已配置',
            }),
          )
        }
        if (url.endsWith('/knowledge-points/p1')) {
          return Promise.resolve(
            jsonResponse({
              ...point,
              document_name: '蛋白质讲义',
              subject_name: '生物化学',
              chapter_name: null,
              source_chunk_content: '蛋白质由氨基酸通过肽键连接。',
              source_chunk_heading: '蛋白质',
            }),
          )
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }))
      }),
    )

    render(
      <MemoryRouter initialEntries={['/documents/d1/review']}>
        <ToastProvider>
          <Routes>
            <Route
              path="/documents/:documentId/review"
              element={<KnowledgeReviewPage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    )

    fireEvent.click(
      await screen.findByRole('button', { name: '重新识别整章' }),
    )
    expect(
      await screen.findByText(/当前资料已有知识点/),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(extractCalled).toBe(false)
  })
})
