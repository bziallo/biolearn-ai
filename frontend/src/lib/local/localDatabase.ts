import {
  LOCAL_DB_NAME,
  LOCAL_DB_SCHEMA_VERSION,
  LOCAL_MIGRATIONS,
} from './schema'
import {
  createExportPayload,
  verifyExportPayload,
} from './exportFormat'
import type { LocalSqliteDriver, SqlRow } from './sqliteDriver'
import {
  SYNTHETIC_ANSWERS,
  SYNTHETIC_CHAPTERS,
  SYNTHETIC_CHUNKS,
  SYNTHETIC_COURSE,
  SYNTHETIC_DOCUMENT,
  SYNTHETIC_KNOWLEDGE_POINTS,
  SYNTHETIC_QUESTIONS,
  SYNTHETIC_SESSION,
} from './syntheticSeed'
import type {
  LocalChapter,
  LocalCourse,
  LocalDatabaseStatus,
  LocalDocument,
  LocalExportData,
  LocalExportPayload,
  LocalKnowledgePoint,
  LocalPracticeAnswer,
  LocalPracticeSession,
  LocalQuestion,
} from './types'

export class LocalDatabaseError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message)
    this.name = 'LocalDatabaseError'
  }
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function nullableText(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null
}

function numberValue(value: unknown): number {
  return typeof value === 'number' ? value : Number(value ?? 0)
}

function nullableNumber(value: unknown): number | null {
  return value === null || value === undefined ? null : Number(value)
}

function parseJson<T>(value: unknown, fallback: T): T {
  if (typeof value !== 'string' || !value) {
    return fallback
  }
  try {
    return JSON.parse(value) as T
  } catch {
    return fallback
  }
}

