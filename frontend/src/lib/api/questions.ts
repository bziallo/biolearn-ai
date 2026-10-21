import { apiRequest } from './client'

export type QuestionType =
  | 'single_choice'
  | 'multiple_choice'
  | 'true_false'
  | 'short_answer'

export type QuestionDifficulty = 'easy' | 'medium' | 'hard'
export type QuestionStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'needs_revision'
export type QuestionOrigin = 'ai' | 'manual'
export type QuestionJobStatus =
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'cancelled'
  | 'completed'
  | 'failed'

export interface QuestionOption {
  key: string
  text: string
}

export interface QuestionKnowledgePoint {
  id: string
  name: string
  chapter_id: string | null
  document_id: string
  source_page: number | null
  source_slide: number | null
  source_locator: string | null
  review_status: string
}

export interface Question {
  id: string
  subject_id: string
  subject_name: string
  chapter_id: string | null
  chapter_name: string | null
  source_document_id: string | null
  source_document_name: string | null
  generation_job_id: string | null
  duplicate_of_id: string | null
  duplicate_reason: string | null
  type: QuestionType
  stem: string
  options: QuestionOption[]
  answer: Record<string, unknown>
  grading_rule: Record<string, unknown>
  explanation: string
  difficulty: QuestionDifficulty
  status: QuestionStatus
  origin: QuestionOrigin
  source_locator: string | null
  ai_provider: string
  ai_model: string
  confidence: number | null
  review_note: string | null
  score: number
  knowledge_points: QuestionKnowledgePoint[]
  reviewed_at: string | null
  published_at: string | null
  created_at: string
  updated_at: string
}

export interface QuestionStats {
  total: number
  pending: number
  approved: number
  rejected: number
  needs_revision: number
}

export interface QuestionListResponse {
  questions: Question[]
  total: number
  stats: QuestionStats
}

export interface QuestionInput {
  subject_id: string
  chapter_id?: string | null
  knowledge_point_ids: string[]
  type: QuestionType
  stem: string
  options: QuestionOption[]
  answer: Record<string, unknown>
  explanation: string
  difficulty: QuestionDifficulty
  source_locator?: string | null
  review_note?: string | null
}

export interface QuestionUpdateInput {
  chapter_id?: string | null
  knowledge_point_ids?: string[]
  type?: QuestionType
  stem?: string
  options?: QuestionOption[]
  answer?: Record<string, unknown>
  explanation?: string
  difficulty?: QuestionDifficulty
  source_locator?: string | null
  review_note?: string | null
}

export interface QuestionGenerateInput {
  subject_id: string
  chapter_id?: string | null
  knowledge_point_ids?: string[]
  types: QuestionType[]
  count: number
  difficulty?: QuestionDifficulty | null
}

export interface QuestionGenerationJob {
  id: string
  subject_id: string
  chapter_id: string | null
  status: QuestionJobStatus
  stage: string
  progress: number
  error: string | null
  cancel_requested: boolean
  attempts: number
  provider: string
  model: string
  request: Record<string, unknown>
  generated_count: number
  skipped_count: number
  timings: Record<string, unknown> | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  updated_at: string
}

export function listQuestions(params: {
  subject_id?: string
  chapter_id?: string
  knowledge_point_id?: string
  type?: QuestionType
  difficulty?: QuestionDifficulty
  status?: QuestionStatus
  origin?: QuestionOrigin
  q?: string
  limit?: number
  offset?: number
}): Promise<QuestionListResponse> {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      query.set(key, String(value))
    }
  })
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiRequest<QuestionListResponse>(`/questions${suffix}`)
}

export function getQuestion(id: string): Promise<Question> {
  return apiRequest<Question>(`/questions/${id}`)
}

export function createQuestion(input: QuestionInput): Promise<Question> {
  return apiRequest<Question>('/questions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function updateQuestion(
  id: string,
  input: QuestionUpdateInput,
): Promise<Question> {
  return apiRequest<Question>(`/questions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function reviewQuestion(
  id: string,
  status: QuestionStatus,
  note?: string,
): Promise<Question> {
  return apiRequest<Question>(`/questions/${id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, note }),
  })
}

export function bulkReviewQuestions(
  ids: string[],
  status: QuestionStatus,
  note?: string,
): Promise<{ updated: number }> {
  return apiRequest<{ updated: number }>('/questions/bulk-review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, status, note }),
  })
}

export function generateQuestions(
  input: QuestionGenerateInput,
): Promise<QuestionGenerationJob> {
  return apiRequest<QuestionGenerationJob>(
    '/questions/generate',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    },
    30_000,
  )
}

export function getQuestionGenerationJob(
  id: string,
): Promise<QuestionGenerationJob> {
  return apiRequest<QuestionGenerationJob>(`/questions/generation-jobs/${id}`)
}

export function retryQuestionGeneration(
  id: string,
): Promise<QuestionGenerationJob> {
  return apiRequest<QuestionGenerationJob>(
    `/questions/generation-jobs/${id}/retry`,
    { method: 'POST' },
  )
}

export function cancelQuestionGeneration(
  id: string,
): Promise<QuestionGenerationJob> {
  return apiRequest<QuestionGenerationJob>(
    `/questions/generation-jobs/${id}/cancel`,
    { method: 'POST' },
  )
}

export function regenerateQuestion(
  id: string,
  count = 1,
  difficulty?: QuestionDifficulty,
): Promise<QuestionGenerationJob> {
  return apiRequest<QuestionGenerationJob>(`/questions/${id}/regenerate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ count, difficulty }),
  })
}
