import { apiRequest } from './client'

export type KnowledgePointType =
  | 'basic_concept'
  | 'structure'
  | 'classification'
  | 'mechanism'
  | 'process'
  | 'causality'
  | 'formula'
  | 'experiment'
  | 'application'
  | 'comparison'

export type ReviewStatus =
  | 'pending'
  | 'approved'
  | 'needs_revision'
  | 'ignored'

export type JobStatus =
  | 'queued'
  | 'analyzing'
  | 'extracting'
  | 'merging'
  | 'cancelling'
  | 'cancelled'
  | 'completed'
  | 'failed'

export interface KnowledgeJob {
  id: string
  document_id: string
  status: JobStatus
  stage: string
  progress: number
  error: string | null
  cancel_requested: boolean
  attempts: number
  provider: string
  model: string
  total_chunks: number
  processed_chunks: number
  extracted_count: number
  merged_count: number
  duplicate_count: number
  timings: Record<string, unknown> | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  updated_at: string
}

export interface KnowledgePoint {
  id: string
  subject_id: string
  chapter_id: string | null
  document_id: string
  parent_id: string | null
  name: string
  type: KnowledgePointType
  explanation: string
  core_points: string[]
  conditions: string | null
  source_quote: string | null
  source_quote_verified: boolean
  source_page: number | null
  source_page_end: number | null
  source_slide: number | null
  source_locator: string | null
  source_chunk_id: string | null
  importance: string | null
  prerequisites: string[]
  external_id: string | null
  confidence: number | null
  review_note: string | null
  needs_review: boolean
  origin: 'ai' | 'manual'
  review_status: ReviewStatus
  duplicate_of_id: string | null
  reviewed_at: string | null
  published_at: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgePointNode extends KnowledgePoint {
  children: KnowledgePointNode[]
}

export interface KnowledgePointDetail extends KnowledgePoint {
  document_name: string
  subject_name: string
  chapter_name: string | null
  source_chunk_content: string | null
  source_chunk_heading: string | null
}

export interface KnowledgeStats {
  total: number
  pending: number
  approved: number
  needs_revision: number
  ignored: number
  needs_review: number
  duplicates: number
  failed_jobs: number
}

export interface DocumentKnowledge {
  document: {
    id: string
    name: string
    status: string
    chunk_count: number
  }
  stats: KnowledgeStats
  points: KnowledgePointNode[]
  latest_job: KnowledgeJob | null
}

export interface KnowledgePointInput {
  document_id: string
  parent_id?: string | null
  name: string
  type?: KnowledgePointType
  explanation: string
  core_points?: string[]
  conditions?: string | null
}

export interface KnowledgePointUpdateInput {
  name?: string
  type?: KnowledgePointType
  explanation?: string
  core_points?: string[]
  conditions?: string | null
  parent_id?: string | null
}

export function getDocumentKnowledge(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentKnowledge> {
  return apiRequest<DocumentKnowledge>(
    `/documents/${documentId}/knowledge-points`,
    { signal },
  )
}

export function getKnowledgePoint(
  pointId: string,
  signal?: AbortSignal,
): Promise<KnowledgePointDetail> {
  return apiRequest<KnowledgePointDetail>(`/knowledge-points/${pointId}`, {
    signal,
  })
}

export function createKnowledgePoint(
  input: KnowledgePointInput,
): Promise<KnowledgePointDetail> {
  return apiRequest<KnowledgePointDetail>('/knowledge-points', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateKnowledgePoint(
  pointId: string,
  input: KnowledgePointUpdateInput,
): Promise<KnowledgePointDetail> {
  return apiRequest<KnowledgePointDetail>(`/knowledge-points/${pointId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function reviewKnowledgePoint(
  pointId: string,
  status: ReviewStatus,
): Promise<KnowledgePointDetail> {
  return apiRequest<KnowledgePointDetail>(
    `/knowledge-points/${pointId}/review`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    },
  )
}

export function bulkReviewKnowledge(
  ids: string[],
  status: ReviewStatus,
): Promise<{ updated: number }> {
  return apiRequest<{ updated: number }>('/knowledge-points/bulk-review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, status }),
  })
}

export function mergeKnowledgePoints(
  sourceIds: string[],
  name?: string,
  explanation?: string,
): Promise<KnowledgePointDetail> {
  return apiRequest<KnowledgePointDetail>('/knowledge-points/merge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_ids: sourceIds,
      ...(name ? { name } : {}),
      ...(explanation ? { explanation } : {}),
    }),
  })
}

export function deleteKnowledgePoint(
  pointId: string,
  cascade: boolean,
): Promise<void> {
  return apiRequest<void>(
    `/knowledge-points/${pointId}?cascade=${cascade ? 'true' : 'false'}`,
    { method: 'DELETE' },
  )
}

export interface KnowledgeListResponse {
  points: KnowledgePoint[]
  stats: KnowledgeStats
  total: number
}

export function listKnowledgePoints(params: {
  document_id?: string
  subject_id?: string
  chapter_id?: string
  review_status?: ReviewStatus
  point_type?: KnowledgePointType
  origin?: 'ai' | 'manual'
  q?: string
  needs_review?: boolean
  limit?: number
  offset?: number
}): Promise<KnowledgeListResponse> {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      query.set(key, String(value))
    }
  })
  return apiRequest<KnowledgeListResponse>(
    `/knowledge-points?${query.toString()}`,
  )
}

export function getJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<KnowledgeJob> {
  return apiRequest<KnowledgeJob>(`/knowledge-jobs/${jobId}`, { signal })
}

export function retryJob(jobId: string): Promise<KnowledgeJob> {
  return apiRequest<KnowledgeJob>(`/knowledge-jobs/${jobId}/retry`, {
    method: 'POST',
  })
}

export function cancelJob(jobId: string): Promise<KnowledgeJob> {
  return apiRequest<KnowledgeJob>(`/knowledge-jobs/${jobId}/cancel`, {
    method: 'POST',
  })
}