function rowsToData(rows: {
  courses: SqlRow[]
  chapters: SqlRow[]
  documents: SqlRow[]
  knowledgePoints: SqlRow[]
  questions: SqlRow[]
  sessions: SqlRow[]
  answers: SqlRow[]
}): LocalExportData {
  return {
    courses: rows.courses.map(
      (row): LocalCourse => ({
        id: text(row.id),
        serverId: nullableText(row.server_id),
        name: text(row.name),
        description: text(row.description),
        color: nullableText(row.color),
        icon: nullableText(row.icon),
        sortOrder: numberValue(row.sort_order),
        createdAt: text(row.created_at),
        updatedAt: text(row.updated_at),
        syncState: (text(row.sync_state) || 'local_only') as LocalCourse['syncState'],
        version: numberValue(row.version),
      }),
    ),
    chapters: rows.chapters.map(
      (row): LocalChapter => ({
        id: text(row.id),
        serverId: nullableText(row.server_id),
        courseId: text(row.course_id),
        parentId: nullableText(row.parent_id),
        name: text(row.name),
        description: text(row.description),
        sortOrder: numberValue(row.sort_order),
        createdAt: text(row.created_at),
        updatedAt: text(row.updated_at),
        syncState: (text(row.sync_state) || 'local_only') as LocalChapter['syncState'],
        version: numberValue(row.version),
      }),
    ),
    documents: rows.documents.map(
      (row): LocalDocument => ({
        id: text(row.id),
        serverId: nullableText(row.server_id),
        courseId: text(row.course_id),
        chapterId: nullableText(row.chapter_id),
        name: text(row.name),
        originalFilename: text(row.original_filename),
        mimeType: text(row.mime_type),
        extension: text(row.extension),
        sizeBytes: numberValue(row.size_bytes),
        sha256: text(row.sha256),
        status: text(row.status),
        parseError: nullableText(row.parse_error),
        chunkCount: numberValue(row.chunk_count),
        knowledgePointCount: numberValue(row.knowledge_point_count),
        localPath: nullableText(row.local_path),
        createdAt: text(row.created_at),
        updatedAt: text(row.updated_at),
        syncState: (text(row.sync_state) || 'local_only') as LocalDocument['syncState'],
        version: numberValue(row.version),
      }),
    ),
    knowledgePoints: rows.knowledgePoints.map(
      (row): LocalKnowledgePoint => ({
        id: text(row.id),
        serverId: nullableText(row.server_id),
        courseId: text(row.course_id),
        chapterId: nullableText(row.chapter_id),
        documentId: nullableText(row.document_id),
        name: text(row.name),
        pointType: text(row.point_type),
        explanation: text(row.explanation),
        corePoints: parseJson<string[]>(row.core_points, []),
        sourcePage: nullableNumber(row.source_page),
        reviewStatus: text(row.review_status),
        origin: text(row.origin),
        confidence: nullableNumber(row.confidence),
        createdAt: text(row.created_at),
        updatedAt: text(row.updated_at),
        syncState: (text(row.sync_state) || 'local_only') as LocalKnowledgePoint['syncState'],
        version: numberValue(row.version),
      }),
    ),
    questions: rows.questions.map(
      (row): LocalQuestion => ({
        id: text(row.id),
        serverId: nullableText(row.server_id),
        courseId: text(row.course_id),
        chapterId: nullableText(row.chapter_id),
        stem: text(row.stem),
        questionType: text(row.question_type),
        options: parseJson<unknown[]>(row.options, []),
        answer: parseJson<Record<string, unknown>>(row.answer, {}),
        explanation: text(row.explanation),
        difficulty: text(row.difficulty),
        status: text(row.status),
        origin: text(row.origin),
        createdAt: text(row.created_at),
        updatedAt: text(row.updated_at),
        syncState: (text(row.sync_state) || 'local_only') as LocalQuestion['syncState'],
        version: numberValue(row.version),
      }),
    ),
    practiceSessions: rows.sessions.map(
      (row): LocalPracticeSession => ({
        id: text(row.id),
        serverId: nullableText(row.server_id),
        userId: nullableText(row.user_id),
        courseId: text(row.course_id),
        chapterId: nullableText(row.chapter_id),
        status: text(row.status),
        questionIds: parseJson<string[]>(row.question_ids, []),
        totalQuestions: numberValue(row.total_questions),
        correctCount: numberValue(row.correct_count),
        score: nullableNumber(row.score),
        startedAt: text(row.started_at),
        finishedAt: nullableText(row.finished_at),
        updatedAt: text(row.updated_at),
        syncState: (text(row.sync_state) || 'local_only') as LocalPracticeSession['syncState'],
        version: numberValue(row.version),
      }),
    ),
    practiceAnswers: rows.answers.map(
      (row): LocalPracticeAnswer => ({
        id: text(row.id),
        serverId: nullableText(row.server_id),
        sessionId: text(row.session_id),
        questionId: nullableText(row.question_id),
        questionSnapshot: parseJson<Record<string, unknown>>(row.question_snapshot, {}),
        userAnswer: parseJson<Record<string, unknown>>(row.user_answer, {}),
        isCorrect:
          row.is_correct === null || row.is_correct === undefined
            ? null
            : Number(row.is_correct) === 1,
        score: nullableNumber(row.score),
        maxScore: numberValue(row.max_score),
        feedback: nullableText(row.feedback),
        gradedBy: text(row.graded_by),
        answeredAt: text(row.answered_at),
        syncState: (text(row.sync_state) || 'local_only') as LocalPracticeAnswer['syncState'],
      }),
    ),
  }
}

export class LocalDatabase {
  private opened = false

  constructor(
    private readonly driver: LocalSqliteDriver,
    private readonly databaseName = LOCAL_DB_NAME,
  ) {}

  async open(): Promise<void> {
    if (this.opened) {
      return
    }
    try {
      await this.driver.open?.()
      await this.driver.execute('PRAGMA foreign_keys = ON')
      const fk = await this.driver.query<{ foreign_keys: number }>('PRAGMA foreign_keys')
      if (Number(fk[0]?.foreign_keys) !== 1) {
        throw new LocalDatabaseError('SQLite 外键约束未能开启')
      }
      await this.driver.execute(
        `CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        )`,
      )
      await this.applyMigrations()
      this.opened = true
    } catch (error) {
      if (error instanceof LocalDatabaseError) {
        throw error
      }
      throw new LocalDatabaseError(
        `本地数据库初始化失败：${error instanceof Error ? error.message : String(error)}`,
        error,
      )
    }
  }

