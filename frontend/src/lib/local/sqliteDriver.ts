import { Capacitor } from '@capacitor/core'
import {
  CapacitorSQLite,
  SQLiteConnection,
  type SQLiteDBConnection,
} from '@capacitor-community/sqlite'

import { LOCAL_DB_NAME, LOCAL_DB_SCHEMA_VERSION } from './schema'

export type SqlValue = string | number | null
export type SqlRow = Record<string, unknown>

export interface LocalSqliteDriver {
  open?(): Promise<void>
  execute(statements: string, transaction?: boolean): Promise<void>
  query<T extends SqlRow = SqlRow>(
    statement: string,
    values?: SqlValue[],
  ): Promise<T[]>
  run(statement: string, values?: SqlValue[]): Promise<void>
  beginTransaction(): Promise<void>
  commitTransaction(): Promise<void>
  rollbackTransaction(): Promise<void>
  isTransactionActive(): Promise<boolean>
  close(): Promise<void>
}

class CapacitorSqliteDriver implements LocalSqliteDriver {
  private connection: SQLiteDBConnection | null = null
  private sqlite: SQLiteConnection

  constructor() {
    if (!Capacitor.isNativePlatform()) {
      throw new Error(
        '本地 SQLite 只在 Android 原生环境可用；浏览器/桌面继续使用 FastAPI。',
      )
    }
    this.sqlite = new SQLiteConnection(CapacitorSQLite)
  }

  async open(): Promise<void> {
    if (this.connection) {
      return
    }
    const existing = await this.sqlite.isConnection(LOCAL_DB_NAME, false)
    const connection = existing.result
      ? await this.sqlite.retrieveConnection(LOCAL_DB_NAME, false)
      : await this.sqlite.createConnection(
          LOCAL_DB_NAME,
          false,
          'no-encryption',
          LOCAL_DB_SCHEMA_VERSION,
          false,
        )
    const openState = await connection.isDBOpen()
    if (!openState.result) {
      await connection.open()
    }
    this.connection = connection
  }

  async execute(statements: string, transaction = false): Promise<void> {
    if (!this.connection) {
      throw new Error('本地数据库尚未打开')
    }
    await this.connection.execute(statements, transaction)
  }

  async query<T extends SqlRow = SqlRow>(
    statement: string,
    values: SqlValue[] = [],
  ): Promise<T[]> {
    if (!this.connection) {
      throw new Error('本地数据库尚未打开')
    }
    const result = await this.connection.query(statement, values)
    return (result.values ?? []) as T[]
  }

  async run(statement: string, values: SqlValue[] = []): Promise<void> {
    if (!this.connection) {
      throw new Error('本地数据库尚未打开')
    }
    // The plugin defaults every run() to its own transaction. We manage the
    // transaction explicitly for seed/import, so nested BEGIN must be disabled.
    await this.connection.run(statement, values, false)
  }

  async beginTransaction(): Promise<void> {
    if (!this.connection) {
      throw new Error('本地数据库尚未打开')
    }
    await this.connection.beginTransaction()
  }

  async commitTransaction(): Promise<void> {
    if (!this.connection) {
      throw new Error('本地数据库尚未打开')
    }
    await this.connection.commitTransaction()
  }

  async rollbackTransaction(): Promise<void> {
    if (!this.connection) {
      throw new Error('本地数据库尚未打开')
    }
    await this.connection.rollbackTransaction()
  }

  async isTransactionActive(): Promise<boolean> {
    if (!this.connection) {
      return false
    }
    const active = await this.connection.isTransactionActive()
    return Boolean(active.result)
  }

  async close(): Promise<void> {
    if (!this.connection) {
      return
    }
    try {
      await this.connection.close()
    } finally {
      this.connection = null
      try {
        await this.sqlite.closeConnection(LOCAL_DB_NAME, false)
      } catch {
        // The plugin may already have removed the connection.
      }
    }
  }
}

export function createNativeSqliteDriver(): LocalSqliteDriver & {
  open(): Promise<void>
} {
  return new CapacitorSqliteDriver()
}
