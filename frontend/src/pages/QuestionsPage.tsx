import { useCallback, useEffect, useMemo, useState } from 'react'

import { ConfirmDialog } from '../components/ConfirmDialog'
import { Modal } from '../components/Modal'
import { Notice } from '../components/Notice'
import { useToast } from '../lib/useToast'
import {
  bulkReviewQuestions,
  cancelQuestionGeneration,
  generateQuestions,
  getErrorMessage,
  getQuestionGenerationJob,
  listKnowledgePoints,
  listQuestions,
  listSubjectChapters,
  listSubjects,
  regenerateQuestion,
  retryQuestionGeneration,
  reviewQuestion,
  updateQuestion,
  type ChapterNode,
  type Question,
  type QuestionDifficulty,
  type QuestionGenerationJob,
  type QuestionOption,
  type QuestionStatus,
  type QuestionType,
  type Subject,
} from '../lib/api'

type PageStatus = 'loading' | 'ready' | 'error'

const TYPE_LABELS: Record<QuestionType, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  true_false: '判断题',
  short_answer: '简答题',
}

const STATUS_LABELS: Record<QuestionStatus, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  needs_revision: '需修改',
}

const DIFFICULTY_LABELS: Record<QuestionDifficulty, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

const TYPE_OPTIONS = Object.keys(TYPE_LABELS) as QuestionType[]
const DIFFICULTY_OPTIONS = Object.keys(DIFFICULTY_LABELS) as QuestionDifficulty[]
const STATUS_OPTIONS = Object.keys(STATUS_LABELS) as QuestionStatus[]

const ALL_TYPES: QuestionType[] = [
  'single_choice',
  'multiple_choice',
  'true_false',
  'short_answer',
]

function choiceKeys(question: Question): string[] {
  const raw = question.answer.choices
  return Array.isArray(raw) ? raw.map(String) : []
}

function booleanAnswer(question: Question): boolean {
  return question.answer.boolean === true
}

function shortAnswer(question: Question): string {
  return typeof question.answer.text === 'string' ? question.answer.text : ''
}

function answerText(question: Question): string {
  if (question.type === 'true_false') {
    return booleanAnswer(question) ? '正确' : '错误'
  }
  if (question.type === 'short_answer') {
    return shortAnswer(question) || '（无参考答案）'
  }
  return choiceKeys(question).join('、') || '（无答案）'
}

function statusBadge(status: QuestionStatus) {
  return <span className={`status-badge question-status-${status}`}>{STATUS_LABELS[status]}</span>
}

function OptionEditor({
  options,
  correctKeys,
  type,
  onChange,
  onCorrectChange,
}: {
  options: QuestionOption[]
  correctKeys: string[]
  type: QuestionType
  onChange: (options: QuestionOption[]) => void
  onCorrectChange: (keys: string[]) => void
}) {
  function toggleCorrect(key: string) {
    if (type === 'single_choice') {
      onCorrectChange([key])
      return
    }
    onCorrectChange(
      correctKeys.includes(key)
        ? correctKeys.filter((item) => item !== key)
        : [...correctKeys, key],
    )
  }

  return (
    <div className="question-option-editor">
      {options.map((option, index) => (
        <div className="question-option-row" key={option.key}>
          <label className="question-correct-toggle">
            <input
              type={type === 'single_choice' ? 'radio' : 'checkbox'}
              name="question-correct-answer"
              checked={correctKeys.includes(option.key)}
              onChange={() => toggleCorrect(option.key)}
            />
            <span>{option.key}</span>
          </label>
          <input
            aria-label={`选项 ${option.key}`}
            value={option.text}
            onChange={(event) => {
              const next = [...options]
              next[index] = { ...option, text: event.target.value }
              onChange(next)
            }}
          />
          <button
            type="button"
            className="text-button"
            disabled={options.length <= 2}
            onClick={() => {
              onChange(options.filter((item) => item.key !== option.key))
              onCorrectChange(correctKeys.filter((key) => key !== option.key))
            }}
          >
            删除
          </button>
        </div>
      ))}
      <button
        type="button"
        className="button button-small button-ghost"
        disabled={options.length >= 8}
        onClick={() => {
          const used = new Set(options.map((option) => option.key))
          let key = ''
          for (let index = 0; index < 26; index += 1) {
            const candidate = String.fromCharCode(65 + index)
            if (!used.has(candidate)) {
              key = candidate
              break
            }
          }
          if (key) {
            onChange([...options, { key, text: '' }])
          }
        }}
      >
        添加选项
      </button>
    </div>
  )
}

