import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Notice } from '../components/Notice'
import { closeLocalDatabase, getLocalDatabase, localBundle } from '../lib/local/repositories'
import {
  isLocalDbEnabled,
  localDbFlagSource,
  setLocalDbEnabled,
} from '../lib/local/featureFlag'
import type { LocalDatabaseStatus, LocalExportPayload } from '../lib/local/types'
import { useToast } from '../lib/useToast'

const PLUGIN_VERSION = '7.0.3'

export function LocalDatabasePage() {
  const { notify } = useToast()
  const [enabled, setEnabled] = useState(isLocalDbEnabled())
  const [status, setStatus] = useState<LocalDatabaseStatus | null>(null)
  const [sample, setSample] = useState<string[]>([])
  const [exported, setExported] = useState<LocalExportPayload | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    if (!enabled) {
      setStatus(null)
      setSample([])
      return
    }
    setBusy(true)
    setError('')
    try {
      const database = await getLocalDatabase()
      const nextStatus = await database.status()
      setStatus(nextStatus)
      const bundle = localBundle(database)
      const courses = await bundle.courses.list()
      const points = courses[0]
        ? await bundle.knowledgePoints.listByCourse(courses[0].id)
        : []
      setSample([
        ...courses.map((course) => `课程：${course.name}`),
        ...points.map((point) => `知识点：${point.name}`),
      ])
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : '本地数据库不可用')
      setStatus(null)
      setSample([])
    } finally {
      setBusy(false)
    }
  }, [enabled])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function toggle() {
    const next = !enabled
    setLocalDbEnabled(next)
    setEnabled(next)
    setExported(null)
    if (!next) {
      await closeLocalDatabase()
      setStatus(null)
      setSample([])
      notify('success', '已关闭本地数据库，业务恢复 FastAPI 数据源')
    }
  }

  async function seed() {
    setBusy(true)
    setError('')
    try {
      const database = await getLocalDatabase()
      await database.seedSynthetic()
      setExported(null)
      await refresh()
      notify('success', '合成数据已写入本地 SQLite')
    } catch (seedError) {
      setError(seedError instanceof Error ? seedError.message : '初始化失败')
    } finally {
      setBusy(false)
    }
  }

  async function exportDatabase() {
    setBusy(true)
    try {
      const database = await getLocalDatabase()
      const payload = await database.exportData()
      setExported(payload)
      notify('success', '已生成带 SHA-256 校验的导出摘要')
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : '导出失败')
    } finally {
      setBusy(false)
    }
  }

  async function closeAndReopen() {
    setBusy(true)
    setError('')
    try {
      await closeLocalDatabase()
      const database = await getLocalDatabase()
      const reopened = await database.status()
      setStatus(reopened)
      notify('success', '数据库已关闭并重新打开，记录仍可查询')
    } catch (reopenError) {
      setError(reopenError instanceof Error ? reopenError.message : '重新打开失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="local-db-page">
      <header className="page-heading">
        <p className="eyebrow">Local SQLite · 7B</p>
        <h1>本地数据库诊断</h1>
        <p className="lede">
          只读合成数据基础层。默认关闭；关闭时所有业务仍走 FastAPI。开启后本页只用于验证
          本地 SQLite，不会把现有业务页面切换到本地数据。
        </p>
      </header>

      <div className="stats-row">
        <span className="stat-chip">
          插件 <strong>@capacitor-community/sqlite {PLUGIN_VERSION}</strong>
        </span>
        <span className="stat-chip">
          开关 <strong>{enabled ? '开' : '关'}</strong>（{localDbFlagSource()}）
        </span>
        <span className="stat-chip">
          schema <strong>{status?.schemaVersion ?? '—'}</strong>
        </span>
        <span className="stat-chip">
          外键 <strong>{status?.foreignKeys ? 'ON' : '—'}</strong>
        </span>
      </div>

      <Notice kind="info">
        7B 不写入真实 SQLite、不同步、不导入真实课程数据。此页的“合成数据”只存在 App
        私有数据库；导出不包含 AI Key、访问令牌或服务端配置。
      </Notice>

      {error && <Notice kind="error">{error}</Notice>}

      <section className="panel">
        <h2>开关与生命周期</h2>
        <div className="form-actions">
          <button type="button" className="button button-primary" onClick={() => void toggle()}>
            {enabled ? '关闭本地数据库' : '开启本地数据库（本机）'}
          </button>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void refresh()}
            disabled={!enabled || busy}
          >
            {busy ? '查询中…' : '查询状态'}
          </button>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void closeAndReopen()}
            disabled={!enabled || busy}
          >
            关闭并重新打开
          </button>
        </div>
        {!enabled && (
          <p className="form-hint">
            当前是默认路径：FastAPI。开启仅用于 7B 验证；不会自动改变现有课程/资料/审核页面。
          </p>
        )}
        {enabled && (
          <p className="form-hint">
            数据库文件位于 Android App 私有目录；浏览器/桌面无法打开原生 SQLite。
          </p>
        )}
      </section>

      <section className="panel">
        <h2>合成数据</h2>
        <div className="form-actions">
          <button
            type="button"
            className="button button-primary"
            onClick={() => void seed()}
            disabled={!enabled || busy}
          >
            初始化/写入合成课程
          </button>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void exportDatabase()}
            disabled={!enabled || busy || !status?.counts.local_courses}
          >
            导出校验摘要
          </button>
        </div>
        {status && (
          <div className="local-db-counts">
            {Object.entries(status.counts).map(([table, count]) => (
              <span className="stat-chip" key={table}>
                {table.replace('local_', '')} <strong>{count}</strong>
              </span>
            ))}
          </div>
        )}
        {sample.length > 0 && (
          <ul className="local-db-sample">
            {sample.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}
        {status && status.counts.local_courses === 0 && (
          <p className="form-hint">还没有合成数据；点击“初始化/写入合成课程”。</p>
        )}
        {exported && (
          <div className="local-db-export">
            <p>
              校验：<code>{exported.checksum}</code>
            </p>
            <p>
              格式：{exported.format} · schema {exported.schemaVersion} · syntheticOnly=
              {String(exported.syntheticOnly)}
            </p>
            <p className="form-hint">
              导出仅包含本地课程/章节/文档元数据/知识点/题目/练习/答题；不含文件、Key、token。
            </p>
          </div>
        )}
      </section>

      <p className="form-hint">
        回滚：关闭上方开关即可恢复 FastAPI 路径；不要通过删除本地数据库完成常规回滚。
        <Link className="text-link" to="/settings/connection"> 返回连接设置</Link>
      </p>
    </div>
  )
}
