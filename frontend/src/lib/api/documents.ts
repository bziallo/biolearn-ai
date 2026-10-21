import { apiRequest } from './client'
import type { KnowledgeJob } from './knowledge'

export type DocumentStatus =
  | 'uploaded'
  | 'parsing'
  | 'parsed'
  | 'failed'
  | 'needs_ocr'

export interface DocumentChunk {
  id: string
  chunk_index: number
  heading_path: string | null
  heading_level: number | null
  content: string
  page_start: number | null
  page_end: number | null
  slide_number: number | null
  char_start: number
  char_end: number
  location_label: string
}

export interface DocumentSummary {
  id: string
  subject_id: string
  chapter_id: string | null
  chapter_name: string | null
  name: string
  content_title: string | null
  original_filename: string
  mime_type: string
  extension: string
  size_bytes: number
  sha256: string
  status: DocumentStatus
  parse_error: string | null
  parse_warnings: string | null
  page_count: number | null
  slide_count: number | null
  chunk_count: number
  knowledge_point_count: number
  approved_count: number
  duplicate: boolean
  uploaded_at: string
  parsed_at: string | null
  created_at: string
  updated_at: string
}

export interface DocumentDetail extends DocumentSummary {
  chunks: DocumentChunk[]
  latest_job: KnowledgeJob | null
}

export function listDocuments(params: {
  subject_id?: string
  chapter_id?: string
  status?: DocumentStatus
}): Promise<DocumentSummary[]> {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      query.set(key, value)
    }
  })
  return apiRequest<DocumentSummary[]>(`/documents?${query.toString()}`)
}

export function getDocument(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentDetail> {
  return apiRequest<DocumentDetail>(`/documents/${documentId}`, { signal })
}

export function uploadDocument(
  formData: FormData,
  signal?: AbortSignal,
): Promise<DocumentSummary> {
  return apiRequest<DocumentSummary>(
    '/documents',
    {
      method: 'POST',
      body: formData,
      signal,
    },
    120_000,
  )
}

export function retryParse(documentId: string): Promise<DocumentSummary> {
  return apiRequest<DocumentSummary>(
    `/documents/${documentId}/retry-parse`,
    { method: 'POST' },
  )
}

export function updateDocument(
  documentId: string,
  input: {
    name?: string
    subject_id?: string
    chapter_id?: string | null
  },
): Promise<DocumentSummary> {
  return apiRequest<DocumentSummary>(`/documents/${documentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function extractKnowledge(documentId: string): Promise<KnowledgeJob> {
  return apiRequest<KnowledgeJob>(`/documents/${documentId}/extract`, {
    method: 'POST',
  })
}

export function deleteDocument(
  documentId: string,
  cascade: boolean,
): Promise<void> {
  return apiRequest<void>(
    `/documents/${documentId}?cascade=${cascade ? 'true' : 'false'}`,
    { method: 'DELETE' },
  )
}
