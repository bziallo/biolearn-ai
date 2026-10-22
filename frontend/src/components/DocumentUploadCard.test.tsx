import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { API_BASE_URL } from '../lib/api/client'
import { ToastProvider } from './ToastProvider'
import { DocumentUploadCard } from './DocumentUploadCard'

const uploadedDocument = {
  id: 'd1',
  subject_id: 's1',
  chapter_id: null,
  chapter_name: null,
  name: '蛋白质讲义',
  content_title: null,
  original_filename: 'protein.md',
  mime_type: 'text/markdown',
  extension: '.md',
  size_bytes: 12,
  sha256: 'a'.repeat(64),
  status: 'uploaded',
  parse_error: null,
  parse_warnings: null,
  page_count: null,
  slide_count: null,
  chunk_count: 0,
  knowledge_point_count: 0,
  approved_count: 0,
  uploaded_at: '2026-10-19T10:00:00',
  parsed_at: null,
  created_at: '2026-10-19T10:00:00',
  updated_at: '2026-10-19T10:00:00',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DocumentUploadCard', () => {
  it('uploads a selected file with the subject and name', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(uploadedDocument), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const onUploaded = vi.fn()

    render(
      <ToastProvider>
        <DocumentUploadCard
          subjectId="s1"
          tree={[]}
          onUploaded={onUploaded}
        />
      </ToastProvider>,
    )

    const file = new File(['# 蛋白质'], 'protein.md', {
      type: 'text/markdown',
    })
    fireEvent.change(screen.getByLabelText('选择文件'), {
      target: { files: [file] },
    })
    fireEvent.change(screen.getByLabelText('资料名称'), {
      target: { value: '蛋白质讲义' },
    })
    fireEvent.click(screen.getByRole('button', { name: '上传并解析' }))

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(uploadedDocument))
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    // The API base follows the runtime configuration (env override or the
    // same-origin default), so assert against the single source of truth.
    expect(url).toBe(`${API_BASE_URL}/documents`)
    const body = init.body as FormData
    expect(body.get('subject_id')).toBe('s1')
    expect(body.get('name')).toBe('蛋白质讲义')
    expect((body.get('file') as File).name).toBe('protein.md')
  })

  it('shows a duplicate prompt without pretending upload succeeded', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: {
              code: 'duplicate_document',
              message: '同一章节下已上传过相同内容的资料',
              existing_document_name: '旧蛋白质讲义',
            },
          }),
          { status: 409 },
        ),
      ),
    )
    const onUploaded = vi.fn()

    render(
      <ToastProvider>
        <DocumentUploadCard
          subjectId="s1"
          tree={[]}
          onUploaded={onUploaded}
        />
      </ToastProvider>,
    )

    fireEvent.change(screen.getByLabelText('选择文件'), {
      target: {
        files: [new File(['same'], 'same.txt', { type: 'text/plain' })],
      },
    })
    fireEvent.click(screen.getByRole('button', { name: '上传并解析' }))

    expect(await screen.findByText(/已有资料/)).toBeInTheDocument()
    expect(screen.getByText('旧蛋白质讲义', { exact: false })).toBeInTheDocument()
    expect(onUploaded).not.toHaveBeenCalled()
    expect(
      screen.getByRole('button', { name: '仍然上传' }),
    ).toBeInTheDocument()
  })

  it('rejects unsupported formats and files over 25 MB before upload', () => {
    vi.stubGlobal('fetch', vi.fn())
    render(
      <ToastProvider>
        <DocumentUploadCard subjectId="s1" tree={[]} onUploaded={vi.fn()} />
      </ToastProvider>,
    )

    fireEvent.change(screen.getByLabelText('选择文件'), {
      target: { files: [new File(['x'], 'slides.ppt', { type: 'application/vnd.ms-powerpoint' })] },
    })
    expect(screen.getByText(/不支持该文件格式/)).toBeInTheDocument()

    const large = new File(['x'], 'large.pdf', { type: 'application/pdf' })
    Object.defineProperty(large, 'size', { value: 26 * 1024 * 1024 })
    fireEvent.change(screen.getByLabelText('选择文件'), {
      target: { files: [large] },
    })
    expect(screen.getByText(/超过 25 MB/)).toBeInTheDocument()
  })

  it('keeps the selected file and offers a retry after a network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))
    const onUploaded = vi.fn()
    render(
      <ToastProvider>
        <DocumentUploadCard subjectId="s1" tree={[]} onUploaded={onUploaded} />
      </ToastProvider>,
    )

    fireEvent.change(screen.getByLabelText('选择文件'), {
      target: { files: [new File(['# x'], 'protein.md', { type: 'text/markdown' })] },
    })
    fireEvent.click(screen.getByRole('button', { name: '上传并解析' }))

    expect(await screen.findByText(/网络中断/)).toBeInTheDocument()
    expect(screen.getByText(/已选择：protein.md/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重试上传' })).toBeInTheDocument()
    expect(onUploaded).not.toHaveBeenCalled()
  })

})
