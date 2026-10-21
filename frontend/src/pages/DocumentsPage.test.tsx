import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import { DocumentsPage } from './DocumentsPage'

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

const subject = {
  id: 's1',
  name: '生物化学',
  description: '蛋白质',
  color: '#2dd4bf',
  icon: '🧬',
  sort_order: 0,
  chapter_count: 0,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
}

const document = {
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
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DocumentsPage', () => {
  it('lists documents and opens the parsed chunk viewer', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.endsWith('/subjects')) {
          return Promise.resolve(jsonResponse([subject]))
        }
        if (url.endsWith('/subjects/s1')) {
          return Promise.resolve(jsonResponse(subject))
        }
        if (url.includes('/documents?')) {
          return Promise.resolve(jsonResponse([document]))
        }
        if (url.endsWith('/documents/d1')) {
          return Promise.resolve(
            jsonResponse({
              ...document,
              chunks: [
                {
                  id: 'c1',
                  chunk_index: 0,
                  heading_path: '蛋白质',
                  heading_level: 1,
                  content: '蛋白质由氨基酸通过肽键连接。',
                  page_start: 1,
                  page_end: 1,
                  slide_number: null,
                  char_start: 0,
                  char_end: 15,
                  location_label: '第 1 页',
                },
              ],
              latest_job: null,
            }),
          )
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }))
      }),
    )

    render(
      <MemoryRouter initialEntries={['/subjects/s1/documents']}>
        <ToastProvider>
          <Routes>
            <Route
              path="/subjects/:subjectId/documents"
              element={<DocumentsPage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByText('蛋白质讲义')).toBeInTheDocument()
    expect(screen.getAllByText('已解析').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: '查看解析' }))
    expect(
      await screen.findByText('蛋白质由氨基酸通过肽键连接。'),
    ).toBeInTheDocument()
    expect(screen.getByText('第 1 页')).toBeInTheDocument()
  })

  it('adjusts document attribution through PATCH', async () => {
    let patched = false
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.endsWith('/subjects')) {
          return Promise.resolve(jsonResponse([subject]))
        }
        if (url.endsWith('/subjects/s1')) {
          return Promise.resolve(jsonResponse(subject))
        }
        if (url.includes('/documents?')) {
          return Promise.resolve(jsonResponse([document]))
        }
        if (url.endsWith('/documents/d1') && init?.method === 'PATCH') {
          patched = true
          return Promise.resolve(
            jsonResponse({
              ...document,
              chapter_id: null,
              chapter_name: null,
            }),
          )
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }))
      }),
    )

    render(
      <MemoryRouter initialEntries={['/subjects/s1/documents']}>
        <ToastProvider>
          <Routes>
            <Route
              path="/subjects/:subjectId/documents"
              element={<DocumentsPage />}
            />
          </Routes>
        </ToastProvider>
      </MemoryRouter>,
    )

    expect(await screen.findByText('蛋白质讲义')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '调整归属' }))
    expect(await screen.findByText('调整资料归属')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '保存归属' }))
    expect(await screen.findByText('资料归属已更新')).toBeInTheDocument()
    expect(patched).toBe(true)
  })
})
