import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ToastProvider } from '../components/ToastProvider'
import { ImportPage } from './ImportPage'

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

const preferences = {
  default_subject_id: 's1',
  default_subject_name: '生物化学',
  default_chapter_id: 'c1',
  default_chapter_name: '蛋白质',
  default_mode: 'preset',
  auto_analyze: false,
  require_preview: false,
  uncertain_policy: 'confirm',
  updated_at: '2026-10-19T10:00:00',
}

const baseJob = {
  id: 'i1',
  document_id: 'd1',
  document_name: 'lecture.pptx',
  document_status: 'parsed',
  status: 'completed',
  stage: '资料已归档',
  progress: 100,
  mode: 'preset',
  auto_analyze: false,
  require_preview: false,
  uncertain_policy: 'confirm',
  suggestion: null,
  result: {
    subject_id: 's1',
    chapter_id: 'c1',
    chapter_name: '蛋白质',
    created_chapter_ids: [],
    reused_chapter_ids: ['c1'],
    chapter_path: ['蛋白质'],
    duplicate: false,
  },
  error: null,
  analysis_job_id: null,
  analysis_status: 'not_started',
  analysis_error: null,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
  finished_at: '2026-10-19T10:00:01',
}

const suggestion = {
  title: '蛋白质的结构与功能',
  subject_id: 's1',
  subject_name: '生物化学',
  subject_confidence: 0.9,
  subject_reason: null,
  outline_source: 'toc',
  chapters: [
    {
      name: '蛋白质的结构与功能',
      level: 1,
      parent_index: null,
      action: 'create',
      existing_chapter_id: null,
      existing_path: null,
      confidence: 0.9,
      source_slide: null,
      source_kind: 'document_title',
      reason: '资料标题',
    },
    {
      name: '第一章 蛋白质的分子结构',
      level: 2,
      parent_index: 0,
      action: 'create',
      existing_chapter_id: null,
      existing_path: null,
      confidence: 0.9,
      source_slide: 2,
      source_kind: 'toc',
      reason: '来自目录',
    },
  ],
  confidence: 0.9,
  needs_confirmation: false,
  reasons: ['检测到目录页（第 2 张幻灯片）'],
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/import']}>
      <ToastProvider>
        <Routes>
          <Route path="/import" element={<ImportPage />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ImportPage', () => {
  it('uses saved defaults and imports into the preset chapter', async () => {
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        calls.push(`${init?.method ?? 'GET'} ${url}`)
        if (url.endsWith('/imports/preferences')) {
          return Promise.resolve(jsonResponse(preferences))
        }
        if (url.endsWith('/subjects')) {
          return Promise.resolve(jsonResponse([subject]))
        }
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse([chapter]))
        }
        if (url.endsWith('/imports')) {
          return Promise.resolve(jsonResponse(baseJob, 201))
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }, 404))
      }),
    )

    const { container } = renderPage()
    expect(await screen.findByText('智能资料导入')).toBeInTheDocument()
    expect(await screen.findByText('归入预设章节')).toBeInTheDocument()
    expect(await screen.findByDisplayValue('生物化学')).toBeInTheDocument()

    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement
    const file = new File(['demo'], 'lecture.pptx', {
      type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    })
    fireEvent.change(fileInput, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: '开始导入' }))

    expect(await screen.findByText('归档完成')).toBeInTheDocument()
    expect(
      calls.some((call) => call.startsWith('POST') && call.includes('/imports')),
    ).toBe(true)
  })

  it('shows the suggested tree and confirms archive', async () => {
    const pendingJob = {
      ...baseJob,
      status: 'awaiting_confirmation',
      stage: '等待确认归档结构',
      progress: 50,
      result: null,
      suggestion,
      finished_at: null,
    }
    const confirmedJob = {
      ...baseJob,
      status: 'completed',
      stage: '资料已归档',
      suggestion,
    }
    let confirmBody = ''
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.endsWith('/imports/preferences')) {
          return Promise.resolve(jsonResponse(preferences))
        }
        if (url.endsWith('/subjects')) {
          return Promise.resolve(jsonResponse([subject]))
        }
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse([chapter]))
        }
        if (url.endsWith('/imports/i1/confirm')) {
          confirmBody = String(init?.body ?? '')
          return Promise.resolve(jsonResponse(confirmedJob))
        }
        if (url.endsWith('/imports')) {
          return Promise.resolve(jsonResponse(pendingJob, 201))
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }, 404))
      }),
    )

    const { container } = renderPage()
    await screen.findByText('智能资料导入')
    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement
    fireEvent.change(fileInput, {
      target: {
        files: [
          new File(['demo'], 'lecture.pptx', {
            type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
          }),
        ],
      },
    })
    fireEvent.click(screen.getByRole('button', { name: '开始导入' }))

    expect(
      await screen.findByText('第一章 蛋白质的分子结构'),
    ).toBeInTheDocument()
    expect(screen.getByText('检测到目录页（第 2 张幻灯片）')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '按建议归档' }))

    expect(await screen.findByText('归档完成')).toBeInTheDocument()
    expect(confirmBody).toContain('"accept_suggestions":true')
  })

  it('saves the current selection as default preferences', async () => {
    let savedBody = ''
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.endsWith('/imports/preferences')) {
          if (init?.method === 'PUT') {
            savedBody = String(init.body ?? '')
            return Promise.resolve(jsonResponse(preferences))
          }
          return Promise.resolve(jsonResponse(preferences))
        }
        if (url.endsWith('/subjects')) {
          return Promise.resolve(jsonResponse([subject]))
        }
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse([chapter]))
        }
        if (url.endsWith('/imports')) {
          return Promise.resolve(jsonResponse([]))
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }, 404))
      }),
    )

    renderPage()
    await screen.findByText('智能资料导入')
    fireEvent.click(screen.getByRole('button', { name: '默认设置' }))
    fireEvent.click(screen.getByRole('button', { name: '保存为默认设置' }))
    expect(
      await screen.findByText('默认导入设置已保存'),
    ).toBeInTheDocument()
    expect(savedBody).toContain('"default_subject_id":"s1"')
  })

  it('previews and confirms an external AI JSON import', async () => {
    const externalSuggestion = {
      ...suggestion,
      source_type: 'external_json',
      outline_source: 'external_json',
      knowledge_point_count: 2,
      duplicate_point_count: 1,
      missing_source_count: 1,
      duplicate_import: false,
      points_preview: [
        {
          point_id: 'kp-1',
          title: '一级结构',
          chapter_path: ['第一章 蛋白质的分子结构'],
          category: 'structure',
          importance: 'high',
          source_page: 5,
          source_slide: null,
          duplicate_of_id: null,
          duplicate_of_title: null,
          warnings: [],
        },
        {
          point_id: 'kp-2',
          title: '已有概念',
          chapter_path: [],
          category: 'basic_concept',
          importance: null,
          source_page: null,
          source_slide: null,
          duplicate_of_id: 'p1',
          duplicate_of_title: '已有概念',
          warnings: ['缺少来源页码/幻灯片'],
        },
      ],
    }
    const pendingExternal = {
      ...baseJob,
      id: 'i2',
      document_id: 'd2',
      source_type: 'external_json',
      status: 'awaiting_confirmation',
      stage: '外部 AI JSON 已校验，等待确认归档',
      progress: 50,
      suggestion: externalSuggestion,
      result: null,
    }
    const confirmedExternal = {
      ...pendingExternal,
      status: 'completed',
      stage: '外部 AI 知识点已导入，等待人工审核',
      progress: 100,
      result: {
        ...baseJob.result,
        document_id: 'd2',
        knowledge_point_count: 2,
        created_point_count: 1,
        updated_point_count: 0,
        skipped_point_count: 1,
      },
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.endsWith('/imports/preferences')) {
          return Promise.resolve(jsonResponse(preferences))
        }
        if (url.endsWith('/subjects')) {
          return Promise.resolve(jsonResponse([subject]))
        }
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse([chapter]))
        }
        if (url.endsWith('/imports') && (!init?.method || init.method === 'GET')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.endsWith('/imports/external')) {
          return Promise.resolve(jsonResponse(pendingExternal, 201))
        }
        if (url.endsWith('/imports/i2/confirm')) {
          return Promise.resolve(jsonResponse(confirmedExternal))
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }, 404))
      }),
    )

    const { container } = renderPage()
    await screen.findByText('智能资料导入')
    fireEvent.click(
      screen.getByRole('tab', { name: '导入 AI 预处理 JSON' }),
    )
    const fileInput = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement
    const file = new File(['{}'], 'external.json', {
      type: 'application/json',
    })
    fireEvent.change(fileInput, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: '开始导入' }))

    expect(await screen.findByText('重复：已有概念')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '按建议归档' }))
    expect(await screen.findByText(/新建 1/)).toBeInTheDocument()
  })

  it('loads the external AI prompt template', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/imports/preferences')) {
          return Promise.resolve(jsonResponse(preferences))
        }
        if (url.endsWith('/subjects')) {
          return Promise.resolve(jsonResponse([subject]))
        }
        if (url.endsWith('/subjects/s1/chapters')) {
          return Promise.resolve(jsonResponse([chapter]))
        }
        if (url.endsWith('/imports')) {
          return Promise.resolve(jsonResponse([]))
        }
        if (url.endsWith('/imports/external/template')) {
          return Promise.resolve(
            jsonResponse({
              schema_version: '1.0',
              json_schema: { type: 'object' },
              prompt: '请严格输出 schema_version 1.0 的 JSON',
              example: { schema_version: '1.0' },
            }),
          )
        }
        return Promise.resolve(jsonResponse({ detail: 'not found' }, 404))
      }),
    )

    renderPage()
    await screen.findByText('智能资料导入')
    fireEvent.click(screen.getByRole('button', { name: '查看导入模板' }))
    expect(
      await screen.findByText('请严格输出 schema_version 1.0 的 JSON'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '复制提示词' })).toBeInTheDocument()
  })
})
