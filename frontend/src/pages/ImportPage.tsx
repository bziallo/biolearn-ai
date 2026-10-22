import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type DragEvent,
} from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Notice } from '../components/Notice'
import {
  confirmImport,
  createExternalImport,
  createImport,
  getErrorMessage,
  getExternalTemplate,
  getImport,
  getImportPreferences,
  listImports,
  listSubjectChapters,
  listSubjects,
  retryImport,
  updateImportPreferences,
  type ChapterNode,
  type ExternalTemplate,
  type ImportJob,
  type ImportMode,
  type ImportPreferences,
  type Subject,
  type UncertainPolicy,
} from '../lib/api'
import { flattenTree } from '../lib/chapterTree'
import { formatBytes } from '../lib/format'
import { isOfflineError, useOnlineStatus } from '../lib/offline/network'
import { useToast } from '../lib/useToast'

const RUNNING_STATUSES = new Set([
  'queued',
  'parsing',
  'detecting',
  'archiving',
  'analyzing',
])

const MODE_LABELS: Record<ImportMode, string> = {
  preset: '归入预设章节',
  auto_create: '自动识别并建章',
  smart_archive: '智能归档',
}

const MODE_HINTS: Record<ImportMode, string> = {
  preset: '使用你设置的默认学科/章节；本次选择优先。',
  auto_create: '从 PPT 目录、编号标题和文档标题生成章节树，自动创建缺失章节。',
  smart_archive: '优先复用已有同名章节；相似或冲突时按设置确认，避免重复建章。',
}

const ACTION_LABELS: Record<string, string> = {
  create: '将创建',
  reuse: '复用已有',
  uncertain: '需确认',
}

const PREVIEW_SOURCE_LABELS: Record<string, string> = {
  toc: '目录页',
  slide_titles: '编号标题',
  headings: '文档标题结构',
  filename: '文件名/资料标题',
  external_json: '外部 AI JSON',
}

type PageStatus = 'loading' | 'ready' | 'error'
type SourceType = 'courseware' | 'external_json'

