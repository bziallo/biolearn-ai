import {
  getPracticeResult,
  listDocuments,
  listKnowledgePoints,
  listPracticeSessions,
  listQuestions,
  listSubjectChapters,
  listSubjects,
  getSubject,
} from '../api'
import { flattenTree } from '../chapterTree'
import { isLocalDbEnabled } from './featureFlag'
import { LocalDatabase, LocalDatabaseError } from './localDatabase'
import { createNativeSqliteDriver } from './sqliteDriver'
import type {
  LocalChapter,
  LocalCourse,
  LocalDocument,
  LocalKnowledgePoint,
  LocalPracticeAnswer,
  LocalPracticeSession,
  LocalQuestion,
  LocalRepositoryBundle,
} from './types'

let localDatabase: LocalDatabase | null = null

export async function getLocalDatabase(): Promise<LocalDatabase> {
  if (!localDatabase) {
    const database = new LocalDatabase(createNativeSqliteDriver())
    try {
      await database.open()
      localDatabase = database
    } catch (error) {
      await database.close().catch(() => undefined)
      throw error instanceof Error
        ? error
        : new LocalDatabaseError('本地数据库打开失败')
    }
  }
  return localDatabase
}

export async function closeLocalDatabase(): Promise<void> {
  if (localDatabase) {
    await localDatabase.close()
    localDatabase = null
  }
}

function courseFromApi(item: {
  id: string
  name: string
  description: string
  color: string | null
  icon: string | null
  sort_order: number
  created_at: string
  updated_at: string
}): LocalCourse {
  return {
    id: item.id,
    serverId: item.id,
    name: item.name,
    description: item.description,
    color: item.color,
    icon: item.icon,
    sortOrder: item.sort_order,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    syncState: 'synced',
    version: 0,
  }
}

function chapterFromApi(item: {
  id: string
  subject_id: string
  parent_id: string | null
  name: string
  description: string
  sort_order: number
  created_at: string
  updated_at: string
}): LocalChapter {
  return {
    id: item.id,
    serverId: item.id,
    courseId: item.subject_id,
    parentId: item.parent_id,
    name: item.name,
    description: item.description,
    sortOrder: item.sort_order,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    syncState: 'synced',
    version: 0,
  }
}

function documentFromApi(item: Awaited<ReturnType<typeof listDocuments>>[number]): LocalDocument {
  return {
    id: item.id,
    serverId: item.id,
    courseId: item.subject_id,
    chapterId: item.chapter_id,
    name: item.name,
    originalFilename: item.original_filename,
    mimeType: item.mime_type,
    extension: item.extension,
    sizeBytes: item.size_bytes,
    sha256: item.sha256,
    status: item.status,
    parseError: item.parse_error,
    chunkCount: item.chunk_count,
    knowledgePointCount: item.knowledge_point_count,
    localPath: null,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    syncState: 'synced',
    version: 0,
  }
}

function pointFromApi(item: Awaited<ReturnType<typeof listKnowledgePoints>>['points'][number]): LocalKnowledgePoint {
  return {
    id: item.id,
    serverId: item.id,
    courseId: item.subject_id,
    chapterId: item.chapter_id,
    documentId: item.document_id,
    name: item.name,
    pointType: item.type,
    explanation: item.explanation,
    corePoints: item.core_points,
    sourcePage: item.source_page,
    reviewStatus: item.review_status,
    origin: item.origin,
    confidence: item.confidence,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    syncState: 'synced',
    version: 0,
  }
}

function questionFromApi(item: Awaited<ReturnType<typeof listQuestions>>['questions'][number]): LocalQuestion {
  return {
    id: item.id,
    serverId: item.id,
    courseId: item.subject_id,
    chapterId: item.chapter_id,
    stem: item.stem,
    questionType: item.type,
    options: item.options,
    answer: item.answer,
    explanation: item.explanation,
    difficulty: item.difficulty,
    status: item.status,
    origin: item.origin,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    syncState: 'synced',
    version: 0,
  }
}