  private async applyMigrations(): Promise<void> {
    const versionRows = await this.driver.query<{ user_version: number }>(
      'PRAGMA user_version',
    )
    const userVersion = Number(versionRows[0]?.user_version ?? 0)
    const applied = await this.driver.query<{ version: number }>(
      'SELECT version FROM schema_migrations ORDER BY version',
    )
    const appliedVersions = new Set(applied.map((row) => Number(row.version)))
    const hasAnySchema = await this.driver.query<{ name: string }>(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='local_courses'",
    )
    if (!hasAnySchema.length && userVersion > 0) {
      // A native connection can create a DB header before our tables exist.
      await this.driver.execute('PRAGMA user_version = 0')
    }

    for (const migration of LOCAL_MIGRATIONS) {
      if (appliedVersions.has(migration.version)) {
        continue
      }
      if (
        migration.version === 2 &&
        (await this.columnExists('local_documents', 'local_path'))
      ) {
        // Idempotent only for a partially applied local schema.
        await this.recordMigration(migration.version)
        continue
      }
      try {
        await this.driver.execute(migration.statements.join(';\n'), true)
        await this.recordMigration(migration.version)
        await this.driver.execute(`PRAGMA user_version = ${migration.version}`)
      } catch (error) {
        throw new LocalDatabaseError(
          `本地数据库迁移 v${migration.version} 失败：${
            error instanceof Error ? error.message : String(error)
          }`,
          error,
        )
      }
    }
    await this.driver.execute(`PRAGMA user_version = ${LOCAL_DB_SCHEMA_VERSION}`)
  }

  private async clearActiveTransaction(): Promise<void> {
    // Some native bridge versions report isTransactionActive=false while the
    // underlying SQLiteDatabase still has an open transaction after a failed
    // migration. An unconditional rollback is harmless when no transaction is
    // active (the plugin rejects it), so always attempt it before BEGIN.
    await this.driver.rollbackTransaction().catch(() => undefined)
  }

  private async recordMigration(version: number): Promise<void> {
    await this.driver.run(
      'INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES (?, ?)',
      [version, new Date().toISOString()],
    )
  }

  private async columnExists(table: string, column: string): Promise<boolean> {
    const rows = await this.driver.query<{ name: string }>(`PRAGMA table_info(${table})`)
    return rows.some((row) => row.name === column)
  }

  async close(): Promise<void> {
    await this.driver.close()
    this.opened = false
  }

  async status(): Promise<LocalDatabaseStatus> {
    const counts: Record<string, number> = {}
    for (const table of [
      'local_courses',
      'local_chapters',
      'local_documents',
      'local_knowledge_points',
      'local_questions',
      'local_practice_sessions',
      'local_practice_answers',
    ]) {
      const rows = await this.driver.query<{ count: number }>(
        `SELECT COUNT(*) AS count FROM ${table}`,
      )
      counts[table] = numberValue(rows[0]?.count)
    }
    const versionRows = await this.driver.query<{ user_version: number }>(
      'PRAGMA user_version',
    )
    const syntheticRows = await this.driver.query<{ value: string }>(
      "SELECT value FROM local_meta WHERE key = 'synthetic_only'",
    )
    return {
      databaseName: this.databaseName,
      schemaVersion: numberValue(versionRows[0]?.user_version),
      foreignKeys: true,
      open: this.opened,
      syntheticOnly: syntheticRows[0]?.value === '1',
      counts,
    }
  }

