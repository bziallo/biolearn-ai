import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import type { Subject } from '../lib/api'
import { SubjectsPage } from './SubjectsPage'

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function makeSubject(overrides: Partial<Subject> = {}): Subject {
  return {
    id: 's1',
    name: '生物化学',
    description: '从分子层面理解生命过程。',
    color: '#2dd4bf',
    icon: '🧬',
    sort_order: 0,
    chapter_count: 2,
    created_at: '2026-10-19T10:00:00',
    updated_at: '2026-10-19T10:00:00',
    ...overrides,
  }
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <SubjectsPage />
      </ToastProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SubjectsPage', () => {
  it('renders subjects loaded from the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse([
          makeSubject(),
          makeSubject({
            id: 's2',
            name: '微生物学',
            chapter_count: 5,
            color: '#38bdf8',
            icon: '🦠',
          }),
        ]),
      ),
    )

    renderPage()

    expect(await screen.findByText('生物化学')).toBeInTheDocument()
    expect(screen.getByText('微生物学')).toBeInTheDocument()
    expect(screen.getByText('2 章')).toBeInTheDocument()
    expect(screen.getByText('5 章')).toBeInTheDocument()
    expect(screen.getByText('数据来自本地 SQLite')).toBeInTheDocument()
  })

  it('shows an empty state when the database has no subjects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])))

    renderPage()

    expect(await screen.findByText('还没有学科')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: '创建第一个学科' }),
    ).toBeInTheDocument()
  })

  it('shows the backend error instead of falling back to fake data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: {
              code: 'database_unavailable',
              message: '数据库暂时不可用',
            },
          },
          500,
        ),
      ),
    )

    renderPage()

    expect(await screen.findByText(/无法加载学科/)).toBeInTheDocument()
    expect(screen.getByText(/数据库暂时不可用/)).toBeInTheDocument()
  })
})
