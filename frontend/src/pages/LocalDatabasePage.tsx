import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { Notice } from '../components/Notice'
import {
  closeLocalDatabase,
  getLocalDatabase,
  localBundle,
} from '../lib/local/repositories'
import {
  cleanupTemporaryFiles,
  deleteStoredFile,
  FileStorageError,
  isNativeFileStorageAvailable,
  MAX_LOCAL_TEXT_BYTES,
  readStoredText,
  storeTextFile,
} from '../lib/local/fileStore'
import {
  parseTextDocument,
  TextParseError,
  type ParsedTextDocument,
} from '../lib/local/textParser'
import {
  isLocalDbEnabled,
  localDbFlagSource,
  setLocalDbEnabled,
} from '../lib/local/featureFlag'
import { formatBytes, formatDate } from '../lib/format'
import type {
  LocalDatabaseStatus,
  LocalExportPayload,
  LocalFileRecord,
  LocalParseJob,
  LocalUploadJob,
} from '../lib/local/types'
import { useToast } from '../lib/useToast'

const PLUGIN_VERSION = '7.0.3'

export function LocalDatabasePage() {
  const { notify } = useToast()
  const [enabled, setEnabled] = useState(isLocalDbEnabled())
  const [status, setStatus] = useState<LocalDatabaseStatus | null>(null)
  const [sample, setSample] = useState<string[]>([])
  const [exported, setExported] = useState<LocalExportPayload | null>(null)
  const [error, setError] = useState('')
  const [fileError, setFileError] = useState('')
  const [busy, setBusy] = useState(false)
  const [files, setFiles] = useState<LocalFileRecord[]>([])
  const [parseJobs, setParseJobs] = useState<LocalParseJob[]>([])
  const [uploadJobs, setUploadJobs] = useState<LocalUploadJob[]>([])
  const [preview, setPreview] = useState<{
    file: LocalFileRecord
    parsed: ParsedTextDocument
  } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

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
      setFiles(await database.listFiles())
      setParseJobs(await database.listParseJobs())
      setUploadJobs(await database.listUploadJobs())
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

  async function importTextFile(file: File) {
    if (!enabled) {
      setFileError('请先开启本地数据库')
      return
    }
    setFileError('')
    setPreview(null)
    setBusy(true)
    try {
      const database = await getLocalDatabase()
      await database.seedSynthetic()
      const stored = await storeTextFile(file)
      let parsed: ParsedTextDocument
      try {
        parsed = await parseTextDocument(
          await readStoredText(stored.relativePath),
          stored.originalFilename,
          stored.id,
        )
      } catch (parseError) {
        try {
          await database.recordFailedTextDocument(
            stored,
            parseError instanceof Error ? parseError.message : '本地文本解析失败',
          )
        } catch (recordError) {
          await deleteStoredFile(stored.relativePath).catch(() => undefined)
          setFileError(
            recordError instanceof Error
              ? recordError.message
              : '保存失败文件记录失败',
          )
          await refresh()
          return
        }
        setFileError(
          parseError instanceof TextParseError
            ? parseError.message
            : '本地文本解析失败，文件已保存但不会写入知识点',
        )
        await refresh()
        return
      }

      try {
        await database.createTextDocument(stored, parsed)
      } catch (dbError) {
        await deleteStoredFile(stored.relativePath).catch(() => undefined)
        await cleanupTemporaryFiles()
        setFileError(
          dbError instanceof Error ? dbError.message : '本地数据库记录失败',
        )
        return
      }
      const nextFile = (await database.listFiles()).find(
        (item) => item.documentId === stored.id,
      )
      if (nextFile) {
        setPreview({ file: nextFile, parsed })
      }
      await refresh()
      notify(
        'success',
        `本地文本解析完成：${parsed.chunks.length} 个片段；未进行 AI 知识点提取`,
      )
    } catch (importError) {
      setFileError(
        importError instanceof FileStorageError
          ? importError.message
          : importError instanceof Error
            ? importError.message
            : '文件保存失败',
      )
    } finally {
      setBusy(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  async function previewStored(item: LocalFileRecord) {
    setFileError('')
    setBusy(true)
    try {
      const bytes = await readStoredText(item.relativePath)
      const parsed = await parseTextDocument(
        bytes,
        item.originalFilename,
        item.documentId,
      )
      setPreview({ file: item, parsed })
      notify('success', '从私有目录重新读取并完成本地文本解析')
    } catch (previewError) {
      setFileError(
        previewError instanceof Error ? previewError.message : '读取私有文件失败',
      )
    } finally {
      setBusy(false)
    }
  }

  async function retryQueue(job: LocalUploadJob) {
    try {
      const database = await getLocalDatabase()
      await database.requeueUploadJob(job.id)
      await refresh()
      notify('info', '任务已重新排队；7C 不会自动上传，也不会把状态标为成功')
    } catch (queueError) {
      setFileError(queueError instanceof Error ? queueError.message : '重新排队失败')
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
        <p className="eyebrow">Local files · 7C</p>
        <h1>本地文件与数据库</h1>
        <p className="lede">
          TXT/MD 复制到 App 私有目录并在本地分段；默认关闭，关闭时所有业务仍走 FastAPI。
          本页不会把现有业务页面切换到本地数据，也不会自动上传。
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
        7C 不写真实服务端 SQLite、不同步、不自动上传。文件只存在 App 私有目录；
        本地解析完成不等于 AI 知识提取完成；导出不包含文件/Key/token。
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
            当前是默认路径：FastAPI。开启仅用于 7C 验证；不会自动改变现有课程/资料/审核页面。
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

      <section className="panel">
        <h2>私有文件与 TXT/MD 离线解析</h2>
        <p className="form-hint">
          只复制到 App 私有目录，不使用临时 SAF URI 作为永久路径。文件上限{' '}
          {MAX_LOCAL_TEXT_BYTES / (1024 * 1024)} MB；PDF/DOCX/PPTX 仍走 FastAPI。
        </p>
        {!isNativeFileStorageAvailable() && (
          <Notice kind="info">
            浏览器/桌面没有 Android Filesystem；本地文件功能不可用，现有 FastAPI 上传不受影响。
          </Notice>
        )}
        <div className="form-actions">
          <input
            ref={fileInputRef}
            className="visually-hidden"
            type="file"
            accept=".txt,.md,.markdown,text/plain,text/markdown"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) {
                void importTextFile(file)
              }
            }}
            aria-label="选择本地 TXT 或 Markdown"
          />
          <button
            type="button"
            className="button button-primary"
            onClick={() => fileInputRef.current?.click()}
            disabled={!enabled || busy || !isNativeFileStorageAvailable()}
          >
            选择 TXT/MD 并复制到私有目录
          </button>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => {
              void cleanupTemporaryFiles().then((count) => {
                notify('success', count ? `已清理 ${count} 个临时文件` : '没有临时文件')
              })
            }}
            disabled={!enabled || busy || !isNativeFileStorageAvailable()}
          >
            清理 .part 临时文件
          </button>
        </div>
        {fileError && <Notice kind="error">{fileError}</Notice>}
        {preview && (
          <div className="local-db-export">
            <Notice kind="success">
              本地文本解析完成（{preview.parsed.chunks.length} 个片段）。这不是 AI
              知识点提取；未写入正式知识库、未自动批准知识点。
            </Notice>
            <p>
              {preview.file.originalFilename} · {formatBytes(preview.file.sizeBytes)} ·{' '}
              {preview.parsed.encoding} · {preview.parsed.charCount} 字符
            </p>
            <p>
              SHA-256：<code>{preview.file.sha256}</code>
            </p>
            <p className="form-hint">私有相对路径：{preview.file.relativePath}</p>
            <pre className="local-db-preview">
              {preview.parsed.chunks[0]?.content.slice(0, 600)}
            </pre>
          </div>
        )}

        {files.length > 0 && (
          <div className="local-db-export">
            <h3>本地文件</h3>
            <ul className="local-db-sample">
              {files.map((item) => (
                <li key={item.id}>
                  {item.originalFilename} · {formatBytes(item.sizeBytes)} · {item.status} ·{' '}
                  <code>{item.sha256.slice(0, 12)}…</code> · {formatDate(item.createdAt)}
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => void previewStored(item)}
                    disabled={busy}
                  >
                    读取并预览
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {parseJobs.length > 0 && (
          <div className="local-db-export">
            <h3>解析任务</h3>
            <ul className="local-db-sample">
              {parseJobs.map((job) => (
                <li key={job.id}>
                  {job.documentId} · {job.status}
                  {job.error ? ` · ${job.error}` : ''}
                </li>
              ))}
            </ul>
          </div>
        )}

        {uploadJobs.length > 0 && (
          <div className="local-db-export">
            <h3>待上传队列</h3>
            <p className="form-hint">
              7C 只持久化队列，不自动上传；服务端尚无幂等键，不能把排队或超时当成上传成功。
            </p>
            <ul className="local-db-sample">
              {uploadJobs.map((job) => (
                <li key={job.id}>
                  {job.documentId} · {job.status} · 尝试 {job.attempts}
                  {job.lastError ? ` · ${job.lastError}` : ''}
                  {(job.status === 'failed' || job.status === 'needs_verification') && (
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => void retryQueue(job)}
                    >
                      重新排队（不执行上传）
                    </button>
                  )}
                </li>
              ))}
            </ul>
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
