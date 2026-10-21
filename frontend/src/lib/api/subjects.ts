import { apiRequest } from './client'

export interface Subject {
  id: string
  name: string
  description: string
  color: string | null
  icon: string | null
  sort_order: number
  chapter_count: number
  created_at: string
  updated_at: string
}

export interface SubjectInput {
  name: string
  description?: string
  color?: string | null
  icon?: string | null
}

export function listSubjects(signal?: AbortSignal): Promise<Subject[]> {
  return apiRequest<Subject[]>('/subjects', { signal })
}

export function getSubject(
  subjectId: string,
  signal?: AbortSignal,
): Promise<Subject> {
  return apiRequest<Subject>(`/subjects/${subjectId}`, { signal })
}

export function createSubject(input: SubjectInput): Promise<Subject> {
  return apiRequest<Subject>('/subjects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateSubject(
  subjectId: string,
  input: SubjectInput,
): Promise<Subject> {
  return apiRequest<Subject>(`/subjects/${subjectId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function deleteSubject(
  subjectId: string,
  cascade: boolean,
): Promise<void> {
  return apiRequest<void>(
    `/subjects/${subjectId}?cascade=${cascade ? 'true' : 'false'}`,
    { method: 'DELETE' },
  )
}