function sessionFromApi(item: Awaited<ReturnType<typeof listPracticeSessions>>[number]): LocalPracticeSession {
  return {
    id: item.id,
    serverId: item.id,
    userId: null,
    courseId: item.subject_id,
    chapterId: item.chapter_id,
    status: item.status,
    questionIds: item.questions.map((question) => question.id),
    totalQuestions: item.total_questions,
    correctCount: item.correct_count,
    score: item.score,
    startedAt: item.started_at,
    finishedAt: item.finished_at,
    updatedAt: item.started_at,
    syncState: 'synced',
    version: 0,
  }
}

function answerFromApi(item: Awaited<ReturnType<typeof getPracticeResult>>['answers'][number]): LocalPracticeAnswer {
  return {
    id: item.id,
    serverId: item.id,
    sessionId: '',
    questionId: item.question.id,
    questionSnapshot: { id: item.question.id, stem: item.question.stem },
    userAnswer: item.user_answer,
    isCorrect: item.is_correct,
    score: item.score,
    maxScore: item.max_score,
    feedback: item.feedback,
    gradedBy: item.graded_by,
    answeredAt: item.answered_at,
    syncState: 'synced',
  }
}

function remoteBundle(): LocalRepositoryBundle {
  return {
    mode: 'remote',
    courses: {
      list: async () => (await listSubjects()).map(courseFromApi),
      get: async (id) => courseFromApi(await getSubject(id)),
      chapters: async (courseId) => {
        const tree = await listSubjectChapters(courseId)
        return flattenTree(tree).map(({ node }) => chapterFromApi(node))
      },
    },
    documents: {
      listByCourse: async (courseId) =>
        (await listDocuments({ subject_id: courseId })).map(documentFromApi),
    },
    knowledgePoints: {
      listByCourse: async (courseId) =>
        (await listKnowledgePoints({ subject_id: courseId, limit: 2000 })).points.map(
          pointFromApi,
        ),
      listByDocument: async (documentId) =>
        (
          await listKnowledgePoints({ document_id: documentId, limit: 2000 })
        ).points.map(pointFromApi),
    },
    questions: {
      listByCourse: async (courseId) =>
        (
          await listQuestions({ subject_id: courseId, limit: 200 })
        ).questions.map(questionFromApi),
    },
    practice: {
      sessionsByCourse: async (courseId) =>
        (await listPracticeSessions(courseId, 100)).map(sessionFromApi),
      answers: async (sessionId) => {
        const result = await getPracticeResult(sessionId)
        return result.answers.map((item) => ({
          ...answerFromApi(item),
          sessionId,
        }))
      },
    },
  }
}

export function localBundle(database: LocalDatabase): LocalRepositoryBundle {
  return {
    mode: 'local',
    courses: {
      list: async () => (await database.readAll()).courses,
      get: async (id) =>
        (await database.readAll()).courses.find((course) => course.id === id) ?? null,
      chapters: async (courseId) =>
        (await database.readAll()).chapters.filter(
          (chapter) => chapter.courseId === courseId,
        ),
    },
    documents: {
      listByCourse: async (courseId) =>
        (await database.readAll()).documents.filter(
          (document) => document.courseId === courseId,
        ),
    },
    knowledgePoints: {
      listByCourse: async (courseId) =>
        (await database.readAll()).knowledgePoints.filter(
          (point) => point.courseId === courseId,
        ),
      listByDocument: async (documentId) =>
        (await database.readAll()).knowledgePoints.filter(
          (point) => point.documentId === documentId,
        ),
    },
    questions: {
      listByCourse: async (courseId) =>
        (await database.readAll()).questions.filter(
          (question) => question.courseId === courseId,
        ),
    },
    practice: {
      sessionsByCourse: async (courseId) =>
        (await database.readAll()).practiceSessions.filter(
          (session) => session.courseId === courseId,
        ),
      answers: async (sessionId) =>
        (await database.readAll()).practiceAnswers.filter(
          (answer) => answer.sessionId === sessionId,
        ),
    },
  }
}

/**
 * The only place that chooses local vs remote. Default is always remote; 7B
 * does not wire this into existing pages, so production behavior is unchanged.
 */
export async function createRepositoryBundle(): Promise<LocalRepositoryBundle> {
  if (!isLocalDbEnabled()) {
    return remoteBundle()
  }
  return localBundle(await getLocalDatabase())
}
