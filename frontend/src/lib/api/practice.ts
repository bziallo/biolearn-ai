import { apiRequest } from './client'
import type {
  Question,
  QuestionDifficulty,
  QuestionKnowledgePoint,
  QuestionOption,
  QuestionType,
} from './questions'

export interface PracticeQuestion {
  id: string
  type: QuestionType
  stem: string
  options: QuestionOption[]
  difficulty: QuestionDifficulty
  chapter_id: string | null
  knowledge_points: QuestionKnowledgePoint[]
}

export interface PracticeSession {
  id: string
  subject_id: string
  subject_name: string
  chapter_id: string | null
  chapter_name: string | null
  status: 'in_progress' | 'completed'
  total_questions: number
  answered_count: number
  correct_count: number
  pending_manual_count: number
  score: number | null
  started_at: string
  finished_at: string | null
  questions: PracticeQuestion[]
}

export interface PracticeAnswerResult {
  id: string
  question: Question
  user_answer: Record<string, unknown>
  is_correct: boolean | null
  score: number | null
  max_score: number
  feedback: string | null
  graded_by: string
  answered_at: string
}

export interface PracticeResult {
  session: PracticeSession
  answers: PracticeAnswerResult[]
}

export interface PracticeStartInput {
  subject_id: string
  chapter_id?: string | null
  knowledge_point_ids?: string[]
  types?: QuestionType[]
  difficulty?: QuestionDifficulty | null
  count: number
  wrong_only?: boolean
}

export interface PracticeSubmitInput {
  answers: Array<{ question_id: string; user_answer: Record<string, unknown> }>
}

export interface WrongQuestion {
  question: Question
  wrong_count: number
  last_answer: Record<string, unknown>
  last_answered_at: string
}

export function startPractice(
  input: PracticeStartInput,
): Promise<PracticeSession> {
  return apiRequest<PracticeSession>('/practice/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function getPracticeSession(id: string): Promise<PracticeSession> {
  return apiRequest<PracticeSession>(`/practice/sessions/${id}`)
}

export function listPracticeSessions(
  subjectId?: string,
  limit = 20,
): Promise<PracticeSession[]> {
  const query = new URLSearchParams()
  if (subjectId) {
    query.set('subject_id', subjectId)
  }
  query.set('limit', String(limit))
  return apiRequest<PracticeSession[]>(`/practice/sessions?${query.toString()}`)
}

export function submitPractice(
  sessionId: string,
  input: PracticeSubmitInput,
): Promise<PracticeResult> {
  return apiRequest<PracticeResult>(`/practice/sessions/${sessionId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function getPracticeResult(sessionId: string): Promise<PracticeResult> {
  return apiRequest<PracticeResult>(
    `/practice/sessions/${sessionId}/result`,
  )
}

export function getWrongQuestions(
  subjectId: string,
  chapterId?: string,
): Promise<WrongQuestion[]> {
  const query = new URLSearchParams({ subject_id: subjectId })
  if (chapterId) {
    query.set('chapter_id', chapterId)
  }
  return apiRequest<WrongQuestion[]>(
    `/practice/wrong-questions?${query.toString()}`,
  )
}

export function gradePracticeAnswer(
  answerId: string,
  score: number,
  feedback?: string,
): Promise<PracticeResult> {
  return apiRequest<PracticeResult>(`/practice/answers/${answerId}/grade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ score, feedback }),
  })
}
