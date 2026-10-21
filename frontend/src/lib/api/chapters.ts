import { apiRequest } from './client'

export interface Chapter {
  id: string
  subject_id: string
  parent_id: string | null
  name: string
  description: string
  sort_order: number
  source_document_id?: string | null
  source_import_job_id?: string | null
  source_slide?: number | null
  created_at: string
  updated_at: string
}

export interface ChapterNode extends Chapter {
  children: ChapterNode[]
}

export interface ChapterPathItem {
  id: string
  name: string
}

export interface ChapterDetail extends Chapter {
  subject: {
    id: string
    name: string
    color: string | null
    icon: string | null
  }
  parent: { id: string; name: string } | null
  path: ChapterPathItem[]
  descendant_count: number
}

export interface ChapterInput {
  name: string
  description?: string
  parent_id?: string | null
}

export type ChapterUpdateInput = Partial<ChapterInput>

export function listSubjectChapters(
  subjectId: string,
  signal?: AbortSignal,
): Promise<ChapterNode[]> {
  return apiRequest<ChapterNode[]>(`/subjects/${subjectId}/chapters`, {
    signal,
  })
}

export function getChapter(
  chapterId: string,
  signal?: AbortSignal,
): Promise<ChapterDetail> {
  return apiRequest<ChapterDetail>(`/chapters/${chapterId}`, { signal })
}

export function createChapter(
  subjectId: string,
  input: ChapterInput,
): Promise<Chapter> {
  return apiRequest<Chapter>(`/subjects/${subjectId}/chapters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateChapter(
  chapterId: string,
  input: ChapterUpdateInput,
): Promise<Chapter> {
  return apiRequest<Chapter>(`/chapters/${chapterId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteChapter(
  chapterId: string,
  cascade: boolean,
): Promise<void> {
  return apiRequest<void>(
    `/chapters/${chapterId}?cascade=${cascade ? 'true' : 'false'}`,
    { method: 'DELETE' },
  )
}

export function moveChapter(
  chapterId: string,
  direction: 'up' | 'down',
): Promise<Chapter> {
  return apiRequest<Chapter>(`/chapters/${chapterId}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction }),
  })
}
