import { createRequire } from 'node:module'
import initSqlJs, { type Database } from 'sql.js'
import { beforeEach, describe, expect, it } from 'vitest'

import { LocalDatabase, LocalDatabaseError } from './localDatabase'
import { LOCAL_MIGRATIONS } from './schema'
import type { LocalSqliteDriver, SqlRow, SqlValue } from './sqliteDriver'

const require = createRequire(import.meta.url)
const wasmPath = require.resolve('sql.js/dist/sql-wasm.wasm')

class SqlJsDriver implements LocalSqliteDriver {
  constructor(private db: Database) {}

  async execute(statements: string, transaction = false): Promise<void> {
    if (!transaction) {
      this.db.exec(statements)
      return
    }
    this.db.exec('BEGIN')
    try {
      this.db.exec(statements)
      this.db.exec('COMMIT')
    } catch (error) {
      this.db.exec('ROLLBACK')
      throw error
    }
  }

  async query<T extends SqlRow = SqlRow>(
    statement: string,
    values: SqlValue[] = [],
  ): Promise<T[]> {
    const statementObject = this.db.prepare(statement)
    try {
      if (values.length) {
        statementObject.bind(values)
      }
      const rows: T[] = []
      while (statementObject.step()) {
        rows.push(statementObject.getAsObject() as T)
      }
      return rows
    } finally {
      statementObject.free()
    }
  }

  async run(statement: string, values: SqlValue[] = []): Promise<void> {
    this.db.run(statement, values)
  }

  async beginTransaction(): Promise<void> {
    this.db.exec('BEGIN')
  }

  async commitTransaction(): Promise<void> {
    this.db.exec('COMMIT')
  }

  async rollbackTransaction(): Promise<void> {
    this.db.exec('ROLLBACK')
  }

  async isTransactionActive(): Promise<boolean> {
    return false
  }

  async close(): Promise<void> {
    this.db.close()
  }

  exportBytes(): Uint8Array {
    return this.db.export()
  }
}

let SQL: Awaited<ReturnType<typeof initSqlJs>>

async function freshDriver(): Promise<SqlJsDriver> {
  if (!SQL) {
    SQL = await initSqlJs({ locateFile: () => wasmPath })
  }
  return new SqlJsDriver(new SQL.Database())
}

async function openDatabase(driver: LocalSqliteDriver): Promise<LocalDatabase> {
  const database = new LocalDatabase(driver)
  await database.open()
  return database
}

beforeEach(async () => {
  if (!SQL) {
    SQL = await initSqlJs({ locateFile: () => wasmPath })
  }
})

describe('LocalDatabase', () => {
  it('creates schema v2 with foreign keys and synthetic relations', async () => {
    const driver = await freshDriver()
    const database = await openDatabase(driver)
    await database.seedSynthetic()

    const status = await database.status()
    expect(status.schemaVersion).toBe(2)
    expect(status.foreignKeys).toBe(true)
    expect(status.syntheticOnly).toBe(true)
    expect(status.counts.local_courses).toBe(1)
    expect(status.counts.local_chapters).toBe(2)
    expect(status.counts.local_documents).toBe(1)
    expect(status.counts.local_knowledge_points).toBe(2)
    expect(status.counts.local_questions).toBe(2)

    const data = await database.readAll()
    expect(data.knowledgePoints[0].courseId).toBe(data.courses[0].id)
    expect(data.questions[0].chapterId).toBe(data.chapters[0].id)
    expect(data.practiceSessions[0].questionIds).toContain(data.questions[0].id)
    expect(data.practiceAnswers[0].sessionId).toBe(data.practiceSessions[0].id)
  })

  it('enforces foreign keys', async () => {
    const driver = await freshDriver()
    const database = await openDatabase(driver)
    await expect(
      database.run((db) =>
        db.run(
          `INSERT INTO local_chapters
           (id, course_id, name, created_at, updated_at)
           VALUES ('bad', 'missing-course', 'Bad', 'now', 'now')`,
        ),
      ),
    ).rejects.toThrow()
  })

  it('upgrades v1 to v2 and preserves rows', async () => {
    const driver = await freshDriver()
    await driver.execute(LOCAL_MIGRATIONS[0].statements.join(';\n'), true)
    await driver.run(
      "INSERT INTO schema_migrations(version, applied_at) VALUES (1, 'now')",
    )
    await driver.execute('PRAGMA user_version = 1')
    await driver.run(
      `INSERT INTO local_courses
       (id, name, description, created_at, updated_at)
       VALUES ('c1', 'Legacy', '', 'now', 'now')`,
    )

    const database = await openDatabase(driver)
    const versions = await driver.query<{ version: number }>(
      'SELECT version FROM schema_migrations ORDER BY version',
    )
    expect(versions.map((row) => row.version)).toEqual([1, 2])
    const columns = await driver.query<{ name: string }>(
      'PRAGMA table_info(local_documents)',
    )
    expect(columns.some((column) => column.name === 'local_path')).toBe(true)
    expect((await database.status()).counts.local_courses).toBe(1)
  })

  it('exports with SHA-256, imports into a new database, and rejects tampering', async () => {
    const first = await openDatabase(await freshDriver())
    await first.seedSynthetic()
    const exported = await first.exportData()
    expect(exported.checksum).toMatch(/^[a-f0-9]{64}$/)
    expect(exported.syntheticOnly).toBe(true)
    expect(JSON.stringify(exported)).not.toMatch(/api[_-]?key|access[_-]?token/i)

    const second = await openDatabase(await freshDriver())
    await second.importData(exported)
    const imported = await second.readAll()
    expect(imported.courses).toHaveLength(1)
    expect(imported.knowledgePoints).toHaveLength(2)
    expect(imported.questions).toHaveLength(2)
    expect(imported.practiceAnswers).toHaveLength(1)

    const tampered = {
      ...exported,
      data: { ...exported.data, courses: [{ ...exported.data.courses[0], name: 'tampered' }] },
    }
    await expect(second.importData(tampered)).rejects.toBeInstanceOf(
      LocalDatabaseError,
    )
  })

  it('reopens with records intact using saved SQLite bytes', async () => {
    const driver = await freshDriver()
    const first = await openDatabase(driver)
    await first.seedSynthetic()
    const saved = driver.exportBytes()
    await first.close()

    if (!SQL) {
      SQL = await initSqlJs({ locateFile: () => wasmPath })
    }
    const reopenedDriver = new SqlJsDriver(new SQL.Database(saved))
    const reopened = await openDatabase(reopenedDriver)
    const data = await reopened.readAll()
    expect(data.courses).toHaveLength(1)
    expect(data.knowledgePoints).toHaveLength(2)
    expect((await reopened.status()).schemaVersion).toBe(2)
  })
})
