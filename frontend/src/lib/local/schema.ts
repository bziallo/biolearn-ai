export const LOCAL_DB_NAME = 'biolearn_local'
export const LOCAL_DB_SCHEMA_VERSION = 2

export interface LocalMigration {
  version: number
  statements: string[]
}

const v1 = [
  `CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
  )`,
  `CREATE TABLE IF NOT EXISTS local_courses (
    id TEXT PRIMARY KEY,
    server_id TEXT UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    color TEXT,
    icon TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_state TEXT NOT NULL DEFAULT 'pending_create',
    version INTEGER NOT NULL DEFAULT 0
  )`,
  `CREATE TABLE IF NOT EXISTS local_chapters (
    id TEXT PRIMARY KEY,
    server_id TEXT UNIQUE,
    course_id TEXT NOT NULL REFERENCES local_courses(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES local_chapters(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_state TEXT NOT NULL DEFAULT 'pending_create',
    version INTEGER NOT NULL DEFAULT 0
  )`,
  `CREATE INDEX IF NOT EXISTS idx_local_chapters_course ON local_chapters(course_id)`,
  `CREATE INDEX IF NOT EXISTS idx_local_chapters_parent ON local_chapters(parent_id)`,
  `CREATE TABLE IF NOT EXISTS local_documents (
    id TEXT PRIMARY KEY,
    server_id TEXT UNIQUE,
    course_id TEXT NOT NULL REFERENCES local_courses(id) ON DELETE CASCADE,
    chapter_id TEXT REFERENCES local_chapters(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    parse_error TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    knowledge_point_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_state TEXT NOT NULL DEFAULT 'pending_create',
    version INTEGER NOT NULL DEFAULT 0
  )`,
  `CREATE INDEX IF NOT EXISTS idx_local_documents_course ON local_documents(course_id)`,
  `CREATE INDEX IF NOT EXISTS idx_local_documents_chapter ON local_documents(chapter_id)`,
  `CREATE TABLE IF NOT EXISTS local_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES local_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    heading_path TEXT,
    heading_level INTEGER,
    content TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    slide_number INTEGER,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    location_label TEXT NOT NULL,
    created_at TEXT NOT NULL
  )`,
  `CREATE INDEX IF NOT EXISTS idx_local_chunks_document ON local_chunks(document_id)`,
  `CREATE TABLE IF NOT EXISTS local_knowledge_points (
    id TEXT PRIMARY KEY,
    server_id TEXT UNIQUE,
    course_id TEXT NOT NULL REFERENCES local_courses(id) ON DELETE CASCADE,
    chapter_id TEXT REFERENCES local_chapters(id) ON DELETE SET NULL,
    document_id TEXT REFERENCES local_documents(id) ON DELETE CASCADE,
    source_chunk_id TEXT REFERENCES local_chunks(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    point_type TEXT NOT NULL,
    explanation TEXT NOT NULL DEFAULT '',
    core_points TEXT NOT NULL DEFAULT '[]',
    source_page INTEGER,
    review_status TEXT NOT NULL DEFAULT 'pending',
    origin TEXT NOT NULL DEFAULT 'manual',
    confidence REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_state TEXT NOT NULL DEFAULT 'pending_create',
    version INTEGER NOT NULL DEFAULT 0
  )`,
  `CREATE INDEX IF NOT EXISTS idx_local_points_course ON local_knowledge_points(course_id)`,
  `CREATE INDEX IF NOT EXISTS idx_local_points_document ON local_knowledge_points(document_id)`,
  `CREATE TABLE IF NOT EXISTS local_questions (
    id TEXT PRIMARY KEY,
    server_id TEXT UNIQUE,
    course_id TEXT NOT NULL REFERENCES local_courses(id) ON DELETE CASCADE,
    chapter_id TEXT REFERENCES local_chapters(id) ON DELETE SET NULL,
    stem TEXT NOT NULL,
    question_type TEXT NOT NULL,
    options TEXT NOT NULL DEFAULT '[]',
    answer TEXT NOT NULL DEFAULT '{}',
    explanation TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    origin TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_state TEXT NOT NULL DEFAULT 'pending_create',
    version INTEGER NOT NULL DEFAULT 0
  )`,
  `CREATE INDEX IF NOT EXISTS idx_local_questions_course ON local_questions(course_id)`,
  `CREATE TABLE IF NOT EXISTS local_question_knowledge_points (
    question_id TEXT NOT NULL REFERENCES local_questions(id) ON DELETE CASCADE,
    knowledge_point_id TEXT NOT NULL REFERENCES local_knowledge_points(id) ON DELETE CASCADE,
    PRIMARY KEY (question_id, knowledge_point_id)
  )`,
  `CREATE TABLE IF NOT EXISTS local_practice_sessions (
    id TEXT PRIMARY KEY,
    server_id TEXT UNIQUE,
    user_id TEXT,
    course_id TEXT NOT NULL REFERENCES local_courses(id) ON DELETE CASCADE,
    chapter_id TEXT REFERENCES local_chapters(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    question_ids TEXT NOT NULL DEFAULT '[]',
    total_questions INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    score REAL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    updated_at TEXT NOT NULL,
    sync_state TEXT NOT NULL DEFAULT 'pending_create',
    version INTEGER NOT NULL DEFAULT 0
  )`,
  `CREATE INDEX IF NOT EXISTS idx_local_sessions_course ON local_practice_sessions(course_id)`,
  `CREATE TABLE IF NOT EXISTS local_practice_answers (
    id TEXT PRIMARY KEY,
    server_id TEXT UNIQUE,
    session_id TEXT NOT NULL REFERENCES local_practice_sessions(id) ON DELETE CASCADE,
    question_id TEXT REFERENCES local_questions(id) ON DELETE SET NULL,
    question_snapshot TEXT NOT NULL,
    user_answer TEXT NOT NULL,
    is_correct INTEGER,
    score REAL,
    max_score REAL NOT NULL DEFAULT 1,
    feedback TEXT,
    graded_by TEXT NOT NULL DEFAULT 'auto',
    answered_at TEXT NOT NULL,
    sync_state TEXT NOT NULL DEFAULT 'pending_create'
  )`,
  `CREATE INDEX IF NOT EXISTS idx_local_answers_session ON local_practice_answers(session_id)`,
  `CREATE TABLE IF NOT EXISTS local_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  )`,
]

const v2 = [
  // 7C will store a copied app-private file; the column is added by a migration
  // so 7B already exercises an incremental schema upgrade.
  `ALTER TABLE local_documents ADD COLUMN local_path TEXT`,
]

export const LOCAL_MIGRATIONS: LocalMigration[] = [
  { version: 1, statements: v1 },
  { version: 2, statements: v2 },
]
