export type LocalSyncState =
  | 'local_only'
  | 'synced'
  | 'pending_create'
  | 'pending_update'
  | 'pending_delete'
  | 'conflict'

export interface LocalCourse {
  id: string
  serverId: string | null
  name: string
  description: string
  color: string | null
  icon: string | null
  sortOrder: number
  createdAt: string
  updatedAt: string
  syncState: LocalSyncState
  version: number
}

export interface LocalChapter {
  id: string
  serverId: string | null
  courseId: string
  parentId: string | null
  name: string
  description: string
  sortOrder: number
  createdAt: string
  updatedAt: string
  syncState: LocalSyncState
  version: number
}

export interface LocalDocument {
  id: string
  serverId: string | null
  courseId: string
  chapterId: string | null
  name: string
  originalFilename: string
  mimeType: string
  extension: string
  sizeBytes: number
  sha256: string
  status: string
  parseError: string | null
  chunkCount: number
  knowledgePointCount: number
  localPath: string | null
  createdAt: string
  updatedAt: string
  syncState: LocalSyncState
  version: number
}

export interface LocalKnowledgePoint {
  id: string
  serverId: string | null
  courseId: string
  chapterId: string | null
  documentId: string | null
  name: string
  pointType: string
  explanation: string
  corePoints: string[]
  sourcePage: number | null
  reviewStatus: string
  origin: string
  confidence: number | null
  createdAt: string
  updatedAt: string
  syncState: LocalSyncState
  version: number
}

export interface LocalQuestion {
  id: string
  serverId: string | null
  courseId: string
  chapterId: string | null
  stem: string
  questionType: string
  options: unknown[]
  answer: Record<string, unknown>
  explanation: string
  difficulty: string
  status: string
  origin: string
  createdAt: string
  updatedAt: string
  syncState: LocalSyncState
  version: number
}

export interface LocalPracticeSession {
  id: string
  serverId: string | null
  userId: string | null
  courseId: string
  chapterId: string | null
  status: string
  questionIds: string[]
  totalQuestions: number
  correctCount: number
  score: number | null
  startedAt: string
  finishedAt: string | null
  updatedAt: string
  syncState: LocalSyncState
  version: number
}

export interface LocalPracticeAnswer {
  id: string
  serverId: string | null
  sessionId: string
  questionId: string | null
  questionSnapshot: Record<string, unknown>
  userAnswer: Record<string, unknown>
  isCorrect: boolean | null
  score: number | null
  maxScore: number
  feedback: string | null
  gradedBy: string
  answeredAt: string
  syncState: LocalSyncState
}

export type LocalFileStatus =
  | 'selected'
  | 'copying'
  | 'stored'
  | 'failed'
  | 'deleted'

export type LocalParseStatus =
  | 'queued'
  | 'parsing'
  | 'parsed'
  | 'failed'

export type LocalUploadStatus =
  | 'queued'
  | 'uploading'
  | 'uploaded'
  | 'failed'
  | 'needs_verification'

export interface LocalFileRecord {
  id: string
  documentId: string
  relativePath: string
  originalFilename: string
  mimeType: string
  sizeBytes: number
  sha256: string
  status: LocalFileStatus
  error: string | null
  createdAt: string
}

export interface LocalParseJob {
  id: string
  documentId: string
  status: LocalParseStatus
  error: string | null
  createdAt: string
  updatedAt: string
  finishedAt: string | null
}

export interface LocalUploadJob {
  id: string
  documentId: string
  fileId: string
  status: LocalUploadStatus
  attempts: number
  lastError: string | null
  createdAt: string
  updatedAt: string
  nextRetryAt: string | null
  remoteDocumentId: string | null
}

export interface LocalDatabaseStatus {
  databaseName: string
  schemaVersion: number
  foreignKeys: boolean
  open: boolean
  syntheticOnly: boolean
  counts: Record<string, number>
}

export interface LocalExportData {
  courses: LocalCourse[]
  chapters: LocalChapter[]
  documents: LocalDocument[]
  knowledgePoints: LocalKnowledgePoint[]
  questions: LocalQuestion[]
  practiceSessions: LocalPracticeSession[]
  practiceAnswers: LocalPracticeAnswer[]
}

export interface LocalExportPayload {
  format: 'biolearn.localdb.export'
  schemaVersion: number
  exportedAt: string
  syntheticOnly: boolean
  checksumAlgorithm: 'SHA-256'
  checksum: string
  data: LocalExportData
}

export interface LocalRepositoryBundle {
  mode: 'local' | 'remote'
  courses: {
    list(): Promise<LocalCourse[]>
    get(id: string): Promise<LocalCourse | null>
    chapters(courseId: string): Promise<LocalChapter[]>
  }
  documents: {
    listByCourse(courseId: string): Promise<LocalDocument[]>
  }
  knowledgePoints: {
    listByCourse(courseId: string): Promise<LocalKnowledgePoint[]>
    listByDocument(documentId: string): Promise<LocalKnowledgePoint[]>
  }
  questions: {
    listByCourse(courseId: string): Promise<LocalQuestion[]>
  }
  practice: {
    sessionsByCourse(courseId: string): Promise<LocalPracticeSession[]>
    answers(sessionId: string): Promise<LocalPracticeAnswer[]>
  }
}