  async seedSynthetic(): Promise<void> {
    const existing = await this.driver.query<{ count: number }>(
      'SELECT COUNT(*) AS count FROM local_courses',
    )
    if (numberValue(existing[0]?.count) > 0) {
      return
    }
    try {
      await this.clearActiveTransaction()
      await this.driver.beginTransaction()
      await this.driver.run(
        `INSERT INTO local_courses
        (id, server_id, name, description, color, icon, sort_order, created_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          SYNTHETIC_COURSE.id,
          SYNTHETIC_COURSE.serverId,
          SYNTHETIC_COURSE.name,
          SYNTHETIC_COURSE.description,
          SYNTHETIC_COURSE.color,
          SYNTHETIC_COURSE.icon,
          SYNTHETIC_COURSE.sortOrder,
          SYNTHETIC_COURSE.createdAt,
          SYNTHETIC_COURSE.updatedAt,
          SYNTHETIC_COURSE.syncState,
          SYNTHETIC_COURSE.version,
        ],
      )
      for (const chapter of SYNTHETIC_CHAPTERS) {
        await this.driver.run(
          `INSERT INTO local_chapters
          (id, server_id, course_id, parent_id, name, description, sort_order, created_at, updated_at, sync_state, version)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          [
            chapter.id,
            chapter.serverId,
            chapter.courseId,
            chapter.parentId,
            chapter.name,
            chapter.description,
            chapter.sortOrder,
            chapter.createdAt,
            chapter.updatedAt,
            chapter.syncState,
            chapter.version,
          ],
        )
      }
      await this.driver.run(
        `INSERT INTO local_documents
        (id, server_id, course_id, chapter_id, name, original_filename, mime_type, extension, size_bytes, sha256, status, parse_error, chunk_count, knowledge_point_count, local_path, created_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          SYNTHETIC_DOCUMENT.id,
          SYNTHETIC_DOCUMENT.serverId,
          SYNTHETIC_DOCUMENT.courseId,
          SYNTHETIC_DOCUMENT.chapterId,
          SYNTHETIC_DOCUMENT.name,
          SYNTHETIC_DOCUMENT.originalFilename,
          SYNTHETIC_DOCUMENT.mimeType,
          SYNTHETIC_DOCUMENT.extension,
          SYNTHETIC_DOCUMENT.sizeBytes,
          SYNTHETIC_DOCUMENT.sha256,
          SYNTHETIC_DOCUMENT.status,
          SYNTHETIC_DOCUMENT.parseError,
          SYNTHETIC_DOCUMENT.chunkCount,
          SYNTHETIC_DOCUMENT.knowledgePointCount,
          SYNTHETIC_DOCUMENT.localPath,
          SYNTHETIC_DOCUMENT.createdAt,
          SYNTHETIC_DOCUMENT.updatedAt,
          SYNTHETIC_DOCUMENT.syncState,
          SYNTHETIC_DOCUMENT.version,
        ],
      )
      for (const chunk of SYNTHETIC_CHUNKS) {
        await this.driver.run(
          `INSERT INTO local_chunks
          (id, document_id, chunk_index, heading_path, heading_level, content, page_start, page_end, slide_number, char_start, char_end, location_label, created_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          [
            chunk.id,
            chunk.documentId,
            chunk.chunkIndex,
            chunk.headingPath,
            chunk.headingLevel,
            chunk.content,
            chunk.pageStart,
            chunk.pageEnd,
            chunk.slideNumber,
            chunk.charStart,
            chunk.charEnd,
            chunk.locationLabel,
            chunk.createdAt,
          ],
        )
      }
      for (const point of SYNTHETIC_KNOWLEDGE_POINTS) {
        await this.driver.run(
          `INSERT INTO local_knowledge_points
          (id, server_id, course_id, chapter_id, document_id, source_chunk_id, name, point_type, explanation, core_points, source_page, review_status, origin, confidence, created_at, updated_at, sync_state, version)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          [
            point.id,
            point.serverId,
            point.courseId,
            point.chapterId,
            point.documentId,
            null,
            point.name,
            point.pointType,
            point.explanation,
            JSON.stringify(point.corePoints),
            point.sourcePage,
            point.reviewStatus,
            point.origin,
            point.confidence,
            point.createdAt,
            point.updatedAt,
            point.syncState,
            point.version,
          ],
        )
      }
      for (const question of SYNTHETIC_QUESTIONS) {
        await this.driver.run(
          `INSERT INTO local_questions
          (id, server_id, course_id, chapter_id, stem, question_type, options, answer, explanation, difficulty, status, origin, created_at, updated_at, sync_state, version)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          [
            question.id,
            question.serverId,
            question.courseId,
            question.chapterId,
            question.stem,
            question.questionType,
            JSON.stringify(question.options),
            JSON.stringify(question.answer),
            question.explanation,
            question.difficulty,
            question.status,
            question.origin,
            question.createdAt,
            question.updatedAt,
            question.syncState,
            question.version,
          ],
        )
      }
      await this.driver.run(
        'INSERT OR IGNORE INTO local_question_knowledge_points(question_id, knowledge_point_id) VALUES (?, ?)',
        [SYNTHETIC_QUESTIONS[0].id, SYNTHETIC_KNOWLEDGE_POINTS[0].id],
      )
      await this.driver.run(
        `INSERT INTO local_practice_sessions
        (id, server_id, user_id, course_id, chapter_id, status, question_ids, total_questions, correct_count, score, started_at, finished_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          SYNTHETIC_SESSION.id,
          SYNTHETIC_SESSION.serverId,
          SYNTHETIC_SESSION.userId,
          SYNTHETIC_SESSION.courseId,
          SYNTHETIC_SESSION.chapterId,
          SYNTHETIC_SESSION.status,
          JSON.stringify(SYNTHETIC_SESSION.questionIds),
          SYNTHETIC_SESSION.totalQuestions,
          SYNTHETIC_SESSION.correctCount,
          SYNTHETIC_SESSION.score,
          SYNTHETIC_SESSION.startedAt,
          SYNTHETIC_SESSION.finishedAt,
          SYNTHETIC_SESSION.updatedAt,
          SYNTHETIC_SESSION.syncState,
          SYNTHETIC_SESSION.version,
        ],
      )
      for (const answer of SYNTHETIC_ANSWERS) {
        await this.driver.run(
          `INSERT INTO local_practice_answers
          (id, server_id, session_id, question_id, question_snapshot, user_answer, is_correct, score, max_score, feedback, graded_by, answered_at, sync_state)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          [
            answer.id,
            answer.serverId,
            answer.sessionId,
            answer.questionId,
            JSON.stringify(answer.questionSnapshot),
            JSON.stringify(answer.userAnswer),
            answer.isCorrect === null ? null : answer.isCorrect ? 1 : 0,
            answer.score,
            answer.maxScore,
            answer.feedback,
            answer.gradedBy,
            answer.answeredAt,
            answer.syncState,
          ],
        )
      }
      await this.driver.run(
        "INSERT OR REPLACE INTO local_meta(key, value) VALUES ('synthetic_only', '1')",
      )
      await this.driver.commitTransaction()
    } catch (error) {
      await this.driver.rollbackTransaction().catch(() => undefined)
      throw new LocalDatabaseError(
        `写入本地合成数据失败：${error instanceof Error ? error.message : String(error)}`,
        error,
      )
    }
  }

  async exportData(): Promise<LocalExportPayload> {
    const data = await this.readAll()
    const status = await this.status()
    return createExportPayload(
      status.schemaVersion,
      status.syntheticOnly,
      data,
    )
  }

  async importData(payload: LocalExportPayload): Promise<void> {
    if (!payload.syntheticOnly) {
      throw new LocalDatabaseError('7B 只允许导入 syntheticOnly 的导出文件')
    }
    const check = await verifyExportPayload(payload)
    if (!check.ok) {
      throw new LocalDatabaseError(check.reason ?? '导出文件校验失败')
    }
    try {
      await this.clearActiveTransaction()
      await this.driver.beginTransaction()
      for (const table of [
        'local_practice_answers',
        'local_practice_sessions',
        'local_question_knowledge_points',
        'local_questions',
        'local_knowledge_points',
        'local_chunks',
        'local_documents',
        'local_chapters',
        'local_courses',
      ]) {
        await this.driver.run(`DELETE FROM ${table}`)
      }
      await this.insertData(payload.data)
      await this.driver.run(
        "INSERT OR REPLACE INTO local_meta(key, value) VALUES ('synthetic_only', '1')",
      )
      await this.driver.commitTransaction()
    } catch (error) {
      await this.driver.rollbackTransaction().catch(() => undefined)
      throw new LocalDatabaseError(
        `导入本地数据库失败：${error instanceof Error ? error.message : String(error)}`,
        error,
      )
    }
  }

  private async insertData(data: LocalExportData): Promise<void> {
    for (const course of data.courses) {
      await this.driver.run(
        `INSERT INTO local_courses
        (id, server_id, name, description, color, icon, sort_order, created_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          course.id,
          course.serverId,
          course.name,
          course.description,
          course.color,
          course.icon,
          course.sortOrder,
          course.createdAt,
          course.updatedAt,
          course.syncState,
          course.version,
        ],
      )
    }
    for (const chapter of data.chapters) {
      await this.driver.run(
        `INSERT INTO local_chapters
        (id, server_id, course_id, parent_id, name, description, sort_order, created_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          chapter.id,
          chapter.serverId,
          chapter.courseId,
          chapter.parentId,
          chapter.name,
          chapter.description,
          chapter.sortOrder,
          chapter.createdAt,
          chapter.updatedAt,
          chapter.syncState,
          chapter.version,
        ],
      )
    }
    for (const document of data.documents) {
      await this.driver.run(
        `INSERT INTO local_documents
        (id, server_id, course_id, chapter_id, name, original_filename, mime_type, extension, size_bytes, sha256, status, parse_error, chunk_count, knowledge_point_count, local_path, created_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          document.id,
          document.serverId,
          document.courseId,
          document.chapterId,
          document.name,
          document.originalFilename,
          document.mimeType,
          document.extension,
          document.sizeBytes,
          document.sha256,
          document.status,
          document.parseError,
          document.chunkCount,
          document.knowledgePointCount,
          document.localPath,
          document.createdAt,
          document.updatedAt,
          document.syncState,
          document.version,
        ],
      )
    }
    for (const point of data.knowledgePoints) {
      await this.driver.run(
        `INSERT INTO local_knowledge_points
        (id, server_id, course_id, chapter_id, document_id, source_chunk_id, name, point_type, explanation, core_points, source_page, review_status, origin, confidence, created_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          point.id,
          point.serverId,
          point.courseId,
          point.chapterId,
          point.documentId,
          null,
          point.name,
          point.pointType,
          point.explanation,
          JSON.stringify(point.corePoints),
          point.sourcePage,
          point.reviewStatus,
          point.origin,
          point.confidence,
          point.createdAt,
          point.updatedAt,
          point.syncState,
          point.version,
        ],
      )
    }
    for (const question of data.questions) {
      await this.driver.run(
        `INSERT INTO local_questions
        (id, server_id, course_id, chapter_id, stem, question_type, options, answer, explanation, difficulty, status, origin, created_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          question.id,
          question.serverId,
          question.courseId,
          question.chapterId,
          question.stem,
          question.questionType,
          JSON.stringify(question.options),
          JSON.stringify(question.answer),
          question.explanation,
          question.difficulty,
          question.status,
          question.origin,
          question.createdAt,
          question.updatedAt,
          question.syncState,
          question.version,
        ],
      )
    }
    for (const session of data.practiceSessions) {
      await this.driver.run(
        `INSERT INTO local_practice_sessions
        (id, server_id, user_id, course_id, chapter_id, status, question_ids, total_questions, correct_count, score, started_at, finished_at, updated_at, sync_state, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          session.id,
          session.serverId,
          session.userId,
          session.courseId,
          session.chapterId,
          session.status,
          JSON.stringify(session.questionIds),
          session.totalQuestions,
          session.correctCount,
          session.score,
          session.startedAt,
          session.finishedAt,
          session.updatedAt,
          session.syncState,
          session.version,
        ],
      )
    }
    for (const answer of data.practiceAnswers) {
      await this.driver.run(
        `INSERT INTO local_practice_answers
        (id, server_id, session_id, question_id, question_snapshot, user_answer, is_correct, score, max_score, feedback, graded_by, answered_at, sync_state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [
          answer.id,
          answer.serverId,
          answer.sessionId,
          answer.questionId,
          JSON.stringify(answer.questionSnapshot),
          JSON.stringify(answer.userAnswer),
          answer.isCorrect === null ? null : answer.isCorrect ? 1 : 0,
          answer.score,
          answer.maxScore,
          answer.feedback,
          answer.gradedBy,
          answer.answeredAt,
          answer.syncState,
        ],
      )
    }
  }

  async readAll(): Promise<LocalExportData> {
    const [courses, chapters, documents, knowledgePoints, questions, sessions, answers] =
      await Promise.all([
        this.driver.query('SELECT * FROM local_courses ORDER BY sort_order, id'),
        this.driver.query('SELECT * FROM local_chapters ORDER BY sort_order, id'),
        this.driver.query('SELECT * FROM local_documents ORDER BY created_at, id'),
        this.driver.query('SELECT * FROM local_knowledge_points ORDER BY created_at, id'),
        this.driver.query('SELECT * FROM local_questions ORDER BY created_at, id'),
        this.driver.query('SELECT * FROM local_practice_sessions ORDER BY started_at, id'),
        this.driver.query('SELECT * FROM local_practice_answers ORDER BY answered_at, id'),
      ])
    return rowsToData({ courses, chapters, documents, knowledgePoints, questions, sessions, answers })
  }

  async run<T = void>(callback: (driver: LocalSqliteDriver) => Promise<T>): Promise<T> {
    return callback(this.driver)
  }
}
