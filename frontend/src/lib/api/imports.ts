import { apiRequest } from './client'

export type ImportMode = 'preset' | 'auto_create' | 'smart_archive'
export type UncertainPolicy = 'confirm' | 'use_default' | 'create'
export type SuggestedAction = 'create' | 'reuse' | 'uncertain'

export interface ImportPreferences {
  default_subject_id: string | null
  default_subject_name: string | null
  default_chapter_id: string | null
  default_chapter_name: string | null
  default_mode: ImportMode
  auto_analyze: boolean
  require_preview: boolean
  uncertain_policy: UncertainPolicy
  updated_at: string | null
}

export interface ImportPreferencesInput {
  default_subject_id: string | null
  default_chapter_id: string | null
  default_mode: ImportMode
  auto_analyze: boolean
  require_preview: boolean
  uncertain_policy: UncertainPolicy
}

export interface SuggestedChapter {
  name: string
  level: number
  parent_index: number | null
  action: SuggestedAction
  existing_chapter_id: string | null
  existing_path: string | null
  confidence: number
  source_slide: number | null
  source_kind: string
  reason: string | null
}

export interface ImportSuggestion {
  title: string
  subject_id: string
  subject_name: string
  subject_confidence: number
  subject_reason: string | null
  outline_source: string
  chapters: SuggestedChapter[]
  confidence: number
  needs_confirmation: boolean
  reasons: string[]
  source_type: string
  knowledge_point_count: number
  duplicate_point_count: number
  missing_source_count: number
  points_preview: ExternalPointPreview[]
  duplicate_import: boolean
}

export interface ExternalPointPreview {
  point_id: string | null
  title: string
  chapter_path: string[]
  category: string
  importance: string | null
  source_page: number | null
  source_slide: number | null
  duplicate_of_id: string | null
  duplicate_of_title: string | null
  warnings: string[]
}

export interface ImportResult {
  subject_id: string
  chapter_id: string | null
  chapter_name: string | null
  created_chapter_ids: string[]
  reused_chapter_ids: string[]
  chapter_path: string[]
  duplicate: boolean
  knowledge_point_count: number
  created_point_count: number
  updated_point_count: number
  skipped_point_count: number
  warning_count: number
}

export interface ImportJob {
  id: string
  document_id: string
  document_name: string
  document_status: string
  status: string
  stage: string
  progress: number
  mode: ImportMode
  source_type: string
  duplicate_strategy: string | null
  auto_analyze: boolean
  require_preview: boolean
  uncertain_policy: UncertainPolicy
  suggestion: ImportSuggestion | null
  result: ImportResult | null
  error: string | null
  analysis_job_id: string | null
  analysis_status: string
  analysis_error: string | null
  timings: Record<string, unknown> | null
  created_at: string
  updated_at: string
  finished_at: string | null
}

export interface ExternalTemplate {
  schema_version: string
  json_schema: Record<string, unknown>
  prompt: string
  example: Record<string, unknown>
}

export interface ImportConfirmInput {
  accept_suggestions: boolean
  subject_id?: string | null
  chapter_id?: string | null
  create_missing?: boolean
  auto_analyze?: boolean | null
}

export function getImportPreferences(
  signal?: AbortSignal,
): Promise<ImportPreferences> {
  return apiRequest<ImportPreferences>('/imports/preferences', { signal })
}

export function updateImportPreferences(
  input: ImportPreferencesInput,
): Promise<ImportPreferences> {
  return apiRequest<ImportPreferences>('/imports/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function listImports(signal?: AbortSignal): Promise<ImportJob[]> {
  return apiRequest<ImportJob[]>('/imports', { signal })
}

export function getImport(
  importId: string,
  signal?: AbortSignal,
): Promise<ImportJob> {
  return apiRequest<ImportJob>(`/imports/${importId}`, { signal })
}

export function createImport(
  formData: FormData,
  signal?: AbortSignal,
): Promise<ImportJob> {
  return apiRequest<ImportJob>(
    '/imports',
    { method: 'POST', body: formData, signal },
    120_000,
  )
}

export function createExternalImport(
  formData: FormData,
  signal?: AbortSignal,
): Promise<ImportJob> {
  return apiRequest<ImportJob>(
    '/imports/external',
    { method: 'POST', body: formData, signal },
    120_000,
  )
}

export function getExternalTemplate(
  signal?: AbortSignal,
): Promise<ExternalTemplate> {
  return apiRequest<ExternalTemplate>('/imports/external/template', { signal })
}

export function confirmImport(
  importId: string,
  input: ImportConfirmInput,
): Promise<ImportJob> {
  return apiRequest<ImportJob>(`/imports/${importId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function retryImport(importId: string): Promise<ImportJob> {
  return apiRequest<ImportJob>(`/imports/${importId}/retry`, {
    method: 'POST',
  })
}