export function QuestionsPage() {
  const { notify } = useToast()
  const [status, setStatus] = useState<PageStatus>('loading')
  const [error, setError] = useState('')
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [chapters, setChapters] = useState<ChapterNode[]>([])
  const [genChapters, setGenChapters] = useState<ChapterNode[]>([])
  const [questions, setQuestions] = useState<Question[]>([])
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    approved: 0,
    rejected: 0,
    needs_revision: 0,
  })
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Question | null>(null)
  const [editor, setEditor] = useState<Question | null>(null)
  const [saving, setSaving] = useState(false)
  const [bulkStatus, setBulkStatus] = useState<QuestionStatus | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [genOpen, setGenOpen] = useState(false)
  const [genSubject, setGenSubject] = useState('')
  const [genChapter, setGenChapter] = useState('')
  const [genKps, setGenKps] = useState<Array<{ id: string; name: string }>>([])
  const [genKpIds, setGenKpIds] = useState<Set<string>>(new Set())
  const [genKpQuery, setGenKpQuery] = useState('')
  const [genTypes, setGenTypes] = useState<Set<QuestionType>>(new Set(ALL_TYPES))
  const [genCount, setGenCount] = useState(5)
  const [genDifficulty, setGenDifficulty] = useState<QuestionDifficulty | ''>('')
  const [genBusy, setGenBusy] = useState(false)
  const [genJob, setGenJob] = useState<QuestionGenerationJob | null>(null)

  const [subjectId, setSubjectId] = useState('')
  const [chapterId, setChapterId] = useState('')
  const [kpFilter, setKpFilter] = useState('')
  const [filterKps, setFilterKps] = useState<Array<{ id: string; name: string }>>([])
  const [typeFilter, setTypeFilter] = useState<QuestionType | ''>('')
  const [difficultyFilter, setDifficultyFilter] = useState<QuestionDifficulty | ''>('')
  const [statusFilter, setStatusFilter] = useState<QuestionStatus | ''>('')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')

  const loadSubjects = useCallback(async () => {
    try {
      const next = await listSubjects()
      setSubjects(next)
      setGenSubject((current) => current || next[0]?.id || '')
    } catch (loadError) {
      setError(getErrorMessage(loadError))
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    void loadSubjects()
  }, [loadSubjects])

  useEffect(() => {
    if (!subjectId) {
      setChapters([])
      setChapterId('')
      return
    }
    const controller = new AbortController()
    listSubjectChapters(subjectId, controller.signal)
      .then((next) => {
        setChapters(next)
        setChapterId('')
      })
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) {
          setError(getErrorMessage(loadError))
        }
      })
    return () => controller.abort()
  }, [subjectId])

  useEffect(() => {
    if (!subjectId) {
      setFilterKps([])
      setKpFilter('')
      return
    }
    const controller = new AbortController()
    listKnowledgePoints({
      subject_id: subjectId,
      chapter_id: chapterId || undefined,
      review_status: 'approved',
      limit: 500,
    })
      .then((data) => {
        setFilterKps(
          data.points.map((point) => ({ id: point.id, name: point.name })),
        )
        setKpFilter('')
      })
      .catch(() => setFilterKps([]))
    return () => controller.abort()
  }, [subjectId, chapterId])

  useEffect(() => {
    if (!genSubject) {
      setGenChapters([])
      return
    }
    const controller = new AbortController()
    listSubjectChapters(genSubject, controller.signal)
      .then((next) => {
        setGenChapters(next)
        setGenChapter('')
      })
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) {
          setError(getErrorMessage(loadError))
        }
      })
    return () => controller.abort()
  }, [genSubject])

  useEffect(() => {
    if (!genSubject) {
      setGenKps([])
      return
    }
    const controller = new AbortController()
    listKnowledgePoints({
      subject_id: genSubject,
      chapter_id: genChapter || undefined,
      review_status: 'approved',
      limit: 500,
    })
      .then((data) => {
        setGenKps(data.points.map((point) => ({ id: point.id, name: point.name })))
        setGenKpIds(new Set())
        setGenKpQuery('')
      })
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) {
          setError(getErrorMessage(loadError))
        }
      })
    return () => controller.abort()
  }, [genSubject, genChapter])

  const refresh = useCallback(async () => {
    setStatus('loading')
    setError('')
    try {
      const data = await listQuestions({
        subject_id: subjectId || undefined,
        chapter_id: chapterId || undefined,
        knowledge_point_id: kpFilter || undefined,
        type: typeFilter || undefined,
        difficulty: difficultyFilter || undefined,
        status: statusFilter || undefined,
        q: query || undefined,
        limit: 50,
        offset,
      })
      setQuestions(data.questions)
      setStats(data.stats)
      setTotal(data.total)
      setChecked(new Set())
      setStatus('ready')
    } catch (loadError) {
      setError(getErrorMessage(loadError))
      setStatus('error')
    }
  }, [subjectId, chapterId, kpFilter, typeFilter, difficultyFilter, statusFilter, query, offset])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (!genJob || !['queued', 'running', 'cancelling'].includes(genJob.status)) {
      return
    }
    const timer = globalThis.setTimeout(() => {
      getQuestionGenerationJob(genJob.id)
        .then((next) => {
          setGenJob(next)
          if (next.status === 'completed') {
            notify('success', `已生成 ${next.generated_count} 道题，等待审核`)
            setStatusFilter('pending')
            setOffset(0)
            void refresh()
          } else if (next.status === 'failed') {
            notify('error', next.error || '出题失败')
          }
        })
        .catch((pollError: unknown) => {
          notify('error', getErrorMessage(pollError))
        })
    }, 1200)
    return () => globalThis.clearTimeout(timer)
  }, [genJob, notify, refresh])

  const chapterOptions = useMemo(() => {
    const rows: Array<{ node: ChapterNode; depth: number }> = []
    const walk = (nodes: ChapterNode[], depth: number) => {
      for (const node of nodes) {
        rows.push({ node, depth })
        walk(node.children ?? [], depth + 1)
      }
    }
    walk(chapters, 0)
    return rows
  }, [chapters])

  const genChapterOptions = useMemo(() => {
    const rows: Array<{ node: ChapterNode; depth: number }> = []
    const walk = (nodes: ChapterNode[], depth: number) => {
      for (const node of nodes) {
        rows.push({ node, depth })
        walk(node.children ?? [], depth + 1)
      }
    }
    walk(genChapters, 0)
    return rows
  }, [genChapters])

  const visibleGenKps = useMemo(() => {
    const keyword = genKpQuery.trim().toLowerCase()
    if (!keyword) {
      return genKps
    }
    return genKps.filter((point) =>
      point.name.toLowerCase().includes(keyword),
    )
  }, [genKps, genKpQuery])

  async function updateOne(question: Question, nextStatus: QuestionStatus) {
    try {
      const updated = await reviewQuestion(question.id, nextStatus)
      setSelected((current) => (current?.id === updated.id ? updated : current))
      notify('success', `题目已标记为${STATUS_LABELS[nextStatus]}`)
      await refresh()
    } catch (reviewError) {
      notify('error', getErrorMessage(reviewError))
    }
  }

  async function runBulk() {
    if (!bulkStatus || checked.size === 0) {
      return
    }
    setBulkBusy(true)
    try {
      const result = await bulkReviewQuestions(Array.from(checked), bulkStatus)
      setBulkStatus(null)
      setChecked(new Set())
      notify('success', `已批量更新 ${result.updated} 道题`)
      await refresh()
    } catch (bulkError) {
      notify('error', getErrorMessage(bulkError))
    } finally {
      setBulkBusy(false)
    }
  }

  async function regenerate(question: Question) {
    try {
      const job = await regenerateQuestion(question.id)
      setGenJob(job)
      setGenOpen(true)
      setSelected(null)
      notify('success', '已提交重新生成任务')
    } catch (regenerateError) {
      notify('error', getErrorMessage(regenerateError))
    }
  }

  async function startGeneration() {
    if (!genSubject) {
      setError('请先选择学科')
      return
    }
    if (genTypes.size === 0) {
      setError('至少选择一种题型')
      return
    }
    setGenBusy(true)
    setError('')
    try {
      const job = await generateQuestions({
        subject_id: genSubject,
        chapter_id: genChapter || null,
        knowledge_point_ids: Array.from(genKpIds),
        types: Array.from(genTypes),
        count: genCount,
        difficulty: genDifficulty || null,
      })
      setGenJob(job)
      notify('success', '出题任务已开始')
    } catch (generateError) {
      setError(getErrorMessage(generateError))
    } finally {
      setGenBusy(false)
    }
  }

  async function cancelGeneration() {
    if (!genJob) {
      return
    }
    try {
      setGenJob(await cancelQuestionGeneration(genJob.id))
      notify('success', '已请求停止出题')
    } catch (cancelError) {
      notify('error', getErrorMessage(cancelError))
    }
  }

  async function retryGeneration() {
    if (!genJob) {
      return
    }
    try {
      setGenJob(await retryQuestionGeneration(genJob.id))
      notify('success', '已重新开始出题')
    } catch (retryError) {
      notify('error', getErrorMessage(retryError))
    }
  }

  async function saveEditor(input: {
    stem: string
    explanation: string
    type: QuestionType
    difficulty: QuestionDifficulty
    options: QuestionOption[]
    answer: Record<string, unknown>
  }) {
    if (!editor) {
      return
    }
    setSaving(true)
    try {
      const updated = await updateQuestion(editor.id, input)
      setEditor(null)
      setSelected(updated)
      notify(
        'success',
        updated.status === 'pending'
          ? '题目已保存，修改后需要重新审核'
          : '题目已保存',
      )
      await refresh()
    } catch (saveError) {
      notify('error', getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="questions-page">
      <header className="page-heading">
        <p className="eyebrow">Question bank</p>
        <h1>题库管理</h1>
        <p className="lede">
          从已审核知识点生成题目，逐题人工核验后再进入正式练习。AI 只负责起草，不替代事实审核。
        </p>
      </header>

      {error && <Notice kind="error">{error}</Notice>}

      <div className="question-actions">
        <button
          type="button"
          className="button button-primary"
          onClick={() => setGenOpen((open) => !open)}
        >
          {genOpen ? '收起 AI 出题' : 'AI 出题'}
        </button>
        <button
          type="button"
          className="button button-ghost"
          onClick={() => {
            setStatusFilter('pending')
            setOffset(0)
          }}
        >
          只看待审核
        </button>
      </div>

      {genOpen && (
        <section className="question-generator panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">AI generation</p>
              <h2>从已审核知识点出题</h2>
              <p className="form-hint">
                只使用已通过审核的知识点；生成结果进入待审核，不会直接进入练习。
              </p>
            </div>
          </div>
          <div className="question-generator-grid">
            <div className="field">
              <label>学科</label>
              <select value={genSubject} onChange={(event) => setGenSubject(event.target.value)}>
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>章节</label>
              <select value={genChapter} onChange={(event) => setGenChapter(event.target.value)}>
                <option value="">全部章节</option>
                {genChapterOptions.map(({ node, depth }) => (
                  <option key={node.id} value={node.id}>
                    {'— '.repeat(depth)}
                    {node.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>题量</label>
              <input
                type="number"
                min={1}
                max={20}
                value={genCount}
                onChange={(event) => setGenCount(Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>难度</label>
              <select
                value={genDifficulty}
                onChange={(event) =>
                  setGenDifficulty(event.target.value as QuestionDifficulty | '')
                }
              >
                <option value="">由模型判断</option>
                {DIFFICULTY_OPTIONS.map((item) => (
                  <option key={item} value={item}>
                    {DIFFICULTY_LABELS[item]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label>题型</label>
            <div className="question-type-checks">
              {TYPE_OPTIONS.map((item) => (
                <label className="checkbox-field" key={item}>
                  <input
                    type="checkbox"
                    checked={genTypes.has(item)}
                    onChange={(event) => {
                      const next = new Set(genTypes)
                      if (event.target.checked) {
                        next.add(item)
                      } else {
                        next.delete(item)
                      }
                      setGenTypes(next)
                    }}
                  />
                  <span>{TYPE_LABELS[item]}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="field">
            <label>知识点（不选则使用该范围全部已审核知识点）</label>
            {genKps.length === 0 ? (
              <p className="form-hint">该范围暂时没有已通过审核的知识点。</p>
            ) : (
              <>
                <div className="question-kp-picker-toolbar">
                  <input
                    type="search"
                    aria-label="搜索可选知识点"
                    placeholder="搜索知识点"
                    value={genKpQuery}
                    onChange={(event) => setGenKpQuery(event.target.value)}
                  />
                  <button
                    type="button"
                    className="text-button"
                    disabled={visibleGenKps.length === 0}
                    onClick={() =>
                      setGenKpIds((current) => {
                        const next = new Set(current)
                        visibleGenKps.forEach((point) => next.add(point.id))
                        return next
                      })
                    }
                  >
                    全选{genKpQuery.trim() ? '筛选结果' : '当前范围'}
                  </button>
                  <button
                    type="button"
                    className="text-button"
                    disabled={genKpIds.size === 0}
                    onClick={() => setGenKpIds(new Set())}
                  >
                    清空
                  </button>
                  <button
                    type="button"
                    className="text-button"
                    disabled={genKps.length === 0}
                    onClick={() =>
                      setGenKpIds(
                        new Set(
                          genKps
                            .filter((point) => !genKpIds.has(point.id))
                            .map((point) => point.id),
                        ),
                      )
                    }
                  >
                    反选
                  </button>
                  <span className="question-kp-count">
                    已选 {genKpIds.size}/{genKps.length}
                  </span>
                </div>
                {visibleGenKps.length === 0 ? (
                  <p className="form-hint">没有匹配的知识点。</p>
                ) : (
                  <div className="question-kp-picker">
                    {visibleGenKps.map((point) => (
                      <label className="checkbox-field" key={point.id}>
                        <input
                          type="checkbox"
                          checked={genKpIds.has(point.id)}
                          onChange={(event) => {
                            const next = new Set(genKpIds)
                            if (event.target.checked) {
                              next.add(point.id)
                            } else {
                              next.delete(point.id)
                            }
                            setGenKpIds(next)
                          }}
                        />
                        <span>{point.name}</span>
                      </label>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
          <div className="form-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={() => void startGeneration()}
              disabled={genBusy || !genSubject || genTypes.size === 0}
            >
              {genBusy ? '提交中…' : '开始生成'}
            </button>
            {genJob && ['queued', 'running', 'cancelling'].includes(genJob.status) && (
              <button type="button" className="button button-danger" onClick={() => void cancelGeneration()}>
                停止出题
              </button>
            )}
            {genJob?.status === 'failed' && (
              <button type="button" className="button button-ghost" onClick={() => void retryGeneration()}>
                重试
              </button>
            )}
          </div>
          {genJob && (
            <div className="question-generation-status">
              <strong>{genJob.stage}</strong>
              <span>
                已生成 {genJob.generated_count} · 跳过重复 {genJob.skipped_count}
              </span>
              {genJob.error && <span className="form-error">{genJob.error}</span>}
            </div>
          )}
        </section>
      )}

      <section className="question-stats">
        <div><span>全部</span><strong>{stats.total}</strong></div>
        <div><span>待审核</span><strong>{stats.pending}</strong></div>
        <div><span>已通过</span><strong>{stats.approved}</strong></div>
        <div><span>需修改</span><strong>{stats.needs_revision}</strong></div>
        <div><span>已拒绝</span><strong>{stats.rejected}</strong></div>
      </section>

      <section className="panel question-filter-panel">
        <div className="question-filters">
          <div className="field">
            <label htmlFor="question-filter-subject">学科</label>
            <select
              id="question-filter-subject"
              value={subjectId}
              onChange={(event) => {
                setSubjectId(event.target.value)
                setOffset(0)
              }}
            >
              <option value="">全部学科</option>
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>{subject.name}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="question-filter-chapter">章节</label>
            <select
              id="question-filter-chapter"
              value={chapterId}
              onChange={(event) => {
                setChapterId(event.target.value)
                setOffset(0)
              }}
              disabled={!subjectId}
            >
              <option value="">全部章节</option>
              {chapterOptions.map(({ node, depth }) => (
                <option key={node.id} value={node.id}>
                  {'— '.repeat(depth)}
                  {node.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="question-filter-kp">知识点</label>
            <select
              id="question-filter-kp"
              value={kpFilter}
              onChange={(event) => {
                setKpFilter(event.target.value)
                setOffset(0)
              }}
              disabled={!subjectId}
            >
              <option value="">全部知识点</option>
              {filterKps.map((point) => (
                <option key={point.id} value={point.id}>{point.name}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="question-filter-type">题型</label>
            <select
              id="question-filter-type"
              value={typeFilter}
              onChange={(event) => {
                setTypeFilter(event.target.value as QuestionType | '')
                setOffset(0)
              }}
            >
              <option value="">全部题型</option>
              {TYPE_OPTIONS.map((item) => (
                <option key={item} value={item}>{TYPE_LABELS[item]}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="question-filter-difficulty">难度</label>
            <select
              id="question-filter-difficulty"
              value={difficultyFilter}
              onChange={(event) => {
                setDifficultyFilter(event.target.value as QuestionDifficulty | '')
                setOffset(0)
              }}
            >
              <option value="">全部难度</option>
              {DIFFICULTY_OPTIONS.map((item) => (
                <option key={item} value={item}>{DIFFICULTY_LABELS[item]}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="question-filter-status">状态</label>
            <select
              id="question-filter-status"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value as QuestionStatus | '')
                setOffset(0)
              }}
            >
              <option value="">全部状态</option>
              {STATUS_OPTIONS.map((item) => (
                <option key={item} value={item}>{STATUS_LABELS[item]}</option>
              ))}
            </select>
          </div>
          <div className="field question-search-field">
            <label htmlFor="question-search">搜索题干/解析</label>
            <div className="question-search-row">
              <input
                id="question-search"
                value={q}
                onChange={(event) => setQ(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    setQuery(q)
                    setOffset(0)
                  }
                }}
                placeholder="输入关键词"
              />
              <button
                type="button"
                className="button button-small"
                onClick={() => {
                  setQuery(q)
                  setOffset(0)
                }}
              >
                搜索
              </button>
            </div>
          </div>
        </div>
      </section>

      {checked.size > 0 && (
        <div className="bulk-bar">
          <span>{checked.size} 道已选</span>
          <button type="button" className="mini-button" onClick={() => setBulkStatus('approved')}>
            批量通过
          </button>
          <button type="button" className="mini-button" onClick={() => setBulkStatus('needs_revision')}>
            批量需修改
          </button>
          <button type="button" className="mini-button" onClick={() => setBulkStatus('rejected')}>
            批量拒绝
          </button>
          <button type="button" className="text-button" onClick={() => setChecked(new Set())}>
            清空
          </button>
        </div>
      )}

      {status === 'loading' && <div className="loading-block">正在加载题库…</div>}
      {status === 'ready' && questions.length === 0 && (
        <div className="empty-panel">
          <h2>没有匹配的题目</h2>
          <p>调整筛选条件，或从已审核知识点生成一组待审核题目。</p>
        </div>
      )}
      {questions.length > 0 && (
        <section className="question-list">
          <div className="question-list-head">
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={questions.every((item) => checked.has(item.id))}
                onChange={(event) =>
                  setChecked(
                    event.target.checked
                      ? new Set(questions.map((item) => item.id))
                      : new Set(),
                  )
                }
              />
              <span>全选本页</span>
            </label>
            <span>共 {total} 道</span>
          </div>
          {questions.map((question) => (
            <article className="question-row" key={question.id}>
              <input
                type="checkbox"
                aria-label={`选择题目 ${question.id}`}
                checked={checked.has(question.id)}
                onChange={(event) => {
                  const next = new Set(checked)
                  if (event.target.checked) {
                    next.add(question.id)
                  } else {
                    next.delete(question.id)
                  }
                  setChecked(next)
                }}
              />
              <button
                type="button"
                className="question-row-main"
                onClick={() => setSelected(question)}
              >
                <span className="question-row-meta">
                  <span>{TYPE_LABELS[question.type]}</span>
                  <span>{DIFFICULTY_LABELS[question.difficulty]}</span>
                  <span>{question.chapter_name ?? '未指定章节'}</span>
                  {question.duplicate_of_id && <span className="question-duplicate">疑似重复</span>}
                </span>
                <strong>{question.stem}</strong>
                <span className="question-row-answer">答案：{answerText(question)}</span>
              </button>
              <div className="question-row-status">
                {statusBadge(question.status)}
                <button type="button" className="text-button" onClick={() => setSelected(question)}>
                  查看
                </button>
              </div>
            </article>
          ))}
        </section>
      )}
      {total > 50 && (
        <div className="pagination">
          <button
            type="button"
            className="button button-small"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            上一页
          </button>
          <span>
            {offset + 1}–{Math.min(offset + 50, total)} / {total}
          </span>
          <button
            type="button"
            className="button button-small"
            disabled={offset + 50 >= total}
            onClick={() => setOffset(offset + 50)}
          >
            下一页
          </button>
        </div>
      )}

      <Modal
        open={Boolean(selected)}
        title={selected ? TYPE_LABELS[selected.type] : '题目详情'}
        onClose={() => setSelected(null)}
      >
        {selected && (
          <div className="question-detail">
            <div className="question-detail-head">
              {statusBadge(selected.status)}
              <span>{DIFFICULTY_LABELS[selected.difficulty]}</span>
              <span>{selected.subject_name}</span>
              {selected.duplicate_of_id && (
                <span className="question-duplicate">疑似重复：{selected.duplicate_reason}</span>
              )}
            </div>
            <h3>{selected.stem}</h3>
            {selected.options.length > 0 && (
              <ol className="question-detail-options">
                {selected.options.map((option) => (
                  <li
                    key={option.key}
                    className={choiceKeys(selected).includes(option.key) ? 'is-correct' : ''}
                  >
                    <strong>{option.key}.</strong> {option.text}
                  </li>
                ))}
              </ol>
            )}
            <div className="question-detail-block">
              <dt>标准答案</dt>
              <dd>{answerText(selected)}</dd>
            </div>
            <div className="question-detail-block">
              <dt>解析</dt>
              <dd>{selected.explanation}</dd>
            </div>
            <div className="question-detail-block">
              <dt>来源资料</dt>
              <dd>
                {selected.source_document_name ?? '未记录'}
                {selected.source_locator ? ` · ${selected.source_locator}` : ''}
                {selected.ai_model ? ` · AI 模型 ${selected.ai_model}` : ''}
              </dd>
            </div>
            <div className="question-detail-block">
              <dt>关联知识点 / 来源</dt>
              <dd>
                {selected.knowledge_points.length === 0
                  ? '未关联'
                  : selected.knowledge_points.map((point) => (
                      <div key={point.id} className="question-source-row">
                        <strong>{point.name}</strong>
                        <span>
                          {point.source_locator ||
                            (point.source_page ? `第 ${point.source_page} 页` : '') ||
                            (point.source_slide ? `第 ${point.source_slide} 张幻灯片` : '来源未记录')}
                          {point.review_status !== 'approved' ? ' · 知识点未通过' : ''}
                        </span>
                      </div>
                    ))}
              </dd>
            </div>
            {selected.review_note && (
              <p className="form-hint">审核备注：{selected.review_note}</p>
            )}
            <div className="form-actions question-detail-actions">
              <button type="button" className="button button-primary" onClick={() => void updateOne(selected, 'approved')}>
                通过
              </button>
              <button type="button" className="button button-ghost" onClick={() => void updateOne(selected, 'needs_revision')}>
                需修改
              </button>
              <button type="button" className="button button-danger" onClick={() => void updateOne(selected, 'rejected')}>
                拒绝
              </button>
              <button type="button" className="button button-ghost" onClick={() => setEditor(selected)}>
                编辑
              </button>
              <button type="button" className="button button-ghost" onClick={() => void regenerate(selected)}>
                重新生成
              </button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={Boolean(editor)}
        title="编辑题目"
        busy={saving}
        onClose={() => {
          if (!saving) setEditor(null)
        }}
      >
        {editor && (
          <QuestionEditForm
            question={editor}
            busy={saving}
            onCancel={() => setEditor(null)}
            onSave={(input) => void saveEditor(input)}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(bulkStatus)}
        title="批量审核题目"
        description={`确认将选中的 ${checked.size} 道题标记为${bulkStatus ? STATUS_LABELS[bulkStatus] : ''}？该操作会立即影响练习抽题范围。`}
        confirmLabel="确认更新"
        busy={bulkBusy}
        onConfirm={() => void runBulk()}
        onCancel={() => setBulkStatus(null)}
      />
    </div>
  )
}

function QuestionEditForm({
  question,
  busy,
  onCancel,
  onSave,
}: {
  question: Question
  busy: boolean
  onCancel: () => void
  onSave: (input: {
    stem: string
    explanation: string
    type: QuestionType
    difficulty: QuestionDifficulty
    options: QuestionOption[]
    answer: Record<string, unknown>
  }) => void
}) {
  const [type, setType] = useState<QuestionType>(question.type)
  const [stem, setStem] = useState(question.stem)
  const [explanation, setExplanation] = useState(question.explanation)
  const [difficulty, setDifficulty] = useState<QuestionDifficulty>(question.difficulty)
  const [options, setOptions] = useState<QuestionOption[]>(
    question.options.length
      ? question.options
      : [
          { key: 'A', text: '' },
          { key: 'B', text: '' },
        ],
  )
  const [correctKeys, setCorrectKeys] = useState<string[]>(choiceKeys(question))
  const [trueAnswer, setTrueAnswer] = useState(booleanAnswer(question))
  const [shortText, setShortText] = useState(shortAnswer(question))
  const [error, setError] = useState('')

  function changeType(next: QuestionType) {
    setType(next)
    if (next === 'single_choice' || next === 'multiple_choice') {
      setOptions((current) =>
        current.length >= 2 ? current : [
          { key: 'A', text: '' },
          { key: 'B', text: '' },
        ],
      )
      setCorrectKeys([])
    } else if (next === 'true_false') {
      setOptions([])
      setCorrectKeys([])
      setTrueAnswer(true)
    } else {
      setOptions([])
      setCorrectKeys([])
      setShortText('')
    }
  }

  function submit() {
    if (stem.trim().length < 5) {
      setError('题干至少 5 个字符')
      return
    }
    if (explanation.trim().length < 5) {
      setError('解析至少 5 个字符')
      return
    }
    if (type === 'single_choice' && correctKeys.length !== 1) {
      setError('单选题必须选择一个正确答案')
      return
    }
    if (type === 'multiple_choice' && correctKeys.length === 0) {
      setError('多选题至少选择一个正确答案')
      return
    }
    if (
      (type === 'single_choice' || type === 'multiple_choice') &&
      options.some((option) => !option.text.trim())
    ) {
      setError('选项内容不能为空')
      return
    }
    if (type === 'short_answer' && !shortText.trim()) {
      setError('简答题需要参考答案')
      return
    }
    setError('')
    onSave({
      stem: stem.trim(),
      explanation: explanation.trim(),
      type,
      difficulty,
      options,
      answer:
        type === 'true_false'
          ? { boolean: trueAnswer }
          : type === 'short_answer'
            ? { text: shortText.trim() }
            : { choices: correctKeys },
    })
  }

  return (
    <div className="question-edit-form">
      {error && <Notice kind="error">{error}</Notice>}
      <div className="field">
        <label>题型</label>
        <select value={type} onChange={(event) => changeType(event.target.value as QuestionType)}>
          {TYPE_OPTIONS.map((item) => (
            <option key={item} value={item}>{TYPE_LABELS[item]}</option>
          ))}
        </select>
      </div>
      <div className="field">
        <label>题干</label>
        <textarea
          rows={4}
          value={stem}
          onChange={(event) => setStem(event.target.value)}
        />
      </div>
      {(type === 'single_choice' || type === 'multiple_choice') && (
        <OptionEditor
          options={options}
          correctKeys={correctKeys}
          type={type}
          onChange={setOptions}
          onCorrectChange={setCorrectKeys}
        />
      )}
      {type === 'true_false' && (
        <div className="field">
          <label>正确答案</label>
          <select value={trueAnswer ? 'true' : 'false'} onChange={(event) => setTrueAnswer(event.target.value === 'true')}>
            <option value="true">正确</option>
            <option value="false">错误</option>
          </select>
        </div>
      )}
      {type === 'short_answer' && (
        <div className="field">
          <label>参考答案</label>
          <textarea
            rows={3}
            value={shortText}
            onChange={(event) => setShortText(event.target.value)}
          />
        </div>
      )}
      <div className="field">
        <label>解析</label>
        <textarea
          rows={4}
          value={explanation}
          onChange={(event) => setExplanation(event.target.value)}
        />
      </div>
      <div className="field">
        <label>难度</label>
        <select
          value={difficulty}
          onChange={(event) => setDifficulty(event.target.value as QuestionDifficulty)}
        >
          {DIFFICULTY_OPTIONS.map((item) => (
            <option key={item} value={item}>{DIFFICULTY_LABELS[item]}</option>
          ))}
        </select>
      </div>
      <p className="form-hint">
        保存已通过题目会重新进入待审核；题目需要重新人工确认后才能用于正式练习。
      </p>
      <div className="form-actions">
        <button type="button" className="button button-ghost" onClick={onCancel} disabled={busy}>
          取消
        </button>
        <button type="button" className="button button-primary" onClick={submit} disabled={busy}>
          {busy ? '保存中…' : '保存题目'}
        </button>
      </div>
    </div>
  )
}
