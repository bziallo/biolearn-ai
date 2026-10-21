import { useCallback, useEffect, useMemo, useState } from 'react'

import { Notice } from '../components/Notice'
import { useToast } from '../lib/useToast'
import {
  getErrorMessage,
  getWrongQuestions,
  gradePracticeAnswer,
  listKnowledgePoints,
  listSubjectChapters,
  listSubjects,
  startPractice,
  submitPractice,
  type ChapterNode,
  type PracticeAnswerResult,
  type PracticeQuestion,
  type PracticeResult,
  type PracticeSession,
  type QuestionDifficulty,
  type QuestionType,
  type Subject,
  type WrongQuestion,
} from '../lib/api'

const TYPE_LABELS: Record<QuestionType, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  true_false: '判断题',
  short_answer: '简答题',
}

const DIFFICULTY_LABELS: Record<QuestionDifficulty, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

const ALL_TYPES: QuestionType[] = [
  'single_choice',
  'multiple_choice',
  'true_false',
  'short_answer',
]

type AnswerValue = {
  choices?: string[]
  boolean?: boolean
  text?: string
}

function resultAnswerText(answer: PracticeAnswerResult): string {
  const value = answer.question.answer
  if (answer.question.type === 'true_false') {
    return value.boolean === true ? '正确' : '错误'
  }
  if (answer.question.type === 'short_answer') {
    return typeof value.text === 'string' ? value.text : ''
  }
  const raw = value.choices
  return Array.isArray(raw) ? raw.join('、') : ''
}

function userAnswerText(answer: PracticeAnswerResult): string {
  if (answer.question.type === 'true_false') {
    return answer.user_answer.boolean === true ? '正确' : '错误'
  }
  if (answer.question.type === 'short_answer') {
    return typeof answer.user_answer.text === 'string'
      ? answer.user_answer.text
      : ''
  }
  const raw = answer.user_answer.choices
  return Array.isArray(raw) ? raw.join('、') : ''
}

function choiceKeys(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item).toUpperCase())
    : []
}

