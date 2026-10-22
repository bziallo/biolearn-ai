import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { Link, useParams } from 'react-router-dom'

import { Notice } from '../components/Notice'
import {
  getErrorMessage,
  getSubject,
  listDocuments,
  listKnowledgePoints,
  listQuestions,
  listSubjectChapters,
  retryParse,
  type ChapterNode,
  type DocumentStatus,
  type DocumentSummary,
  type KnowledgePoint,
  type Question,
  type Subject,
} from '../lib/api'
import { flattenTree } from '../lib/chapterTree'
import {
  documentStatusLabels,
  formatBytes,
  formatDate,
  knowledgeTypeLabels,
  reviewStatusLabels,
} from '../lib/format'
import { readOfflineCache, writeOfflineCache } from '../lib/offline/cache'
import { isOfflineError, useOnlineStatus } from '../lib/offline/network'
import { useToast } from '../lib/useToast'

type PageStatus = 'loading' | 'ready' | 'cache' | 'error'

interface KnowledgeSnapshot {
  subject: Subject
  chapters: ChapterNode[]
  documents: DocumentSummary[]
  points: KnowledgePoint[]
  questions: Question[]
  savedAt: string
}

const questionTypeLabels: Record<string, string> = {
  single_choice: '单选',
  multiple_choice: '多选',
  true_false: '判断',
  short_answer: '简答',
}

function cacheKey(subjectId: string): string {
  return `subject-knowledge:${subjectId}`
}

function countByChapter<T>(
  items: T[],
  getId: (item: T) => string | null,
): Map<string, number> {
  const counts = new Map<string, number>()
  for (const item of items) {
    const id = getId(item)
    if (id) {
      counts.set(id, (counts.get(id) ?? 0) + 1)
    }
  }
  return counts
}

