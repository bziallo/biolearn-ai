import {
  useCallback,
  useEffect,
  useState,
  type CSSProperties,
} from 'react'
import { Link } from 'react-router-dom'

import { ConfirmDialog } from '../components/ConfirmDialog'
import { Modal } from '../components/Modal'
import { Notice } from '../components/Notice'
import { SubjectForm } from '../components/SubjectForm'
import {
  createSubject,
  deleteSubject,
  getErrorMessage,
  listSubjects,
  updateSubject,
  type Subject,
  type SubjectInput,
} from '../lib/api'
import { useToast } from '../lib/useToast'

type PageStatus = 'loading' | 'ready' | 'error'

export function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [status, setStatus] = useState<PageStatus>('loading')
  const [error, setError] = useState('')
  const [formMode, setFormMode] = useState<'create' | 'edit' | null>(null)
  const [editing, setEditing] = useState<Subject | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<Subject | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const { notify } = useToast()

  const load = useCallback(async (signal?: AbortSignal) => {
    setStatus('loading')
    setError('')
    try {
      const data = await listSubjects(signal)
      setSubjects(data)
      setStatus('ready')
    } catch (loadError) {
      if (signal?.aborted) {
        return
      }
      setStatus('error')
      setError(getErrorMessage(loadError))
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  async function refreshSubjects() {
    const data = await listSubjects()
    setSubjects(data)
    setStatus('ready')
  }

  function openCreate() {
    setEditing(null)
    setFormMode('create')
  }

  function openEdit(subject: Subject) {
    setEditing(subject)
    setFormMode('edit')
  }

  function closeForm() {
    if (saving) {
      return
    }
    setFormMode(null)
    setEditing(null)
  }

  async function handleSave(input: SubjectInput) {
    const isEdit = formMode === 'edit' && editing !== null
    setSaving(true)
    try {
      if (isEdit && editing) {
        await updateSubject(editing.id, input)
      } else {
        await createSubject(input)
      }
      setFormMode(null)
      setEditing(null)
      await refreshSubjects()
      notify('success', isEdit ? '学科信息已更新' : '学科已创建')
    } catch (saveError) {
      notify('error', getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleting) {
      return
    }

    setDeleteBusy(true)
    try {
      await deleteSubject(deleting.id, deleting.chapter_count > 0)
      setDeleting(null)
      await refreshSubjects()
      notify('success', '学科已删除')
    } catch (deleteError) {
      notify('error', getErrorMessage(deleteError))
    } finally {
      setDeleteBusy(false)
    }
  }

  const totalChapters = subjects.reduce(
    (total, subject) => total + subject.chapter_count,
    0,
  )

  return (
    <div className="subjects-page">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Academic structure</p>
          <h1>学科与章节</h1>
          <p className="lede">
            先把知识地图搭起来。学科是顶层容器，章节可以继续向下拆分，
            后续的资料、知识点和题目都会挂在这棵树上。
          </p>
        </div>
        <button
          type="button"
          className="button button-primary"
          onClick={openCreate}
        >
          ＋ 新建学科
        </button>
      </section>

      <div className="stats-row" aria-label="学科统计">
        <span className="stat-chip">
          <strong>{subjects.length}</strong> 个学科
        </span>
        <span className="stat-chip">
          <strong>{totalChapters}</strong> 个章节
        </span>
        <span className="stat-chip stat-chip-muted">数据来自本地 SQLite</span>
      </div>

      {status === 'error' && (
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
      )}

      {status === 'loading' && (
        <div className="loading-block">正在从后端加载学科…</div>
      )}

      {status === 'ready' && subjects.length === 0 && (
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">
            🧬
          </span>
          <h2>还没有学科</h2>
          <p>
            数据库目前是空的。创建第一个学科，之后就可以在详情页里搭建章节树。
          </p>
          <button
            type="button"
            className="button button-primary"
            onClick={openCreate}
          >
            创建第一个学科
          </button>
        </div>
      )}

      {status === 'ready' && subjects.length > 0 && (
        <div className="subject-grid">
          {subjects.map((subject) => (
            <article
              className="subject-card"
              key={subject.id}
              style={
                {
                  '--subject-color': subject.color ?? '#5fe3a6',
                } as CSSProperties
              }
            >
              <div className="subject-card-head">
                <span className="subject-icon" aria-hidden="true">
                  {subject.icon ?? '📚'}
                </span>
                <span className="subject-count">
                  {subject.chapter_count} 章
                </span>
              </div>
              <h2>
                <Link to={`/subjects/${subject.id}`}>{subject.name}</Link>
              </h2>
              <p>{subject.description || '还没有简介。'}</p>
              <div className="subject-actions">
                <Link
                  className="button button-small"
                  to={`/subjects/${subject.id}`}
                >
                  查看章节
                </Link>
                <button
                  type="button"
                  className="button button-small button-ghost"
                  onClick={() => openEdit(subject)}
                >
                  编辑
                </button>
                <button
                  type="button"
                  className="button button-small button-danger-ghost"
                  onClick={() => setDeleting(subject)}
                >
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <p className="page-note">
        初始学科由数据库迁移插入，不是前端写死的列表；重命名、删除或新增都会直接写入 SQLite。
      </p>

      <Modal
        open={formMode !== null}
        title={formMode === 'edit' ? '编辑学科' : '新建学科'}
        busy={saving}
        onClose={closeForm}
      >
        <SubjectForm
          key={editing?.id ?? 'create'}
          initial={editing}
          submitting={saving}
          onSubmit={(input) => void handleSave(input)}
          onCancel={closeForm}
        />
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        title="删除学科"
        description={
          deleting
            ? deleting.chapter_count > 0
              ? `「${deleting.name}」下有 ${deleting.chapter_count} 个章节。删除学科会一并删除全部章节，且无法恢复。`
              : `「${deleting.name}」下没有章节。删除后无法恢复。`
            : ''
        }
        confirmLabel="删除学科"
        busy={deleteBusy}
        acknowledgement={
          deleting && deleting.chapter_count > 0
            ? `我了解将同时删除 ${deleting.chapter_count} 个章节`
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