function ResultOptions({ answer }: { answer: PracticeAnswerResult }) {
  if (answer.question.type === 'short_answer') {
    return null
  }

  const correct = new Set(
    answer.question.type === 'true_false'
      ? []
      : choiceKeys(answer.question.answer.choices),
  )
  const chosen = new Set(
    answer.question.type === 'true_false'
      ? []
      : choiceKeys(answer.user_answer.choices),
  )
  const options =
    answer.question.type === 'true_false'
      ? [
          {
            key: 'true',
            text: '正确',
            correct: answer.question.answer.boolean === true,
            chosen: answer.user_answer.boolean === true,
          },
          {
            key: 'false',
            text: '错误',
            correct: answer.question.answer.boolean === false,
            chosen: answer.user_answer.boolean === false,
          },
        ]
      : answer.question.options.map((option) => ({
          key: option.key,
          text: option.text,
          correct: correct.has(option.key.toUpperCase()),
          chosen: chosen.has(option.key.toUpperCase()),
        }))

  return (
    <div className="practice-result-options">
      <p className="practice-result-options-title">选项</p>
      <ul>
        {options.map((option) => (
          <li
            key={option.key}
            className={[
              option.correct ? 'is-correct' : '',
              option.chosen ? 'is-chosen' : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <span className="practice-option-key">
              {answer.question.type === 'true_false' ? '' : `${option.key}.`}
            </span>
            <span>{option.text}</span>
            {option.correct && (
              <span className="practice-option-tag correct">正确答案</span>
            )}
            {option.chosen && (
              <span className="practice-option-tag chosen">你的选择</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function PracticePage() {
  const { notify } = useToast()
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [chapters, setChapters] = useState<ChapterNode[]>([])
  const [subjectId, setSubjectId] = useState('')
  const [chapterId, setChapterId] = useState('')
  const [types, setTypes] = useState<Set<QuestionType>>(new Set(ALL_TYPES))
  const [difficulty, setDifficulty] = useState<QuestionDifficulty | ''>('')
  const [count, setCount] = useState(10)
  const [wrongOnly, setWrongOnly] = useState(false)
  const [kpOptions, setKpOptions] = useState<Array<{ id: string; name: string }>>([])
  const [selectedKpIds, setSelectedKpIds] = useState<Set<string>>(new Set())
  const [session, setSession] = useState<PracticeSession | null>(null)
  const [result, setResult] = useState<PracticeResult | null>(null)
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({})
  const [wrongQuestions, setWrongQuestions] = useState<WrongQuestion[]>([])
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [manualScores, setManualScores] = useState<Record<string, number>>({})
  const [gradingId, setGradingId] = useState<string | null>(null)

  useEffect(() => {
    listSubjects()
      .then((next) => {
        setSubjects(next)
        setSubjectId((current) => current || next[0]?.id || '')
      })
      .catch((loadError: unknown) => setError(getErrorMessage(loadError)))
  }, [])

  useEffect(() => {
    if (!subjectId) {
      setChapters([])
      setWrongQuestions([])
      return
    }
    const controller = new AbortController()
    listSubjectChapters(subjectId, controller.signal)
      .then((next) => {
        setChapters(next)
        setChapterId('')
      })
      .catch((loadError: unknown) => {
        if (!controller.signal.aborted) setError(getErrorMessage(loadError))
      })
    getWrongQuestions(subjectId)
      .then(setWrongQuestions)
      .catch(() => setWrongQuestions([]))
    listKnowledgePoints({
      subject_id: subjectId,
      chapter_id: chapterId || undefined,
      review_status: 'approved',
      limit: 500,
    })
      .then((data) => {
        setKpOptions(
          data.points.map((point) => ({ id: point.id, name: point.name })),
        )
        setSelectedKpIds(new Set())
      })
      .catch(() => setKpOptions([]))
    return () => controller.abort()
  }, [subjectId, chapterId])

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

  const load = useCallback(async (onlyWrong = wrongOnly) => {
    if (!subjectId) {
      setError('请先选择学科')
      return
    }
    if (types.size === 0) {
      setError('至少选择一种题型')
      return
    }
    setLoading(true)
    setError('')
    try {
      const next = await startPractice({
        subject_id: subjectId,
        chapter_id: chapterId || null,
        knowledge_point_ids: Array.from(selectedKpIds),
        types: Array.from(types),
        difficulty: difficulty || null,
        count,
        wrong_only: onlyWrong,
      })
      setSession(next)
      setResult(null)
      setAnswers({})
    } catch (startError) {
      setError(getErrorMessage(startError))
    } finally {
      setLoading(false)
    }
  }, [subjectId, chapterId, types, difficulty, count, wrongOnly, selectedKpIds])

  function setChoice(question: PracticeQuestion, key: string, checked: boolean) {
    setAnswers((current) => {
      const previous = current[question.id]?.choices ?? []
      const nextChoices =
        question.type === 'single_choice'
          ? checked
            ? [key]
            : []
          : checked
            ? Array.from(new Set([...previous, key]))
            : previous.filter((item) => item !== key)
      return { ...current, [question.id]: { choices: nextChoices } }
    })
  }

  function setTrueAnswer(question: PracticeQuestion, value: boolean) {
    setAnswers((current) => ({
      ...current,
      [question.id]: { boolean: value },
    }))
  }

  function setTextAnswer(question: PracticeQuestion, text: string) {
    setAnswers((current) => ({
      ...current,
      [question.id]: { text },
    }))
  }

  async function submit() {
    if (!session) {
      return
    }
    const missing = session.questions.filter((question) => {
      const answer = answers[question.id]
      if (question.type === 'short_answer') {
        return !answer?.text?.trim()
      }
      if (question.type === 'true_false') {
        return typeof answer?.boolean !== 'boolean'
      }
      return !answer?.choices || answer.choices.length === 0
    })
    if (missing.length > 0) {
      setError(`还有 ${missing.length} 道题未作答`)
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const next = await submitPractice(session.id, {
        answers: session.questions.map((question) => ({
          question_id: question.id,
          user_answer: answers[question.id] as Record<string, unknown>,
        })),
      })
      setResult(next)
      setSession(next.session)
      if (subjectId) {
        getWrongQuestions(subjectId)
          .then(setWrongQuestions)
          .catch(() => undefined)
      }
    } catch (submitError) {
      setError(getErrorMessage(submitError))
    } finally {
      setSubmitting(false)
    }
  }

  async function grade(answer: PracticeAnswerResult) {
    setGradingId(answer.id)
    try {
      const next = await gradePracticeAnswer(
        answer.id,
        manualScores[answer.id] ?? 0.6,
      )
      setResult(next)
      setSession(next.session)
      notify('success', '简答题评分已保存')
    } catch (gradeError) {
      notify('error', getErrorMessage(gradeError))
    } finally {
      setGradingId(null)
    }
  }

  function reset() {
    setSession(null)
    setResult(null)
    setAnswers({})
    setWrongOnly(false)
  }

  return (
    <div className="practice-page">
      <header className="page-heading">
        <p className="eyebrow">Practice</p>
        <h1>智能练习</h1>
        <p className="lede">
          只从已通过审核的题库抽题。单选、多选和判断题自动判分；简答题由人工评分，模型不会直接给出绝对分数。
        </p>
      </header>

      {error && <Notice kind="error">{error}</Notice>}

      {!session && (
        <section className="panel practice-setup">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Session setup</p>
              <h2>开始一组练习</h2>
            </div>
          </div>
          <div className="practice-grid">
            <div className="field">
              <label>学科</label>
              <select value={subjectId} onChange={(event) => setSubjectId(event.target.value)}>
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>{subject.name}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>章节</label>
              <select value={chapterId} onChange={(event) => setChapterId(event.target.value)}>
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
              <label>题量</label>
              <input
                type="number"
                min={1}
                max={50}
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
              />
            </div>
            <div className="field">
              <label>难度</label>
              <select
                value={difficulty}
                onChange={(event) =>
                  setDifficulty(event.target.value as QuestionDifficulty | '')
                }
              >
                <option value="">全部难度</option>
                {Object.entries(DIFFICULTY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label>知识点范围（不选则使用该范围全部已审核知识点）</label>
            {kpOptions.length === 0 ? (
              <p className="form-hint">该范围暂时没有已审核知识点。</p>
            ) : (
              <div className="question-kp-picker">
                {kpOptions.map((point) => (
                  <label className="checkbox-field" key={point.id}>
                    <input
                      type="checkbox"
                      checked={selectedKpIds.has(point.id)}
                      onChange={(event) => {
                        const next = new Set(selectedKpIds)
                        if (event.target.checked) next.add(point.id)
                        else next.delete(point.id)
                        setSelectedKpIds(next)
                      }}
                    />
                    <span>{point.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <div className="field">
            <label>题型</label>
            <div className="question-type-checks">
              {ALL_TYPES.map((item) => (
                <label className="checkbox-field" key={item}>
                  <input
                    type="checkbox"
                    checked={types.has(item)}
                    onChange={(event) => {
                      const next = new Set(types)
                      if (event.target.checked) next.add(item)
                      else next.delete(item)
                      setTypes(next)
                    }}
                  />
                  <span>{TYPE_LABELS[item]}</span>
                </label>
              ))}
            </div>
          </div>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={wrongOnly}
              onChange={(event) => setWrongOnly(event.target.checked)}
              disabled={wrongQuestions.length === 0}
            />
            <span>只练错题（{wrongQuestions.length} 道）</span>
          </label>
          <div className="form-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={() => void load()}
              disabled={loading || !subjectId || types.size === 0}
            >
              {loading ? '抽题中…' : '开始练习'}
            </button>
            <button type="button" className="button button-ghost" onClick={() => {
              setWrongOnly(true)
              void load(true)
            }} disabled={loading || wrongQuestions.length === 0}>
              错题再练
            </button>
          </div>
        </section>
      )}

      {session && !result && (
        <section className="practice-run panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">In progress</p>
              <h2>练习中 · 共 {session.total_questions} 题</h2>
            </div>
            <button type="button" className="button button-ghost" onClick={reset}>
              退出练习
            </button>
          </div>
          {session.questions.map((question, index) => {
            const answer = answers[question.id] ?? {}
            return (
              <article className="practice-question" key={question.id}>
                <div className="practice-question-head">
                  <span>第 {index + 1} 题</span>
                  <span>{TYPE_LABELS[question.type]}</span>
                  <span>{DIFFICULTY_LABELS[question.difficulty]}</span>
                </div>
                <h3>{question.stem}</h3>
                {question.type === 'single_choice' || question.type === 'multiple_choice' ? (
                  <div className="practice-options">
                    {question.options.map((option) => (
                      <label className="practice-option" key={option.key}>
                        <input
                          type={question.type === 'single_choice' ? 'radio' : 'checkbox'}
                          name={`practice-${question.id}`}
                          checked={(answer.choices ?? []).includes(option.key)}
                          onChange={(event) =>
                            setChoice(question, option.key, event.target.checked)
                          }
                        />
                        <span><strong>{option.key}.</strong> {option.text}</span>
                      </label>
                    ))}
                  </div>
                ) : question.type === 'true_false' ? (
                  <div className="practice-options">
                    <label className="practice-option">
                      <input
                        type="radio"
                        name={`practice-${question.id}`}
                        checked={answer.boolean === true}
                        onChange={() => setTrueAnswer(question, true)}
                      />
                      <span>正确</span>
                    </label>
                    <label className="practice-option">
                      <input
                        type="radio"
                        name={`practice-${question.id}`}
                        checked={answer.boolean === false}
                        onChange={() => setTrueAnswer(question, false)}
                      />
                      <span>错误</span>
                    </label>
                  </div>
                ) : (
                  <textarea
                    rows={4}
                    className="practice-short-answer"
                    placeholder="写下你的答案，提交后由人工评分"
                    value={answer.text ?? ''}
                    onChange={(event) => setTextAnswer(question, event.target.value)}
                  />
                )}
                <p className="form-hint">
                  关联知识点：
                  {question.knowledge_points.map((point) => point.name).join('、') || '未记录'}
                </p>
              </article>
            )
          })}
          <div className="form-actions">
            <button type="button" className="button button-primary" onClick={() => void submit()} disabled={submitting}>
              {submitting ? '提交中…' : '提交答案'}
            </button>
          </div>
        </section>
      )}

      {result && (
        <section className="practice-result">
          <div className="practice-score panel">
            <div>
              <p className="eyebrow">Result</p>
              <h2>
                {result.session.score === null
                  ? '等待人工评分'
                  : `得分 ${result.session.score}`}
              </h2>
              <p>
                正确 {result.session.correct_count}/{result.session.total_questions}
                {result.session.pending_manual_count > 0
                  ? ` · 待人工评分 ${result.session.pending_manual_count}`
                  : ''}
              </p>
            </div>
            <button type="button" className="button button-primary" onClick={reset}>
              再练一组
            </button>
          </div>
          {result.answers.map((answer, index) => (
            <article className="practice-result-row panel" key={answer.id}>
              <div className="practice-result-head">
                <span>第 {index + 1} 题</span>
                <span
                  className={
                    answer.is_correct === true
                      ? 'answer-correct'
                      : answer.is_correct === false
                        ? 'answer-wrong'
                        : 'answer-pending'
                  }
                >
                  {answer.is_correct === true
                    ? '正确'
                    : answer.is_correct === false
                      ? '错误'
                      : '待评分'}
                </span>
              </div>
              <h3>{answer.question.stem}</h3>
              <ResultOptions answer={answer} />
              <div className="practice-result-answer">
                <p><strong>你的答案：</strong>{userAnswerText(answer) || '（空）'}</p>
                <p><strong>标准答案：</strong>{resultAnswerText(answer)}</p>
                {answer.question.type === 'short_answer' && answer.graded_by === 'pending' && (
                  <div className="manual-grade">
                    <label>
                      人工评分（0–1）
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.1}
                        value={manualScores[answer.id] ?? 0.6}
                        onChange={(event) =>
                          setManualScores((current) => ({
                            ...current,
                            [answer.id]: Number(event.target.value),
                          }))
                        }
                      />
                    </label>
                    <button
                      type="button"
                      className="button button-small"
                      onClick={() => void grade(answer)}
                      disabled={gradingId === answer.id}
                    >
                      {gradingId === answer.id ? '保存中…' : '保存评分'}
                    </button>
                  </div>
                )}
                <p className="practice-explanation"><strong>解析：</strong>{answer.question.explanation}</p>
                {answer.feedback && (
                  <p className="form-hint"><strong>评语：</strong>{answer.feedback}</p>
                )}
                <p className="form-hint">
                  关联知识点：
                  {answer.question.knowledge_points.map((point) => point.name).join('、') || '未记录'}
                </p>
              </div>
            </article>
          ))}
        </section>
      )}

      {wrongQuestions.length > 0 && !session && (
        <section className="panel wrong-panel">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Wrong questions</p>
              <h2>错题本</h2>
              <p className="form-hint">错误次数来自已保存的答题记录，仅展示已通过审核的题目。</p>
            </div>
          </div>
          <div className="wrong-list">
            {wrongQuestions.slice(0, 20).map((item) => (
              <div className="wrong-row" key={item.question.id}>
                <strong>{item.question.stem}</strong>
                <span>错 {item.wrong_count} 次 · {item.question.chapter_name ?? '未指定章节'}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
