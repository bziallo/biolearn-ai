import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

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
    expect(url).toBe('http://127.0.0.1:8000/api/v1/documents')
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
})