export function SubjectKnowledgePage() {
  const { subjectId = '' } = useParams<{ subjectId: string }>()
  const { notify } = useToast()
  const online = useOnlineStatus()
  const generation = useRef(0)

  const [snapshot, setSnapshot] = useState<KnowledgeSnapshot | null>(null)
  const [status, setStatus] = useState<PageStatus>('loading')
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [chapterFilter, setChapterFilter] = useState('all')
  const [pointQuery, setPointQuery] = useState('')
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null)
  const [retryingDocumentId, setRetryingDocumentId] = useState<string | null>(
    null,
  )

  const load = useCallback(
    async (background = false) => {
      const requestId = generation.current + 1
      generation.current = requestId
      if (background) {
        setRefreshing(true)
      } else {
        setSnapshot(null)
        setStatus('loading')
        setError('')
      }

      try {
        const [subject, chapters, documents, pointsResponse, questionsResponse] =
          await Promise.all([
            getSubject(subjectId),
            listSubjectChapters(subjectId),
            listDocuments({ subject_id: subjectId }),
            listKnowledgePoints({ subject_id: subjectId, limit: 2000 }),
            listQuestions({ subject_id: subjectId, limit: 200 }),
          ])
        if (generation.current !== requestId) {
          return
        }
        const data: KnowledgeSnapshot = {
          subject,
          chapters,
          documents: documents.filter(
            (document) => document.subject_id === subjectId,
          ),
          points: pointsResponse.points.filter(
            (point) => point.subject_id === subjectId,
          ),
          questions: questionsResponse.questions.filter(
            (question) => question.subject_id === subjectId,
          ),
          savedAt: new Date().toISOString(),
        }
        setSnapshot(data)
        setStatus('ready')
        setError('')
        void writeOfflineCache(cacheKey(subjectId), data)
      } catch (loadError) {
        if (generation.current !== requestId) {
          return
        }
        if (isOfflineError(loadError) || !online) {
          const cached = await readOfflineCache<KnowledgeSnapshot>(
            cacheKey(subjectId),
          )
          if (generation.current !== requestId) {
            return
          }
          if (cached) {
            setSnapshot(cached.data)
            setStatus('cache')
            setError('')
            return
          }
          setStatus('error')
          setError(
            '当前离线，且这台设备还没有缓存该课程。请先联网打开一次课程，再离线浏览。',
          )
          return
        }
        setStatus('error')
        setError(getErrorMessage(loadError))
      } finally {
        if (generation.current === requestId) {
          setRefreshing(false)
        }
      }
    },
    [online, subjectId],
  )

  useEffect(() => {
    setChapterFilter('all')
    setPointQuery('')
    setSelectedPointId(null)
    void load()
  }, [load])

  useEffect(() => {
    if (online && status === 'cache') {
      void load(true)
    }
  }, [load, online, status])

  useEffect(() => {
    if (
      !snapshot ||
      !snapshot.documents.some(
        (document) =>
          document.status === 'uploaded' || document.status === 'parsing',
      )
    ) {
      return
    }
    const timer = globalThis.setInterval(() => {
      void load(true)
    }, 2500)
    return () => globalThis.clearInterval(timer)
  }, [load, snapshot])

  const chapterEntries = useMemo(
    () => (snapshot ? flattenTree(snapshot.chapters) : []),
    [snapshot],
  )
  const chapterName = useMemo(
    () => new Map(chapterEntries.map(({ node }) => [node.id, node.name])),
    [chapterEntries],
  )
  const pointCounts = useMemo(
    () =>
      countByChapter(snapshot?.points ?? [], (point) => point.chapter_id),
    [snapshot],
  )
  const unassignedPointCount = useMemo(
    () =>
      (snapshot?.points ?? []).filter((point) => !point.chapter_id).length,
    [snapshot],
  )
  const unassignedDocumentCount = useMemo(
    () =>
      (snapshot?.documents ?? []).filter((document) => !document.chapter_id)
        .length,
    [snapshot],
  )

  const visibleDocuments = useMemo(() => {
    if (!snapshot) {
      return []
    }
    return snapshot.documents.filter((document) => {
      if (chapterFilter === 'all') {
        return true
      }
      if (chapterFilter === 'unassigned') {
        return !document.chapter_id
      }
      return document.chapter_id === chapterFilter
    })
  }, [chapterFilter, snapshot])

  const visiblePoints = useMemo(() => {
    if (!snapshot) {
      return []
    }
    const keyword = pointQuery.trim().toLowerCase()
    return snapshot.points.filter((point) => {
      if (chapterFilter === 'all') {
        // keep all
      } else if (chapterFilter === 'unassigned') {
        if (point.chapter_id) {
          return false
        }
      } else if (point.chapter_id !== chapterFilter) {
        return false
      }
      if (!keyword) {
        return true
      }
      return (
        point.name.toLowerCase().includes(keyword) ||
        point.explanation.toLowerCase().includes(keyword) ||
        point.core_points.some((item) => item.toLowerCase().includes(keyword))
      )
    })
  }, [chapterFilter, pointQuery, snapshot])

  const visibleQuestions = useMemo(() => {
    if (!snapshot) {
      return []
    }
    return snapshot.questions.filter((question) => {
      if (chapterFilter === 'all') {
        return true
      }
      if (chapterFilter === 'unassigned') {
        return !question.chapter_id
      }
      return question.chapter_id === chapterFilter
    })
  }, [chapterFilter, snapshot])

  useEffect(() => {
    if (visiblePoints.length === 0) {
      setSelectedPointId(null)
      return
    }
    setSelectedPointId((current) =>
      current && visiblePoints.some((point) => point.id === current)
        ? current
        : visiblePoints[0].id,
    )
  }, [visiblePoints])

  const selectedPoint =
    visiblePoints.find((point) => point.id === selectedPointId) ?? null

  async function retryDocument(document: DocumentSummary) {
    if (!online) {
      notify('error', '当前离线，重试解析需要连接后端')
      return
    }
    setRetryingDocumentId(document.id)
    try {
      await retryParse(document.id)
      notify('success', '已重新开始解析')
      await load(true)
    } catch (retryError) {
      notify('error', getErrorMessage(retryError))
    } finally {
      setRetryingDocumentId(null)
    }
  }

  if (status === 'loading') {
    return <div className="loading-block">正在加载课程知识库…</div>
  }

  if (status === 'error' || !snapshot) {
    return (
      <div className="subject-knowledge-page">
        <Link className="back-link" to="/subjects">
          ← 返回课程列表
        </Link>
        <div className="error-panel">
          <Notice kind="error">{error}</Notice>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void load()}
            disabled={!online}
          >
            {online ? '重新加载' : '等待网络恢复'}
          </button>
        </div>
      </div>
    )
  }

  const chapterLabel =
    chapterFilter === 'all'
      ? '全部章节'
      : chapterFilter === 'unassigned'
        ? '未归类'
        : (chapterName.get(chapterFilter) ?? '章节')

  return (
    <div className="subject-knowledge-page">
      <Link className="back-link" to="/subjects">
        ← 返回课程列表
      </Link>

      <header className="knowledge-hero">
        <div>
          <p className="eyebrow">Course knowledge base</p>
          <h1>{snapshot.subject.name}</h1>
          <p>{snapshot.subject.description || '这门课程还没有简介。'}</p>
          <div className="knowledge-hero-meta">
            <span>{snapshot.chapters.length} 个根章节</span>
            <span>{snapshot.documents.length} 份课件</span>
            <span>{snapshot.points.length} 个知识点</span>
            <span>{snapshot.questions.length} 道题</span>
          </div>
        </div>
        <div className="knowledge-hero-actions">
          <Link
            className="button button-primary"
            to={`/import?subject=${snapshot.subject.id}`}
          >
            导入课件
          </Link>
          <Link
            className="button button-ghost"
            to={`/subjects/${snapshot.subject.id}/documents`}
          >
            资料库
          </Link>
          <Link
            className="button button-ghost"
            to={`/subjects/${snapshot.subject.id}`}
          >
            章节管理
          </Link>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void load(true)}
            disabled={!online || refreshing}
          >
            {refreshing ? '刷新中…' : '刷新'}
          </button>
        </div>
      </header>

      {status === 'cache' && (
        <Notice kind="info">
          当前显示离线缓存（{formatDate(snapshot.savedAt)}）。上传、解析、AI
          分析需要连接 BioLearn 后端；联网后会自动刷新。
        </Notice>
      )}
      {!online && (
        <Notice kind="info">
          设备处于离线状态：可以浏览已缓存内容，但不能导入或发起解析。
        </Notice>
      )}

      <div className="knowledge-layout">
        <aside className="knowledge-chapters" aria-label="课程章节">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Chapters</p>
              <h2>章节导航</h2>
            </div>
          </div>
          <button
            type="button"
            className={`knowledge-chapter-row${chapterFilter === 'all' ? ' is-active' : ''}`}
            onClick={() => setChapterFilter('all')}
          >
            <span>全部章节</span>
            <small>{snapshot.points.length}</small>
          </button>
          {chapterEntries.map(({ node, depth }) => (
            <button
              type="button"
              key={node.id}
              className={`knowledge-chapter-row${chapterFilter === node.id ? ' is-active' : ''}`}
              style={{ paddingLeft: `${12 + depth * 14}px` }}
              onClick={() => setChapterFilter(node.id)}
            >
              <span>{node.name}</span>
              <small>{pointCounts.get(node.id) ?? 0}</small>
            </button>
          ))}
          {(unassignedPointCount > 0 || unassignedDocumentCount > 0) && (
            <button
              type="button"
              className={`knowledge-chapter-row${chapterFilter === 'unassigned' ? ' is-active' : ''}`}
              onClick={() => setChapterFilter('unassigned')}
            >
              <span>未归类</span>
              <small>{unassignedPointCount}</small>
            </button>
          )}
        </aside>

        <div className="knowledge-main">
          <section className="knowledge-section">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Materials</p>
                <h2>课件与解析状态</h2>
              </div>
              <span className="stat-chip">{chapterLabel}</span>
            </div>
            {visibleDocuments.length === 0 ? (
              <div className="empty-state empty-state-compact">
                <span className="empty-icon" aria-hidden="true">
                  📄
                </span>
                <h3>这个范围还没有课件</h3>
                <p>上传 PDF、DOCX、PPTX、TXT 或 Markdown，解析后即可在这里查看状态。</p>
                <Link
                  className="button button-primary button-small"
                  to={`/import?subject=${snapshot.subject.id}`}
                >
                  添加课件
                </Link>
              </div>
            ) : (
              <div className="knowledge-document-list">
                {visibleDocuments.map((document) => (
                  <article className="knowledge-document-row" key={document.id}>
                    <div className="knowledge-document-identity">
                      <span className="document-format">
                        {document.extension.replace('.', '').toUpperCase()}
                      </span>
                      <div>
                        <strong>{document.name}</strong>
                        <span>
                          {chapterName.get(document.chapter_id ?? '') ??
                            '未指定章节'}{' '}
                          · {formatBytes(document.size_bytes)} ·{' '}
                          {document.chunk_count} 个分块
                        </span>
                      </div>
                    </div>
                    <div className="knowledge-document-status">
                      <span
                        className={`status-badge document-status-${document.status}`}
                      >
                        {documentStatusLabels[document.status as DocumentStatus]}
                      </span>
                      {document.parse_error && (
                        <small className="knowledge-error-text">
                          {document.parse_error}
                        </small>
                      )}
                      <div className="knowledge-inline-actions">
                        {(document.status === 'failed' ||
                          document.status === 'needs_ocr') && (
                          <button
                            type="button"
                            className="text-button"
                            onClick={() => void retryDocument(document)}
                            disabled={!online || retryingDocumentId === document.id}
                          >
                            {retryingDocumentId === document.id
                              ? '重试中…'
                              : '重试解析'}
                          </button>
                        )}
                        <Link
                          className="text-link"
                          to={`/documents/${document.id}/review`}
                        >
                          查看知识点
                        </Link>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="knowledge-section">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Knowledge points</p>
                <h2>知识点</h2>
              </div>
              <span className="stat-chip">{visiblePoints.length} 条</span>
            </div>

            {snapshot.points.length === 0 ? (
              <div className="empty-state empty-state-compact">
                <span className="empty-icon" aria-hidden="true">
                  🧠
                </span>
                <h3>还没有知识点</h3>
                <p>
                  先上传并解析课件，然后在资料库启动 AI 知识点提取；系统会保留待审核状态，不会自动通过。
                </p>
                <Link
                  className="button button-primary button-small"
                  to={`/subjects/${snapshot.subject.id}/documents`}
                >
                  去资料库
                </Link>
              </div>
            ) : (
              <>
                <div className="knowledge-filter-bar">
                  <input
                    type="search"
                    value={pointQuery}
                    onChange={(event) => setPointQuery(event.target.value)}
                    placeholder="搜索知识点名称、解释或要点"
                    aria-label="搜索知识点"
                  />
                  <span className="form-hint">{visiblePoints.length} 条匹配</span>
                </div>
                <div className="knowledge-reader">
                  <div className="knowledge-point-list">
                    {visiblePoints.length === 0 ? (
                      <p className="form-hint">当前筛选没有匹配的知识点。</p>
                    ) : (
                      visiblePoints.map((point) => (
                        <button
                          type="button"
                          key={point.id}
                          className={`knowledge-point-row${selectedPointId === point.id ? ' is-selected' : ''}`}
                          onClick={() => setSelectedPointId(point.id)}
                        >
                          <span>
                            <strong>{point.name}</strong>
                            <small>
                              {chapterName.get(point.chapter_id ?? '') ??
                                '未指定章节'}{' '}
                              · {knowledgeTypeLabels[point.type]}
                            </small>
                          </span>
                          <span
                            className={`status-badge review-status-${point.review_status}`}
                          >
                            {reviewStatusLabels[point.review_status]}
                          </span>
                        </button>
                      ))
                    )}
                  </div>

                  <aside className="knowledge-point-detail" aria-live="polite">
                    {selectedPoint ? (
                      <>
                        <p className="eyebrow">Knowledge detail</p>
                        <h3>{selectedPoint.name}</h3>
                        <div className="knowledge-badges">
                          <span className="status-badge">
                            {knowledgeTypeLabels[selectedPoint.type]}
                          </span>
                          <span
                            className={`status-badge review-status-${selectedPoint.review_status}`}
                          >
                            {reviewStatusLabels[selectedPoint.review_status]}
                          </span>
                          {selectedPoint.origin === 'ai' && (
                            <span className="status-badge">AI 草稿</span>
                          )}
                        </div>
                        <p>{selectedPoint.explanation || '还没有解释。'}</p>
                        {selectedPoint.core_points.length > 0 && (
                          <div>
                            <h4>核心要点</h4>
                            <ul>
                              {selectedPoint.core_points.map((item, index) => (
                                <li key={`${item}-${index}`}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {selectedPoint.conditions && (
                          <div>
                            <h4>适用条件</h4>
                            <p>{selectedPoint.conditions}</p>
                          </div>
                        )}
                        {selectedPoint.source_quote && (
                          <blockquote>
                            {selectedPoint.source_quote}
                            <small>
                              {selectedPoint.source_page
                                ? `第 ${selectedPoint.source_page} 页`
                                : selectedPoint.source_slide
                                  ? `第 ${selectedPoint.source_slide} 张`
                                  : '来源位置未标注'}
                            </small>
                          </blockquote>
                        )}
                      </>
                    ) : (
                      <div className="panel-placeholder">
                        <p className="eyebrow">Knowledge detail</p>
                        <h3>选择一个知识点</h3>
                        <p>点击左侧条目查看解释、核心要点与来源。</p>
                      </div>
                    )}
                  </aside>
                </div>
              </>
            )}
          </section>

          <section className="knowledge-section">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Questions</p>
                <h2>题目</h2>
              </div>
              <span className="stat-chip">{visibleQuestions.length} 道</span>
            </div>
            {visibleQuestions.length === 0 ? (
              <div className="empty-state empty-state-compact">
                <span className="empty-icon" aria-hidden="true">
                  ✎
                </span>
                <h3>还没有题目</h3>
                <p>知识点通过审核后，可以在题库中出题；课程知识库只展示真实题目。</p>
                <Link className="button button-ghost button-small" to="/questions">
                  去题库
                </Link>
              </div>
            ) : (
              <div className="knowledge-question-list">
                {visibleQuestions.map((question) => (
                  <article className="knowledge-question-row" key={question.id}>
                    <div>
                      <strong>{question.stem}</strong>
                      <span>
                        {questionTypeLabels[question.type] ?? question.type} ·{' '}
                        {chapterName.get(question.chapter_id ?? '') ??
                          '未指定章节'}
                      </span>
                    </div>
                    <span className={`status-badge question-status-${question.status}`}>
                      {question.status === 'approved'
                        ? '已通过'
                        : question.status === 'pending'
                          ? '待审核'
                          : question.status === 'rejected'
                            ? '已拒绝'
                            : '需修改'}
                    </span>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
