import {
  useCallback,
  useEffect,
  useState,
  type CSSProperties,
} from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ChapterForm } from '../components/ChapterForm'
import { ChapterTree } from '../components/ChapterTree'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Modal } from '../components/Modal'
import { Notice } from '../components/Notice'
import { SubjectForm } from '../components/SubjectForm'
import {
  createChapter,
  deleteChapter,
  deleteSubject,
  getChapter,
  getErrorMessage,
  getSubject,
  listSubjectChapters,
  moveChapter,
  updateChapter,
  updateSubject,
  type ChapterDetail,
  type ChapterInput,
  type ChapterNode,
  type Subject,
  type SubjectInput,
} from '../lib/api'
import {
  collectSubtreeIds,
  countDescendants,
  findChapter,
} from '../lib/chapterTree'
import { useToast } from '../lib/useToast'

type PageStatus = 'loading' | 'ready' | 'error'
type DetailStatus = 'idle' | 'loading' | 'ready' | 'error'

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function collectExpandableIds(
  nodes: ChapterNode[],
  target = new Set<string>(),
): Set<string> {
  for (const node of nodes) {
    if (node.children.length > 0) {
      target.add(node.id)
      collectExpandableIds(node.children, target)
    }
  }
  return target
}

export function SubjectDetailPage() {
  const { subjectId = '' } = useParams<{ subjectId: string }>()
  const navigate = useNavigate()
  const { notify } = useToast()

  const [subject, setSubject] = useState<Subject | null>(null)
  const [tree, setTree] = useState<ChapterNode[]>([])
  const [status, setStatus] = useState<PageStatus>('loading')
  const [error, setError] = useState('')

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ChapterDetail | null>(null)
  const [detailStatus, setDetailStatus] = useState<DetailStatus>('idle')
  const [detailError, setDetailError] = useState('')
  const [detailVersion, setDetailVersion] = useState(0)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const [subjectFormOpen, setSubjectFormOpen] = useState(false)
  const [savingSubject, setSavingSubject] = useState(false)
  const [deletingSubject, setDeletingSubject] = useState(false)
  const [deleteSubjectBusy, setDeleteSubjectBusy] = useState(false)

  const [chapterForm, setChapterForm] = useState<
    | { mode: 'create'; parentId: string | null }
    | { mode: 'edit'; chapter: ChapterNode }
    | null
  >(null)
  const [savingChapter, setSavingChapter] = useState(false)
  const [deletingChapter, setDeletingChapter] = useState<ChapterNode | null>(
    null,
  )
  const [deleteChapterBusy, setDeleteChapterBusy] = useState(false)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setStatus('loading')
      setError('')
      try {
        const [nextSubject, nextTree] = await Promise.all([
          getSubject(subjectId, signal),
          listSubjectChapters(subjectId, signal),
        ])
        setSubject(nextSubject)
        setTree(nextTree)
        setStatus('ready')
        setExpanded(
          (previous) =>
            new Set([...previous, ...collectExpandableIds(nextTree)]),
        )
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

  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      setDetailStatus('idle')
      setDetailError('')
      return
    }

    const controller = new AbortController()
    setDetailStatus('loading')
    setDetailError('')
    getChapter(selectedId, controller.signal)
      .then((nextDetail) => {
        setDetail(nextDetail)
        setDetailStatus('ready')
      })
      .catch((chapterError: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setDetailStatus('error')
        setDetailError(getErrorMessage(chapterError))
      })

    return () => controller.abort()
  }, [selectedId, detailVersion])

  async function refreshTree() {
    const [nextSubject, nextTree] = await Promise.all([
      getSubject(subjectId),
      listSubjectChapters(subjectId),
    ])
    setSubject(nextSubject)
    setTree(nextTree)
    setStatus('ready')
    setExpanded(
      (previous) =>
        new Set([...previous, ...collectExpandableIds(nextTree)]),
    )
    return nextTree
  }

  async function handleSubjectSave(input: SubjectInput) {
    setSavingSubject(true)
    try {
      const updated = await updateSubject(subjectId, input)
      setSubject(updated)
      setSubjectFormOpen(false)
      notify('success', '学科信息已更新')
    } catch (saveError) {
      notify('error', getErrorMessage(saveError))
    } finally {
      setSavingSubject(false)
    }
  }

  async function handleSubjectDelete() {
    setDeleteSubjectBusy(true)
    try {
      await deleteSubject(subjectId, (subject?.chapter_count ?? 0) > 0)
      setDeletingSubject(false)
      notify('success', '学科已删除')
      navigate('/subjects')
    } catch (deleteError) {
      notify('error', getErrorMessage(deleteError))
    } finally {
      setDeleteSubjectBusy(false)
    }
  }

  async function handleChapterSave(input: ChapterInput) {
    if (!chapterForm) {
      return
    }

    setSavingChapter(true)
    try {
      if (chapterForm.mode === 'edit') {
        const updated = await updateChapter(chapterForm.chapter.id, input)
        setChapterForm(null)
        await refreshTree()
        setSelectedId(updated.id)
        setDetailVersion((version) => version + 1)
        notify('success', '章节已更新')
      } else {
        const created = await createChapter(subjectId, input)
        setChapterForm(null)
        await refreshTree()
        setSelectedId(created.id)
        notify('success', '章节已创建')
      }
    } catch (saveError) {
      notify('error', getErrorMessage(saveError))
    } finally {
      setSavingChapter(false)
    }
  }

  async function handleChapterDelete() {
    if (!deletingChapter) {
      return
    }

    const removedIds = collectSubtreeIds(deletingChapter)
    setDeleteChapterBusy(true)
    try {
      await deleteChapter(
        deletingChapter.id,
        countDescendants(deletingChapter) > 0,
      )
      setDeletingChapter(null)
      if (selectedId && removedIds.has(selectedId)) {
        setSelectedId(null)
        setDetail(null)
      }
      await refreshTree()
      notify('success', '章节已删除')
    } catch (deleteError) {
      notify('error', getErrorMessage(deleteError))
    } finally {
      setDeleteChapterBusy(false)
    }
  }

  async function handleMove(
    node: ChapterNode,
    direction: 'up' | 'down',
  ) {
    try {
      await moveChapter(node.id, direction)
      await refreshTree()
      if (selectedId) {
        setDetailVersion((version) => version + 1)
      }
      notify(
        'success',
        `「${node.name}」已${direction === 'up' ? '上移' : '下移'}`,
      )
    } catch (moveError) {
      notify('error', getErrorMessage(moveError))
    }
  }

  function toggleExpanded(chapterId: string) {
    setExpanded((previous) => {
      const next = new Set(previous)
      if (next.has(chapterId)) {
        next.delete(chapterId)
      } else {
        next.add(chapterId)
      }
      return next
    })
  }

  const selectedNode = selectedId ? findChapter(tree, selectedId) : null

  if (status === 'loading') {
    return <div className="loading-block">正在加载学科与章节…</div>
  }

  if (status === 'error' || !subject) {
    return (
      <div className="subject-detail-page">
        <Link className="back-link" to="/subjects">
          ← 返回学科列表
        </Link>
        <div className="error-panel">
          <Notice kind="error">无法加载学科：{error}</Notice>
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
    <div className="subject-detail-page">
      <Link className="back-link" to="/subjects">
        ← 返回学科列表
      </Link>

      <header
        className="subject-hero"
        style={
          {
            '--subject-color': subject.color ?? '#5fe3a6',
          } as CSSProperties
        }
      >
        <div className="subject-hero-main">
          <span className="subject-icon subject-icon-large" aria-hidden="true">
            {subject.icon ?? '📚'}
          </span>
          <div>
            <p className="eyebrow">Subject workspace</p>
            <h1>{subject.name}</h1>
            <p>{subject.description || '还没有简介。'}</p>
          </div>
        </div>
        <div className="subject-hero-actions">
          <Link
            className="button button-ghost"
            to={`/subjects/${subject.id}/documents`}
          >
            资料库
          </Link>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => setSubjectFormOpen(true)}
          >
            编辑学科
          </button>
          <button
            type="button"
            className="button button-danger-ghost"
            onClick={() => setDeletingSubject(true)}
          >
            删除学科
          </button>
        </div>
      </header>

      <div className="stats-row">
        <span className="stat-chip">
          <strong>{subject.chapter_count}</strong> 个章节
        </span>
        <span className="stat-chip">
          <strong>{tree.length}</strong> 个根章节
        </span>
        <span className="stat-chip stat-chip-muted">
          最近更新 {formatDate(subject.updated_at)}
        </span>
      </div>

      <div className="detail-grid">
        <section className="chapter-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Chapter tree</p>
              <h2>章节结构</h2>
            </div>
            <button
              type="button"
              className="button button-primary button-small"
              onClick={() =>
                setChapterForm({ mode: 'create', parentId: null })
              }
            >
              ＋ 新建根章节
            </button>
          </div>

          {tree.length === 0 ? (
            <div className="empty-state empty-state-compact">
              <span className="empty-icon" aria-hidden="true">
                🧫
              </span>
              <h3>还没有章节</h3>
              <p>从第一个根章节开始，之后可以继续添加子章节。</p>
              <button
                type="button"
                className="button button-primary button-small"
                onClick={() =>
                  setChapterForm({ mode: 'create', parentId: null })
                }
              >
                创建第一个章节
              </button>
            </div>
          ) : (
            <ChapterTree
              nodes={tree}
              selectedId={selectedId}
              expanded={expanded}
              onToggle={toggleExpanded}
              onSelect={setSelectedId}
              onAddChild={(node) =>
                setChapterForm({ mode: 'create', parentId: node.id })
              }
              onEdit={(node) =>
                setChapterForm({ mode: 'edit', chapter: node })
              }
              onDelete={setDeletingChapter}
              onMove={(node, direction) => void handleMove(node, direction)}
            />
          )}
        </section>

        <aside className="chapter-detail-panel" aria-live="polite">
          {detailStatus === 'idle' && (
            <div className="panel-placeholder">
              <p className="eyebrow">Chapter detail</p>
              <h2>选择一个章节</h2>
              <p>点击左侧章节名称，可以查看简介、所属学科与完整路径。</p>
            </div>
          )}

          {detailStatus === 'loading' && (
            <div className="loading-block">正在加载章节详情…</div>
          )}

          {detailStatus === 'error' && (
            <Notice kind="error">{detailError}</Notice>
          )}

          {detailStatus === 'ready' && detail && (
            <div className="chapter-detail-content">
              <p className="eyebrow">Chapter detail</p>
              <h2>{detail.name}</h2>
              <p className="detail-subject">
                所属学科：
                <Link to={`/subjects/${detail.subject.id}`}>
                  {detail.subject.icon ?? '📚'} {detail.subject.name}
                </Link>
              </p>

              {detail.path.length > 0 && (
                <nav className="breadcrumb" aria-label="章节路径">
                  {detail.path.map((item) => (
                    <span key={item.id}>{item.name} / </span>
                  ))}
                  <strong>{detail.name}</strong>
                </nav>
              )}

              <p className="detail-description">
                {detail.description || '还没有章节简介。'}
              </p>

              <dl className="meta-grid">
                <div>
                  <dt>父章节</dt>
                  <dd>{detail.parent?.name ?? '无（根章节）'}</dd>
                </div>
                <div>
                  <dt>后代章节</dt>
                  <dd>{detail.descendant_count} 个</dd>
                </div>
                <div>
                  <dt>排序值</dt>
                  <dd>{detail.sort_order}</dd>
                </div>
                <div>
                  <dt>更新时间</dt>
                  <dd>{formatDate(detail.updated_at)}</dd>
                </div>
              </dl>

              <div className="detail-actions">
                <button
                  type="button"
                  className="button button-small"
                  onClick={() => {
                    if (selectedNode) {
                      setChapterForm({
                        mode: 'edit',
                        chapter: selectedNode,
                      })
                    }
                  }}
                  disabled={!selectedNode}
                >
                  编辑章节
                </button>
                <button
                  type="button"
                  className="button button-small button-ghost"
                  onClick={() =>
                    setChapterForm({
                      mode: 'create',
                      parentId: detail.id,
                    })
                  }
                >
                  ＋ 添加子章节
                </button>
                <button
                  type="button"
                  className="button button-small button-danger-ghost"
                  onClick={() => {
                    if (selectedNode) {
                      setDeletingChapter(selectedNode)
                    }
                  }}
                  disabled={!selectedNode}
                >
                  删除章节
                </button>
              </div>
            </div>
          )}
        </aside>
      </div>

      <Modal
        open={subjectFormOpen}
        title="编辑学科"
        busy={savingSubject}
        onClose={() => {
          if (!savingSubject) {
            setSubjectFormOpen(false)
          }
        }}
      >
        <SubjectForm
          key={subject.id}
          initial={subject}
          submitting={savingSubject}
          onSubmit={(input) => void handleSubjectSave(input)}
          onCancel={() => {
            if (!savingSubject) {
              setSubjectFormOpen(false)
            }
          }}
        />
      </Modal>

      <Modal
        open={chapterForm !== null}
        title={chapterForm?.mode === 'edit' ? '编辑章节' : '新建章节'}
        busy={savingChapter}
        onClose={() => {
          if (!savingChapter) {
            setChapterForm(null)
          }
        }}
      >
        {chapterForm && (
          <ChapterForm
            key={
              chapterForm.mode === 'edit'
                ? chapterForm.chapter.id
                : `create-${chapterForm.parentId ?? 'root'}`
            }
            initial={chapterForm.mode === 'edit' ? chapterForm.chapter : null}
            tree={tree}
            defaultParentId={
              chapterForm.mode === 'create' ? chapterForm.parentId : null
            }
            submitting={savingChapter}
            onSubmit={(input) => void handleChapterSave(input)}
            onCancel={() => {
              if (!savingChapter) {
                setChapterForm(null)
              }
            }}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={deletingSubject}
        title="删除学科"
        description={
          subject.chapter_count > 0
            ? `「${subject.name}」下有 ${subject.chapter_count} 个章节。删除学科会一并删除全部章节，且无法恢复。`
            : `「${subject.name}」下没有章节。删除后无法恢复。`
        }
        confirmLabel="删除学科"
        busy={deleteSubjectBusy}
        acknowledgement={
          subject.chapter_count > 0
            ? `我了解将同时删除 ${subject.chapter_count} 个章节`
            : undefined
        }
        onConfirm={() => void handleSubjectDelete()}
        onCancel={() => {
          if (!deleteSubjectBusy) {
            setDeletingSubject(false)
          }
        }}
      />

      <ConfirmDialog
        open={deletingChapter !== null}
        title="删除章节"
        description={
          deletingChapter
            ? countDescendants(deletingChapter) > 0
              ? `「${deletingChapter.name}」下有 ${countDescendants(
                  deletingChapter,
                )} 个后代章节。删除会移除整棵子树，且无法恢复。`
              : `「${deletingChapter.name}」没有子章节。删除后无法恢复。`
            : ''
        }
        confirmLabel="删除章节"
        busy={deleteChapterBusy}
        acknowledgement={
          deletingChapter && countDescendants(deletingChapter) > 0
            ? `我了解将同时删除 ${countDescendants(
                deletingChapter,
              )} 个子章节`
            : undefined
        }
        onConfirm={() => void handleChapterDelete()}
        onCancel={() => {
          if (!deleteChapterBusy) {
            setDeletingChapter(null)
          }
        }}
      />
    </div>
  )
}