export function ImportPage() {
  const { notify } = useToast()
  const online = useOnlineStatus()
  const [searchParams] = useSearchParams()
  const requestedSubject = searchParams.get('subject')

  const [status, setStatus] = useState<PageStatus>('loading')
  const [error, setError] = useState('')
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [preferences, setPreferences] = useState<ImportPreferences | null>(null)
  const [chapters, setChapters] = useState<ChapterNode[]>([])
  const [sourceType, setSourceType] = useState<SourceType>('courseware')
  const [duplicateStrategy, setDuplicateStrategy] = useState<
    'skip' | 'update_pending'
  >('skip')
  const [externalChapterId, setExternalChapterId] = useState('')
  const [externalTemplate, setExternalTemplate] =
    useState<ExternalTemplate | null>(null)
  const [templateOpen, setTemplateOpen] = useState(false)
  const [templateLoading, setTemplateLoading] = useState(false)
  const [recentImports, setRecentImports] = useState<ImportJob[]>([])

  const [subjectId, setSubjectId] = useState('')
  const [chapterId, setChapterId] = useState('')
  const [mode, setMode] = useState<ImportMode>('preset')
  const [autoAnalyze, setAutoAnalyze] = useState(true)
  const [requirePreview, setRequirePreview] = useState(true)
  const [uncertainPolicy, setUncertainPolicy] =
    useState<UncertainPolicy>('confirm')

  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [job, setJob] = useState<ImportJob | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [savingPreferences, setSavingPreferences] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const jobId = job?.id
  const jobStatus = job?.status

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setStatus('loading')
      setError('')
      try {
        const [nextSubjects, nextPreferences] = await Promise.all([
          listSubjects(signal),
          getImportPreferences(signal),
        ])
        setSubjects(nextSubjects)
        setPreferences(nextPreferences)
        try {
          const nextImports = await listImports(signal)
          const imports = Array.isArray(nextImports) ? nextImports : []
          setRecentImports(imports)
          if (
            imports[0] &&
            ['queued', 'parsing', 'detecting', 'archiving', 'analyzing'].includes(
              imports[0].status,
            )
          ) {
            setJob(imports[0])
          }
        } catch {
          if (!signal?.aborted) {
            setRecentImports([])
          }
        }
        const initialSubject =
          requestedSubject &&
          nextSubjects.some((subject) => subject.id === requestedSubject)
            ? requestedSubject
            : nextPreferences.default_subject_id ?? ''
        setSubjectId(initialSubject)
        if (initialSubject === nextPreferences.default_subject_id) {
          setChapterId(nextPreferences.default_chapter_id ?? '')
        }
        setMode(nextPreferences.default_mode)
        setAutoAnalyze(nextPreferences.auto_analyze)
        setRequirePreview(nextPreferences.require_preview)
        setUncertainPolicy(nextPreferences.uncertain_policy)
        setStatus('ready')
      } catch (loadError) {
        if (signal?.aborted) {
          return
        }
        setStatus('error')
        setError(getErrorMessage(loadError))
      }
    },
    [requestedSubject],
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  useEffect(() => {
    if (!subjectId) {
      setChapters([])
      return
    }
    const controller = new AbortController()
    listSubjectChapters(subjectId, controller.signal)
      .then(setChapters)
      .catch((chaptersError: unknown) => {
        if (!controller.signal.aborted) {
          notify('error', getErrorMessage(chaptersError))
        }
      })
    return () => controller.abort()
  }, [subjectId, notify])

  useEffect(() => {
    if (!templateOpen || externalTemplate) {
      return
    }
    const controller = new AbortController()
    setTemplateLoading(true)
    getExternalTemplate(controller.signal)
      .then(setExternalTemplate)
      .catch((templateError: unknown) => {
        if (!controller.signal.aborted) {
          notify('error', getErrorMessage(templateError))
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setTemplateLoading(false)
        }
      })
    return () => controller.abort()
  }, [templateOpen, externalTemplate, notify])

  useEffect(() => {
    if (!jobId || !jobStatus || !RUNNING_STATUSES.has(jobStatus)) {
      return
    }
    const timer = globalThis.setInterval(() => {
      getImport(jobId)
        .then((nextJob) => {
          setJob(nextJob)
          if (!RUNNING_STATUSES.has(nextJob.status)) {
            if (nextJob.status === 'completed') {
              notify('success', nextJob.stage || '导入完成')
            } else if (nextJob.status === 'awaiting_confirmation') {
              notify('info', '请确认归档结构')
            } else if (nextJob.status === 'failed') {
              notify('error', nextJob.error || '导入失败')
            }
          }
        })
        .catch((pollError: unknown) => {
          notify('error', getErrorMessage(pollError))
        })
    }, 1500)
    return () => globalThis.clearInterval(timer)
  }, [jobId, jobStatus, notify])

  function selectFile(nextFile: File | null) {
    setError('')
    if (!nextFile) {
      setFile(null)
      return
    }
    const allowed = sourceType === 'external_json'
      ? /\.json$/i
      : /\.(pdf|docx|pptx|txt|md|markdown)$/i
    if (!allowed.test(nextFile.name)) {
      setFile(null)
      setError(
        sourceType === 'external_json'
          ? '请选择 .json 文件。'
          : '不支持该格式；当前支持 PDF、DOCX、PPTX、TXT、MD。旧版 .ppt 请先另存为 .pptx。',
      )
      return
    }
    if (nextFile.size > 25 * 1024 * 1024) {
      setFile(null)
      setError(`文件超过 25 MB 限制（当前 ${formatBytes(nextFile.size)}）。`)
      return
    }
    setFile(nextFile)
    setJob(null)
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    const nextFile = event.dataTransfer.files?.[0] ?? null
    if (nextFile) {
      selectFile(nextFile)
    }
  }

  async function submit() {
    if (!file) {
      setError('请选择要导入的文件')
      return
    }
    if (!subjectId) {
      setError('请选择学科，或先在下方设置默认学科')
      return
    }
    if (!online) {
      setError('当前离线，无法上传。文件已保留；恢复网络后重新点击“开始导入”。')
      return
    }
    setBusy(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('subject_id', subjectId)
      let created: ImportJob
      if (sourceType === 'external_json') {
        formData.append('duplicate_strategy', duplicateStrategy)
        created = await createExternalImport(formData)
        notify('success', '外部 AI JSON 已校验，请确认归档预览')
      } else {
        formData.append('mode', mode)
        formData.append('auto_analyze', autoAnalyze ? 'true' : 'false')
        formData.append('require_preview', requirePreview ? 'true' : 'false')
        formData.append('uncertain_policy', uncertainPolicy)
        if (mode === 'preset' && chapterId) {
          formData.append('chapter_id', chapterId)
        }
        created = await createImport(formData)
        notify('success', '文件已上传，正在解析和识别结构')
      }
      setJob(created)
      setRecentImports((current) => [
        created,
        ...(Array.isArray(current) ? current : []).filter(
          (item) => item.id !== created.id,
        ),
      ].slice(0, 10))
    } catch (uploadError) {
      setError(
        isOfflineError(uploadError)
          ? '网络中断或后端不可达，文件仍保留在本次页面中。恢复连接后重试；若提示重复，请先到资料库确认，避免重复记录。'
          : getErrorMessage(uploadError),
      )
    } finally {
      setBusy(false)
    }
  }

  async function confirm(acceptSuggestions: boolean) {
    if (!job) {
      return
    }
    setConfirming(true)
    try {
      const useExternalChapter =
        job.source_type === 'external_json' && Boolean(externalChapterId)
      const next = await confirmImport(job.id, {
        accept_suggestions: useExternalChapter ? false : acceptSuggestions,
        subject_id: subjectId || null,
        chapter_id: useExternalChapter
          ? externalChapterId
          : acceptSuggestions
            ? null
            : chapterId || null,
        create_missing: true,
        auto_analyze: autoAnalyze,
      })
      setJob(next)
      notify('success', '归档结果已保存')
    } catch (confirmError) {
      notify('error', getErrorMessage(confirmError))
    } finally {
      setConfirming(false)
    }
  }

  async function retry() {
    if (!job) {
      return
    }
    try {
      const next = await retryImport(job.id)
      setJob(next)
    } catch (retryError) {
      notify('error', getErrorMessage(retryError))
    }
  }

  async function savePreferences() {
    setSavingPreferences(true)
    try {
      const defaultChapterId =
        chapterId ||
        (preferences?.default_subject_id === subjectId
          ? preferences?.default_chapter_id
          : null) ||
        null
      const next = await updateImportPreferences({
        default_subject_id: subjectId || null,
        default_chapter_id: defaultChapterId,
        default_mode: mode,
        auto_analyze: autoAnalyze,
        require_preview: requirePreview,
        uncertain_policy: uncertainPolicy,
      })
      setPreferences(next)
      notify('success', '默认导入设置已保存')
    } catch (saveError) {
      notify('error', getErrorMessage(saveError))
    } finally {
      setSavingPreferences(false)
    }
  }

  async function copyText(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text)
      notify('success', `${label}已复制`)
    } catch {
      notify('error', '复制失败，请手动选择文本')
    }
  }

  if (status === 'loading') {
    return <div className="loading-block">正在加载导入设置…</div>
  }

  if (status === 'error') {
    return (
      <div className="import-page">
        <div className="error-panel">
          <Notice kind="error">无法加载导入设置：{error}</Notice>
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

  const suggestion = job?.suggestion ?? null
  const result = job?.result ?? null
  const jobRunning = Boolean(job && RUNNING_STATUSES.has(job.status))
  const terminal = job && !jobRunning
  const currentSubject = subjects.find((subject) => subject.id === subjectId)
  const chapterOptions = flattenTree(chapters)

  return (
    <div className="import-page">
      <header className="page-heading">
        <p className="eyebrow">Smart import</p>
        <h1>智能资料导入</h1>
        <p className="lede">
          上传 PPT、PDF、DOCX、TXT 或 Markdown。系统会解析结构、建议学科与章节，
          按你选择的模式归档，并可自动开始 AI 知识点分析。
        </p>
      </header>

      <div className="import-source-tabs" role="tablist" aria-label="导入方式">
        <button
          type="button"
          role="tab"
          aria-selected={sourceType === 'courseware'}
          className={sourceType === 'courseware' ? 'is-active' : ''}
          onClick={() => {
            setSourceType('courseware')
            setFile(null)
            setError('')
          }}
        >
          上传原始课件
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={sourceType === 'external_json'}
          className={sourceType === 'external_json' ? 'is-active' : ''}
          onClick={() => {
            setSourceType('external_json')
            setFile(null)
            setError('')
          }}
        >
          导入 AI 预处理 JSON
        </button>
        <button
          type="button"
          className="import-template-toggle"
          onClick={() => setTemplateOpen((open) => !open)}
        >
          {templateOpen ? '收起导入模板' : '查看导入模板'}
        </button>
      </div>

      {templateOpen && (
        <section className="import-template-panel">
          <div className="import-template-head">
            <div>
              <p className="eyebrow">External AI template</p>
              <h2>外部 AI 知识点 JSON 模板</h2>
              <p className="form-hint">
                把下面的提示词和 JSON Schema 一起交给外部 AI。当前仅接受
                schema_version 1.0；导入后会先预览，不会直接写入正式知识点。
              </p>
            </div>
            {externalTemplate && (
              <div className="import-template-actions">
                <button
                  type="button"
                  className="button button-small button-primary"
                  onClick={() =>
                    void copyText(externalTemplate.prompt, '提示词')
                  }
                >
                  复制提示词
                </button>
                <button
                  type="button"
                  className="button button-small button-ghost"
                  onClick={() =>
                    void copyText(
                      JSON.stringify(externalTemplate.example, null, 2),
                      '示例 JSON',
                    )
                  }
                >
                  复制示例 JSON
                </button>
              </div>
            )}
          </div>
          {templateLoading && (
            <div className="loading-block">正在加载模板…</div>
          )}
          {externalTemplate && (
            <>
              <pre className="import-template-prompt">
                {externalTemplate.prompt}
              </pre>
              <details className="import-template-schema">
                <summary>查看 JSON Schema（版本 {externalTemplate.schema_version}）</summary>
                <pre>
                  {JSON.stringify(externalTemplate.json_schema, null, 2)}
                </pre>
              </details>
            </>
          )}
        </section>
      )}

      {!online && (
        <Notice kind="info">
          当前离线：只能查看已缓存内容。课件上传、解析和 AI 分析需要连接 BioLearn 后端。
        </Notice>
      )}

      {!subjectId && (
        <Notice kind="info">
          还没有可用的默认学科。请在下方选择本次学科，或打开“默认设置”保存一次默认位置。
          <Link className="text-link" to="/subjects">
            去创建学科
          </Link>
        </Notice>
      )}

      <section className="import-panel">
        <div
          className={`import-dropzone${dragging ? ' is-dragging' : ''}`}
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              fileInputRef.current?.click()
            }
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={
              sourceType === 'external_json'
                ? '.json,application/json'
                : '.pdf,.docx,.pptx,.txt,.md,.markdown'
            }
            hidden
            onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
          />
          <strong>
            {file
              ? file.name
              : sourceType === 'external_json'
                ? '拖拽外部 AI JSON 到这里，或点击选择'
                : '拖拽文件到这里，或点击选择'}
          </strong>
          <span>
            {sourceType === 'external_json'
              ? '仅接受 BioLearn AI schema_version 1.0 的 JSON；导入前会校验并预览'
              : 'PDF · DOCX · PPTX · TXT · MD，单文件最大 25 MB'}
          </span>
        </div>

        <div className="import-grid">
          <div className="field">
            <label htmlFor="import-subject">学科</label>
            <select
              id="import-subject"
              value={subjectId}
              onChange={(event) => {
                setSubjectId(event.target.value)
                setChapterId('')
                setExternalChapterId('')
              }}
            >
              <option value="">请选择学科</option>
              {subjects.map((subject) => (
                <option value={subject.id} key={subject.id}>
                  {subject.name}
                </option>
              ))}
            </select>
          </div>

          {sourceType === 'courseware' && (
            <div className="field">
              <label>导入模式</label>
              <div className="import-mode-grid">
                {(Object.keys(MODE_LABELS) as ImportMode[]).map((value) => (
                  <button
                    type="button"
                    key={value}
                    className={`import-mode-card${mode === value ? ' is-active' : ''}`}
                    onClick={() => setMode(value)}
                  >
                    <strong>{MODE_LABELS[value]}</strong>
                    <span>{MODE_HINTS[value]}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {sourceType === 'courseware' && mode === 'preset' && (
            <div className="field">
              <label htmlFor="import-chapter">预设章节</label>
              <select
                id="import-chapter"
                value={chapterId}
                onChange={(event) => setChapterId(event.target.value)}
              >
                <option value="">学科根目录（不指定章节）</option>
                {chapterOptions.map(({ node, depth }) => (
                  <option value={node.id} key={node.id}>
                    {'— '.repeat(depth)}
                    {node.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {sourceType === 'courseware' ? (
            <div className="field import-options">
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={autoAnalyze}
                  onChange={(event) => setAutoAnalyze(event.target.checked)}
                />
                <span>归档后自动开始 AI 知识点分析</span>
              </label>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={requirePreview}
                  onChange={(event) => setRequirePreview(event.target.checked)}
                />
                <span>自动建章前先预览并确认</span>
              </label>
              <div className="field">
                <label htmlFor="import-uncertain">归档不确定时</label>
                <select
                  id="import-uncertain"
                  value={uncertainPolicy}
                  onChange={(event) =>
                    setUncertainPolicy(event.target.value as UncertainPolicy)
                  }
                >
                  <option value="confirm">等待我确认</option>
                  <option value="use_default">使用默认章节/根目录</option>
                  <option value="create">按建议继续（同名优先复用）</option>
                </select>
              </div>
            </div>
          ) : (
            <div className="field import-options">
              <div className="field">
                <label htmlFor="import-external-chapter">归档章节</label>
                <select
                  id="import-external-chapter"
                  value={externalChapterId}
                  onChange={(event) =>
                    setExternalChapterId(event.target.value)
                  }
                >
                  <option value="">按 JSON 章节树自动匹配/创建</option>
                  {chapterOptions.map(({ node, depth }) => (
                    <option value={node.id} key={node.id}>
                      {'— '.repeat(depth)}
                      {node.name}（全部知识点归入此章节）
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="import-duplicate-strategy">重复知识点处理</label>
                <select
                  id="import-duplicate-strategy"
                  value={duplicateStrategy}
                  onChange={(event) =>
                    setDuplicateStrategy(
                      event.target.value as 'skip' | 'update_pending',
                    )
                  }
                >
                  <option value="skip">跳过同名重复项（推荐）</option>
                  <option value="update_pending">更新未审核的 AI 草稿</option>
                </select>
              </div>
              <p className="form-hint">
                外部 AI 知识点默认全部进入待审核；已通过、需修改、已忽略和人工知识点不会被覆盖。
                导入后不会自动调用网页 AI 分析。
              </p>
            </div>
          )}
        </div>

        {error && <Notice kind="error">{error}</Notice>}

        <div className="import-actions">
          <button
            type="button"
            className="button button-primary"
            onClick={() => void submit()}
            disabled={busy || jobRunning || !file || !subjectId || !online}
          >
            {busy ? '上传中…' : '开始导入'}
          </button>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => setSettingsOpen((open) => !open)}
          >
            {settingsOpen ? '收起默认设置' : '默认设置'}
          </button>
          {jobRunning && <span className="form-hint">处理中，请稍候…</span>}
        </div>

        {settingsOpen && (
          <div className="import-settings">
            <div>
              <strong>默认设置</strong>
              <p className="form-hint">
                保存当前学科、章节、模式和自动分析选项，下次导入自动使用。
              </p>
            </div>
            <div className="import-settings-summary">
              <span>学科：{currentSubject?.name ?? '未选择'}</span>
              <span>
                章节：
                {chapterOptions.find(({ node }) => node.id === chapterId)?.node
                  .name ?? '学科根目录'}
              </span>
              <span>模式：{MODE_LABELS[mode]}</span>
            </div>
            <button
              type="button"
              className="button button-small button-primary"
              onClick={() => void savePreferences()}
              disabled={savingPreferences || !subjectId}
            >
              {savingPreferences ? '保存中…' : '保存为默认设置'}
            </button>
            {preferences?.updated_at && (
              <p className="form-hint">
                上次保存：{new Date(preferences.updated_at).toLocaleString()}
              </p>
            )}
          </div>
        )}
      </section>

      {job && (
        <section className="import-status">
          <div className="import-status-head">
            <div>
              <p className="eyebrow">Import progress</p>
              <h2>{job.document_name || file?.name || '导入任务'}</h2>
            </div>
            <span className={`status-badge import-status-${job.status}`}>
              {job.status === 'completed'
                ? '已完成'
                : job.status === 'failed'
                  ? '失败'
                  : job.status === 'awaiting_confirmation'
                    ? '等待确认'
                    : '处理中'}
            </span>
          </div>

          <div className="progress-track">
            <span style={{ width: `${job.progress}%` }} />
          </div>
          <p className="form-hint">
            {job.stage}
            {job.source_type === 'external_json'
              ? ' · 外部 AI JSON'
              : job.mode
                ? ` · ${MODE_LABELS[job.mode]}`
                : ''}
          </p>

          {job.error && <Notice kind="error">{job.error}</Notice>}
          {job.analysis_error && (
            <Notice kind="error">AI 分析：{job.analysis_error}</Notice>
          )}
          {job.analysis_status === 'cancelled' && (
            <Notice kind="info">
              资料已归档；AI 分析已停止，不会删除已导入的文件或章节。
            </Notice>
          )}
          {job.status === 'failed' && (
            <button
              type="button"
              className="button button-ghost"
              onClick={() => void retry()}
            >
              重试导入
            </button>
          )}

          {suggestion && (
            <div className="import-suggestion">
              <div className="import-suggestion-head">
                <div>
                  <strong>建议归档：{suggestion.title}</strong>
                  <p className="form-hint">
                    识别来源：
                    {PREVIEW_SOURCE_LABELS[suggestion.outline_source] ??
                      suggestion.outline_source}
                    · 置信度 {Math.round(suggestion.confidence * 100)}%
                    {suggestion.subject_confidence < 0.7
                      ? ' · 学科匹配较弱，已使用你选择的学科'
                      : ''}
                  </p>
                </div>
                <span className="stat-chip">{suggestion.subject_name}</span>
              </div>

              {suggestion.source_type === 'external_json' && (
                <div className="external-preview">
                  {suggestion.duplicate_import && (
                    <Notice kind="info">
                      该 JSON 文件已导入过。本次只做重复预览；确认后默认跳过重复知识点。
                    </Notice>
                  )}
                  <div className="external-preview-stats">
                    <span className="stat-chip">
                      知识点 <strong>{suggestion.knowledge_point_count}</strong>
                    </span>
                    <span className="stat-chip">
                      重复 <strong>{suggestion.duplicate_point_count}</strong>
                    </span>
                    <span className="stat-chip">
                      缺来源 <strong>{suggestion.missing_source_count}</strong>
                    </span>
                  </div>
                  {suggestion.points_preview.length > 0 && (
                    <div className="external-points">
                      <table>
                        <thead>
                          <tr>
                            <th>知识点</th>
                            <th>章节路径</th>
                            <th>来源</th>
                            <th>状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {suggestion.points_preview.map((point, index) => (
                            <tr key={`${point.title}-${index}`}>
                              <td>{point.title}</td>
                              <td>{point.chapter_path.join(' > ') || '根章节'}</td>
                              <td>
                                {point.source_page
                                  ? `第 ${point.source_page} 页`
                                  : point.source_slide
                                    ? `第 ${point.source_slide} 张`
                                    : '未提供'}
                              </td>
                              <td>
                                {point.duplicate_of_title
                                  ? `重复：${point.duplicate_of_title}`
                                  : point.warnings.length > 0
                                    ? point.warnings[0]
                                    : '待审核'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {suggestion.knowledge_point_count > 100 && (
                        <p className="form-hint">
                          仅展示前 100 条，完整数据会按确认结果导入。
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {suggestion.reasons.length > 0 && (
                <ul className="import-reasons">
                  {suggestion.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              )}

              <div className="import-chapter-tree">
                {suggestion.chapters.map((chapter, index) => (
                  <div
                    key={`${chapter.name}-${index}`}
                    className="import-chapter-row"
                    style={{ paddingLeft: `${(chapter.level - 1) * 18}px` }}
                  >
                    <span
                      className={`import-action import-action-${chapter.action}`}
                    >
                      {ACTION_LABELS[chapter.action] ?? chapter.action}
                    </span>
                    <strong>{chapter.name}</strong>
                    {chapter.source_slide && (
                      <span className="form-hint">
                        第 {chapter.source_slide} 张
                      </span>
                    )}
                    {chapter.existing_path && (
                      <span className="form-hint">
                        已有：{chapter.existing_path}
                      </span>
                    )}
                    {chapter.reason && (
                      <span className="form-hint">{chapter.reason}</span>
                    )}
                  </div>
                ))}
              </div>

              {job.status === 'awaiting_confirmation' && (
                <div className="import-confirm-actions">
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => void confirm(true)}
                    disabled={confirming}
                  >
                    {confirming ? '归档中…' : '按建议归档'}
                  </button>
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => void confirm(false)}
                    disabled={confirming}
                  >
                    归档到所选章节/根目录
                  </button>
                  <span className="form-hint">
                    选择“归档到所选章节”前，请在上方选择学科/章节；未选章节时归档到学科根目录。
                  </span>
                </div>
              )}
            </div>
          )}

          {terminal && result && (
            <div className="import-result">
              <strong>
                {result.duplicate
                  ? '该文件已导入过，未重复创建章节'
                  : '归档完成'}
              </strong>
              <p>
                学科：{currentSubject?.name ?? result.subject_id}
                {result.chapter_path.length > 0
                  ? ` · 章节：${result.chapter_path.join(' > ')}`
                  : ' · 学科根目录'}
              </p>
              {result.knowledge_point_count > 0 && (
                <p>
                  知识点：共 {result.knowledge_point_count} · 新建{' '}
                  {result.created_point_count} · 更新{' '}
                  {result.updated_point_count} · 跳过{' '}
                  {result.skipped_point_count}
                </p>
              )}
              <div className="import-result-actions">
                <Link
                  className="button button-small"
                  to={`/subjects/${result.subject_id}/documents`}
                >
                  查看资料库
                </Link>
                <Link
                  className="button button-small button-ghost"
                  to={`/documents/${job.document_id}/review`}
                >
                  查看知识点
                </Link>
              </div>
              {job.analysis_job_id && job.analysis_status === 'running' && (
                <p className="form-hint">
                  AI 知识点分析已启动，可在审核页查看进度或停止。
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {recentImports.length > 0 && (
        <section className="import-recent">
          <div className="panel-head">
            <div>
              <p className="eyebrow">Recent imports</p>
              <h2>最近导入</h2>
            </div>
          </div>
          <div className="import-recent-list">
            {recentImports.slice(0, 8).map((item) => (
              <button
                type="button"
                className={`import-recent-row${job?.id === item.id ? ' is-active' : ''}`}
                key={item.id}
                onClick={() => {
                  setJob(item)
                  setSourceType(
                    item.source_type === 'external_json'
                      ? 'external_json'
                      : 'courseware',
                  )
                }}
              >
                <span>
                  <strong>{item.document_name || item.id.slice(0, 8)}</strong>
                  <small>{item.stage}</small>
                </span>
                <span className={`status-badge import-status-${item.status}`}>
                  {item.status === 'completed'
                    ? '已完成'
                    : item.status === 'failed'
                      ? '失败'
                      : item.status === 'awaiting_confirmation'
                        ? '等待确认'
                        : '处理中'}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
