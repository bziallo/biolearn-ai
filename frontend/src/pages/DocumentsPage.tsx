import {
  useCallback,
  useEffect,
  useState,
  type CSSProperties,
} from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ConfirmDialog } from '../components/ConfirmDialog'
import { DocumentUploadCard } from '../components/DocumentUploadCard'
import { Modal } from '../components/Modal'
import { Notice } from '../components/Notice'
import {
  deleteDocument,
  extractKnowledge,
  getDocument,
  getErrorMessage,
  getSubject,
  listDocuments,
  listSubjectChapters,
  listSubjects,
  retryParse,
  updateDocument,
  type ChapterNode,
  type DocumentDetail,
  type DocumentSummary,
  type Subject,
} from '../lib/api'
import { flattenTree } from '../lib/chapterTree'
import {
  documentStatusLabels,
  formatBytes,
  formatDate,
} from '../lib/format'
import { useToast } from '../lib/useToast'

type PageStatus = 'loading' | 'ready' | 'error'

export function DocumentsPage() {
  const { subjectId = '' } = useParams<{ subjectId: string }>()
  const navigate = useNavigate()
  const { notify } = useToast()

  const [subject, setSubject] = useState<Subject | null>(null)
  const [chapters, setChapters] = useState<ChapterNode[]>([])
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [status, setStatus] = useState<PageStatus>('loading')
  const [error, setError] = useState('')

  const [viewingId, setViewingId] = useState<string | null>(null)
  const [viewing, setViewing] = useState<DocumentDetail | null>(null)
  const [viewingLoading, setViewingLoading] = useState(false)
  const [viewingError, setViewingError] = useState('')

  const [deleting, setDeleting] = useState<DocumentSummary | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [extractingId, setExtractingId] = useState<string | null>(null)
  const [allSubjects, setAllSubjects] = useState<Subject[]>([])
  const [editingAttribution, setEditingAttribution] =
    useState<DocumentSummary | null>(null)
  const [attributionSubjectId, setAttributionSubjectId] = useState('')
  const [attributionChapterId, setAttributionChapterId] = useState('')
  const [attributionChapters, setAttributionChapters] = useState<ChapterNode[]>(
    [],
  )
  const [attributionBusy, setAttributionBusy] = useState(false)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setStatus('loading')
      setError('')
      try {
        const [nextSubject, nextChapters, nextDocuments, nextSubjects] =
          await Promise.all([
            getSubject(subjectId, signal),
            listSubjectChapters(subjectId, signal),
            listDocuments({ subject_id: subjectId }),
            listSubjects(signal),
          ])
        setSubject(nextSubject)
        setChapters(nextChapters)
        setDocuments(nextDocuments)
        setAllSubjects(nextSubjects)
        setStatus('ready')
      } catch (loadError) {
        if (signal?.aborted) {
          return
        }
        setStatus('error')
        setError(getErrorMessage(loadError))
      }
    },
    [subjectId],
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const refreshDocuments = useCallback(async () => {
    try {
      const nextDocuments = await listDocuments({ subject_id: subjectId })
      setDocuments(nextDocuments)
    } catch (refreshError) {
      notify('error', getErrorMessage(refreshError))
    }
  }, [subjectId, notify])

  useEffect(() => {
    if (
      !documents.some(
        (document) =>
          document.status === 'uploaded' || document.status === 'parsing',
      )
    ) {
      return
    }
    const timer = globalThis.setInterval(() => {
      void refreshDocuments()
    }, 1800)
    return () => globalThis.clearInterval(timer)
  }, [documents, refreshDocuments])

  useEffect(() => {
    if (!viewingId) {
      setViewing(null)
      return
    }
    const controller = new AbortController()
    setViewingLoading(true)
    setViewingError('')
    getDocument(viewingId, controller.signal)
      .then((detail) => {
        setViewing(detail)
        setViewingLoading(false)
      })
      .catch((viewError: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setViewingError(getErrorMessage(viewError))
        setViewingLoading(false)
      })
    return () => controller.abort()
  }, [viewingId])

  useEffect(() => {
    if (!editingAttribution || !attributionSubjectId) {
      setAttributionChapters([])
      return
    }
    const controller = new AbortController()
    listSubjectChapters(attributionSubjectId, controller.signal)
      .then(setAttributionChapters)
      .catch((chaptersError: unknown) => {
        if (!controller.signal.aborted) {
          notify('error', getErrorMessage(chaptersError))
        }
      })
    return () => controller.abort()
  }, [editingAttribution, attributionSubjectId, notify])

  function openAttribution(document: DocumentSummary) {
    setEditingAttribution(document)
    setAttributionSubjectId(document.subject_id)
    setAttributionChapterId(document.chapter_id ?? '')
  }

  async function saveAttribution() {
    if (!editingAttribution) {
      return
    }
    setAttributionBusy(true)
    try {
      const updated = await updateDocument(editingAttribution.id, {
        subject_id: attributionSubjectId,
        chapter_id: attributionChapterId || null,
      })
      setDocuments((current) =>
        updated.subject_id === subjectId
          ? current.map((item) => (item.id === updated.id ? updated : item))
          : current.filter((item) => item.id !== updated.id),
      )
      setEditingAttribution(null)
      notify(
        'success',
        updated.subject_id === subjectId
          ? '资料归属已更新'
          : '资料已移动到其他学科，已从当前资料库移除',
      )
    } catch (attributionError) {
      notify('error', getErrorMessage(attributionError))
    } finally {
      setAttributionBusy(false)
    }
  }

  function handleUploaded(document: DocumentSummary) {
    setDocuments((current) => [
      document,
      ...current.filter((item) => item.id !== document.id),
    ])
  }

  async function handleRetry(document: DocumentSummary) {
    try {
      await retryParse(document.id)
      notify('success', '已重新开始解析')
      await refreshDocuments()
    } catch (retryError) {
      notify('error', getErrorMessage(retryError))
    }
  }

  async function handleExtract(document: DocumentSummary) {
    setExtractingId(document.id)
    try {
      await extractKnowledge(document.id)
      notify('success', 'AI 任务已启动')
      navigate(`/documents/${document.id}/review`)
    } catch (extractError) {
      notify('error', getErrorMessage(extractError))
    } finally {
      setExtractingId(null)
    }
  }

  async function handleDelete() {
    if (!deleting) {
      return
    }
    setDeleteBusy(true)
    try {
      await deleteDocument(
        deleting.id,
        deleting.knowledge_point_count > 0,
      )
      setDeleting(null)
      setViewingId(null)
      await refreshDocuments()
      notify('success', '资料已删除')
    } catch (deleteError) {
      notify('error', getErrorMessage(deleteError))
    } finally {
      setDeleteBusy(false)
    }
  }

  const totalPoints = documents.reduce(
    (total, document) => total + document.knowledge_point_count,
    0,
  )

  if (status === 'error' || !subject) {
    return (
      <div className="documents-page">
        <Link className="back-link" to="/subjects">
          ← 返回学科列表
        </Link>
        <div className="error-panel">
          <Notice kind="error">无法加载资料库：{error}</Notice>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void load()}
          >
            重新加载
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="documents-page">
      <Link className="back-link" to={`/subjects/${subject.id}`}>
        ← 返回 {subject.name}
      </Link>

      <header
        className="page-heading documents-heading"
        style={
          {
            '--subject-color': subject.color ?? '#5fe3a6',
          } as CSSProperties
        }
      >
        <div>
          <p className="eyebrow">Material library</p>
          <h1>资料库</h1>
          <p className="lede">
            {subject.icon ?? '📚'} {subject.name} · 上传资料后先解析为结构化分块，
            再由 AI 生成待审核知识点。
          </p>
        </div>
      </header>

      <div className="stats-row">
        <span className="stat-chip">
          <strong>{documents.length}</strong> 份资料
        </span>
        <span className="stat-chip">
          <strong>
            {documents.filter((document) => document.status === 'parsed').length}
          </strong>{' '}
          已解析
        </span>
        <span className="stat-chip">
          <strong>{totalPoints}</strong> 个知识点
        </span>
        <span className="stat-chip stat-chip-muted">
          文件保存在服务器本地上传目录
        </span>
      </div>

      <div className="documents-import-cta">
        <Link
          className="button button-ghost"
          to={`/import?subject=${subject.id}`}
        >
          使用智能导入（自动识别章节）
        </Link>
      </div>

      <DocumentUploadCard
        subjectId={subject.id}
        tree={chapters}
        onUploaded={handleUploaded}
      />

      {status === 'loading' && (
        <div className="loading-block">正在加载资料…</div>
      )}

      {status === 'ready' && documents.length === 0 && (
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">
            📄
          </span>
          <h2>还没有资料</h2>
          <p>
            上传本章的 PDF、DOCX、PPTX、TXT 或 Markdown，系统会保留页码/幻灯片位置并建立可追溯分块。
          </p>
        </div>
      )}

      {status === 'ready' && documents.length > 0 && (
        <div className="document-list">
          {documents.map((document) => (
            <article className="document-card" key={document.id}>
              <div className="document-card-head">
                <div className="document-identity">
                  <span className="document-format">
                    {document.extension.replace('.', '').toUpperCase()}
                  </span>
                  <div>
                    <h2>{document.name}</h2>
                    <p>{document.original_filename}</p>
                  </div>
                </div>
                <span
                  className={`status-badge document-status-${document.status}`}
                >
                  {documentStatusLabels[document.status]}
                </span>
              </div>

              <dl className="document-meta">
                <div>
                  <dt>大小</dt>
                  <dd>{formatBytes(document.size_bytes)}</dd>
                </div>
                <div>
                  <dt>所属章节</dt>
                  <dd>{document.chapter_name ?? '未指定'}</dd>
                </div>
                <div>
                  <dt>解析分块</dt>
                  <dd>{document.chunk_count}</dd>
                </div>
                <div>
                  <dt>知识点</dt>
                  <dd>
                    {document.knowledge_point_count}（已通过{' '}
                    {document.approved_count}）
                  </dd>
                </div>
                <div>
                  <dt>上传时间</dt>
                  <dd>{formatDate(document.uploaded_at)}</dd>
                </div>
                <div>
                  <dt>页/幻灯片</dt>
                  <dd>
                    {document.page_count
                      ? `${document.page_count} 页`
                      : document.slide_count
                        ? `${document.slide_count} 张`
                        : '—'}
                  </dd>
                </div>
              </dl>

              {document.parse_error && (
                <Notice kind="error">{document.parse_error}</Notice>
              )}
              {document.parse_warnings && (
                <Notice kind="info">
                  {document.parse_warnings.split('\n')[0]}
                </Notice>
              )}

              <div className="document-actions">
                <button
                  type="button"
                  className="button button-small"
                  onClick={() => setViewingId(document.id)}
                >
                  查看解析
                </button>
                <button
                  type="button"
                  className="button button-small button-ghost"
                  onClick={() => openAttribution(document)}
                >
                  调整归属
                </button>
                {(document.status === 'failed' ||
                  document.status === 'needs_ocr') && (
                  <button
                    type="button"
                    className="button button-small button-ghost"
                    onClick={() => void handleRetry(document)}
                  >
                    重试解析
                  </button>
                )}
                <button
                  type="button"
                  className="button button-small button-primary"
                  onClick={() => void handleExtract(document)}
                  disabled={
                    document.status !== 'parsed' ||
                    document.chunk_count === 0 ||
                    extractingId === document.id
                  }
                >
                  {extractingId === document.id ? '启动中…' : 'AI 建知识点'}
                </button>
                <Link
                  className="button button-small button-ghost"
                  to={`/documents/${document.id}/review`}
                >
                  审核知识点
                </Link>
                <button
                  type="button"
                  className="button button-small button-danger-ghost"
                  onClick={() => setDeleting(document)}
                >
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <Modal
        open={viewingId !== null}
        title={viewing ? `解析结果 · ${viewing.name}` : '解析结果'}
        onClose={() => setViewingId(null)}
      >
        {viewingLoading && <div className="loading-block">正在加载解析结果…</div>}
        {viewingError && <Notice kind="error">{viewingError}</Notice>}
        {viewing && !viewingLoading && (
          <div className="parse-viewer">
            <div className="parse-viewer-meta">
              <span>{viewing.original_filename}</span>
              <span>{viewing.chunk_count} 个分块</span>
              <span>{documentStatusLabels[viewing.status]}</span>
            </div>
            {viewing.parse_error && (
              <Notice kind="error">{viewing.parse_error}</Notice>
            )}
            {viewing.parse_warnings && (
              <Notice kind="info">{viewing.parse_warnings}</Notice>
            )}
            {viewing.chunks.length === 0 ? (
              <div className="empty-state empty-state-compact">
                <p>这份资料没有可展示的正文分块。</p>
              </div>
            ) : (
              viewing.chunks.map((chunk) => (
                <article className="parse-chunk" key={chunk.id}>
                  <header>
                    <span>{chunk.location_label}</span>
                    <strong>{chunk.heading_path ?? '正文'}</strong>
                  </header>
                  <pre>{chunk.content}</pre>
                </article>
              ))
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={editingAttribution !== null}
        title="调整资料归属"
        onClose={() => {
          if (!attributionBusy) {
            setEditingAttribution(null)
          }
        }}
      >
        {editingAttribution && (
          <div className="form-stack">
            <p className="form-hint">
              调整后，该资料下已有知识点的学科/章节归属会同步更新；审核状态和内容不变。
            </p>
            <div className="field">
              <label htmlFor="attribution-subject">学科</label>
              <select
                id="attribution-subject"
                value={attributionSubjectId}
                onChange={(event) => {
                  setAttributionSubjectId(event.target.value)
                  setAttributionChapterId('')
                }}
              >
                {allSubjects.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="attribution-chapter">章节</label>
              <select
                id="attribution-chapter"
                value={attributionChapterId}
                onChange={(event) =>
                  setAttributionChapterId(event.target.value)
                }
              >
                <option value="">学科根目录（不指定章节）</option>
                {flattenTree(attributionChapters).map(({ node, depth }) => (
                  <option value={node.id} key={node.id}>
                    {'— '.repeat(depth)}
                    {node.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-actions">
              <button
                type="button"
                className="button button-ghost"
                onClick={() => setEditingAttribution(null)}
                disabled={attributionBusy}
              >
                取消
              </button>
              <button
                type="button"
                className="button button-primary"
                onClick={() => void saveAttribution()}
                disabled={attributionBusy || !attributionSubjectId}
              >
                {attributionBusy ? '保存中…' : '保存归属'}
              </button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        title="删除资料"
        description={
          deleting
            ? deleting.knowledge_point_count > 0
              ? `「${deleting.name}」关联 ${deleting.knowledge_point_count} 个知识点。删除资料会同时删除这些知识点和解析分块，且无法恢复。`
              : `删除「${deleting.name}」会移除服务器上的文件和解析分块。`
            : ''
        }
        confirmLabel="删除资料"
        busy={deleteBusy}
        acknowledgement={
          deleting && deleting.knowledge_point_count > 0
            ? `我了解将同时删除 ${deleting.knowledge_point_count} 个知识点`
            : undefined
        }
        onConfirm={() => void handleDelete()}
        onCancel={() => {
          if (!deleteBusy) {
            setDeleting(null)
          }
        }}
      />
    </div>
  )
}
