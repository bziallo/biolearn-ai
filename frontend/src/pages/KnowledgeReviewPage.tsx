import {
  useCallback,
  useEffect,
  useState,
} from 'react'
import { Link, useParams } from 'react-router-dom'

import { ConfirmDialog } from '../components/ConfirmDialog'
import { KnowledgePointForm, type KnowledgeFormValues } from '../components/KnowledgePointForm'
import { KnowledgePointTree } from '../components/KnowledgePointTree'
import { Modal } from '../components/Modal'
import { Notice } from '../components/Notice'
import {
  bulkReviewKnowledge,
  cancelJob,
  createKnowledgePoint,
  deleteKnowledgePoint,
  extractKnowledge,
  getAIStatus,
  getDocument,
  getDocumentKnowledge,
  getErrorMessage,
  getJob,
  getKnowledgePoint,
  mergeKnowledgePoints,
  retryJob,
  reviewKnowledgePoint,
  testAIConnection,
  updateKnowledgePoint,
  type AIStatus,
  type DocumentDetail,
  type DocumentKnowledge,
  type KnowledgeJob,
  type KnowledgePointDetail,
  type KnowledgePointNode,
  type ReviewStatus,
} from '../lib/api'
import {
  formatConfidence,
  formatDate,
  jobStatusLabels,
  knowledgeTypeLabels,
  reviewStatusLabels,
} from '../lib/format'
import {
  collectExpandablePointIds,
  countPointDescendants,
  findKnowledgeNode,
  flattenKnowledgeTree,
} from '../lib/knowledgeTree'
import { useToast } from '../lib/useToast'

type PageStatus = 'loading' | 'ready' | 'error'
type DetailStatus = 'idle' | 'loading' | 'ready' | 'error'

const RUNNING_JOB_STATUSES = new Set([
  'queued',
  'analyzing',
  'extracting',
  'merging',
  'cancelling',
])

function isRunningJob(job: KnowledgeJob | null): boolean {
  return Boolean(job && RUNNING_JOB_STATUSES.has(job.status))
}

function filterKnowledgeTree(
  nodes: KnowledgePointNode[],
  query: string,
  statusFilter: ReviewStatus | '',
): KnowledgePointNode[] {
  const keyword = query.trim().toLowerCase()
  return nodes.flatMap((node) => {
    const children = filterKnowledgeTree(
      node.children ?? [],
      query,
      statusFilter,
    )
    const matchesQuery =
      !keyword ||
      node.name.toLowerCase().includes(keyword) ||
      node.explanation.toLowerCase().includes(keyword)
    const matchesStatus = !statusFilter || node.review_status === statusFilter
    if ((matchesQuery && matchesStatus) || children.length > 0) {
      return [{ ...node, children }]
    }
    return []
  })
}

export function KnowledgeReviewPage() {
  const { documentId = '' } = useParams<{ documentId: string }>()
  const { notify } = useToast()

  const [data, setData] = useState<DocumentKnowledge | null>(null)
  const [documentDetail, setDocumentDetail] = useState<DocumentDetail | null>(
    null,
  )
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null)
  const [status, setStatus] = useState<PageStatus>('loading')
  const [error, setError] = useState('')

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<KnowledgePointDetail | null>(null)
  const [detailStatus, setDetailStatus] = useState<DetailStatus>('idle')
  const [detailError, setDetailError] = useState('')
  const [detailVersion, setDetailVersion] = useState(0)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())

  const [liveJob, setLiveJob] = useState<KnowledgeJob | null>(null)
  const [jobBusy, setJobBusy] = useState(false)
  const [cancelBusy, setCancelBusy] = useState(false)
  const [reExtractConfirmOpen, setReExtractConfirmOpen] = useState(false)
  const [testBusy, setTestBusy] = useState(false)
  const [editor, setEditor] = useState<
    | { mode: 'create'; parentId: string | null }
    | { mode: 'edit'; point: KnowledgePointNode }
    | null
  >(null)
  const [savingPoint, setSavingPoint] = useState(false)
  const [deletingPoint, setDeletingPoint] =
    useState<KnowledgePointNode | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [mergeOpen, setMergeOpen] = useState(false)
  const [mergeName, setMergeName] = useState('')
  const [mergeExplanation, setMergeExplanation] = useState('')
  const [mergeBusy, setMergeBusy] = useState(false)
  const [pointQuery, setPointQuery] = useState('')
  const [pointStatusFilter, setPointStatusFilter] = useState<ReviewStatus | ''>('')

  const applyKnowledge = useCallback((knowledge: DocumentKnowledge) => {
    setData(knowledge)
    setExpanded((previous) => {
      const next = new Set(previous)
      collectExpandablePointIds(knowledge.points, next)
      return next
    })
    const existingIds = new Set(
      flattenKnowledgeTree(knowledge.points).map(({ node }) => node.id),
    )
    setCheckedIds((previous) => {
      const next = new Set<string>()
      previous.forEach((id) => {
        if (existingIds.has(id)) {
          next.add(id)
        }
      })
      return next
    })
    setSelectedId((current) => {
      if (current && findKnowledgeNode(knowledge.points, current)) {
        return current
      }
      return flattenKnowledgeTree(knowledge.points)[0]?.node.id ?? null
    })
    setLiveJob(knowledge.latest_job)
  }, [])

  const refreshKnowledge = useCallback(
    async (signal?: AbortSignal) => {
      const knowledge = await getDocumentKnowledge(documentId, signal)
      applyKnowledge(knowledge)
      return knowledge
    },
    [applyKnowledge, documentId],
  )

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setStatus('loading')
      setError('')
      try {
        const [knowledge, document] = await Promise.all([
          getDocumentKnowledge(documentId, signal),
          getDocument(documentId, signal),
        ])
        applyKnowledge(knowledge)
        setDocumentDetail(document)
        setStatus('ready')
        getAIStatus(signal)
          .then(setAIStatus)
          .catch(() => setAIStatus(null))
      } catch (loadError) {
        if (signal?.aborted) {
          return
        }
        setStatus('error')
        setError(getErrorMessage(loadError))
      }
    },
    [applyKnowledge, documentId],
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
      return
    }
    const controller = new AbortController()
    setDetailStatus('loading')
    setDetailError('')
    getKnowledgePoint(selectedId, controller.signal)
      .then((nextDetail) => {
        setDetail(nextDetail)
        setDetailStatus('ready')
      })
      .catch((detailRequestError: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setDetailStatus('error')
        setDetailError(getErrorMessage(detailRequestError))
      })
    return () => controller.abort()
  }, [selectedId, detailVersion])

  useEffect(() => {
    if (!liveJob || !isRunningJob(liveJob)) {
      return
    }
    const timer = globalThis.setInterval(() => {
      getJob(liveJob.id)
        .then(async (nextJob) => {
          setLiveJob(nextJob)
          if (!isRunningJob(nextJob)) {
            await refreshKnowledge()
            if (nextJob.status === 'completed') {
              notify('success', 'AI 知识点草稿已生成')
            } else if (nextJob.status === 'cancelled') {
              notify('info', 'AI 任务已停止，未保存新的草稿')
            } else {
              notify('error', nextJob.error || 'AI 任务失败')
            }
          }
        })
        .catch((jobError: unknown) => {
          notify('error', getErrorMessage(jobError))
        })
    }, 1800)
    return () => globalThis.clearInterval(timer)
  }, [liveJob, notify, refreshKnowledge])

  async function startExtraction() {
    setJobBusy(true)
    try {
      const job = await extractKnowledge(documentId)
      setLiveJob(job)
      notify('success', 'AI 任务已启动，正在分析整章结构')
    } catch (startError) {
      notify('error', getErrorMessage(startError))
    } finally {
      setJobBusy(false)
    }
  }

  function requestExtraction() {
    if ((data?.points.length ?? 0) > 0 || liveJob?.status === 'completed') {
      setReExtractConfirmOpen(true)
      return
    }
    void startExtraction()
  }

  async function retryExtraction() {
    if (!liveJob) {
      return
    }
    setJobBusy(true)
    try {
      const job = await retryJob(liveJob.id)
      setLiveJob(job)
      notify('success', 'AI 任务已重新启动')
    } catch (retryError) {
      notify('error', getErrorMessage(retryError))
    } finally {
      setJobBusy(false)
    }
  }

  async function cancelExtraction() {
    if (!liveJob || !isRunningJob(liveJob)) {
      return
    }
    setCancelBusy(true)
    try {
      const job = await cancelJob(liveJob.id)
      setLiveJob(job)
      notify('info', '已请求停止，当前模型请求结束后生效')
    } catch (cancelError) {
      notify('error', getErrorMessage(cancelError))
    } finally {
      setCancelBusy(false)
    }
  }

  async function testAI() {
    setTestBusy(true)
    try {
      const result = await testAIConnection()
      notify('success', `${result.message}：${result.model ?? '模型可用'}`)
    } catch (testError) {
      notify('error', getErrorMessage(testError))
    } finally {
      setTestBusy(false)
    }
  }

  async function review(statusValue: ReviewStatus) {
    if (!selectedId) {
      return
    }
    try {
      await reviewKnowledgePoint(selectedId, statusValue)
      await refreshKnowledge()
      setDetailVersion((version) => version + 1)
      notify('success', `知识点已标记为${reviewStatusLabels[statusValue]}`)
    } catch (reviewError) {
      notify('error', getErrorMessage(reviewError))
    }
  }

  async function bulkReview(statusValue: ReviewStatus) {
    if (checkedIds.size === 0) {
      return
    }
    try {
      const result = await bulkReviewKnowledge(
        Array.from(checkedIds),
        statusValue,
      )
      setCheckedIds(new Set())
      await refreshKnowledge()
      notify(
        'success',
        `已批量标记 ${result.updated} 个知识点为${reviewStatusLabels[statusValue]}`,
      )
    } catch (bulkError) {
      notify('error', getErrorMessage(bulkError))
    }
  }

  function openCreate(parentId: string | null = null) {
    setEditor({ mode: 'create', parentId })
  }

  function openEdit() {
    const node = selectedId
      ? findKnowledgeNode(data?.points ?? [], selectedId)
      : null
    if (node) {
      setEditor({ mode: 'edit', point: node })
    }
  }

  async function savePoint(values: KnowledgeFormValues) {
    if (!editor) {
      return
    }
    setSavingPoint(true)
    try {
      if (editor.mode === 'create') {
        const created = await createKnowledgePoint({
          document_id: documentId,
          ...values,
        })
        setEditor(null)
        await refreshKnowledge()
        setSelectedId(created.id)
        notify('success', '知识点已新增')
      } else {
        const updated = await updateKnowledgePoint(editor.point.id, values)
        setEditor(null)
        await refreshKnowledge()
        setSelectedId(updated.id)
        setDetailVersion((version) => version + 1)
        notify('success', '知识点已更新')
      }
    } catch (saveError) {
      notify('error', getErrorMessage(saveError))
    } finally {
      setSavingPoint(false)
    }
  }

  async function deletePoint() {
    if (!deletingPoint) {
      return
    }
    setDeleteBusy(true)
    try {
      await deleteKnowledgePoint(
        deletingPoint.id,
        countPointDescendants(deletingPoint) > 0,
      )
      setDeletingPoint(null)
      setSelectedId(null)
      setDetail(null)
      await refreshKnowledge()
      notify('success', '知识点已删除')
    } catch (deleteError) {
      notify('error', getErrorMessage(deleteError))
    } finally {
      setDeleteBusy(false)
    }
  }

  function openMerge() {
    const selected = checkedIds.size
      ? flattenKnowledgeTree(data?.points ?? []).filter(({ node }) =>
          checkedIds.has(node.id),
        )
      : []
    if (selected.length < 2) {
      return
    }
    setMergeName(selected[0].node.name)
    setMergeExplanation(selected[0].node.explanation)
    setMergeOpen(true)
  }

  async function mergeSelected() {
    if (checkedIds.size < 2) {
      return
    }
    setMergeBusy(true)
    try {
      const merged = await mergeKnowledgePoints(
        Array.from(checkedIds),
        mergeName.trim() || undefined,
        mergeExplanation.trim() || undefined,
      )
      setMergeOpen(false)
      setCheckedIds(new Set())
      await refreshKnowledge()
      setSelectedId(merged.id)
      setDetailVersion((version) => version + 1)
      notify('success', '知识点已合并，请重新审核')
    } catch (mergeError) {
      notify('error', getErrorMessage(mergeError))
    } finally {
      setMergeBusy(false)
    }
  }

  function toggleChecked(pointId: string, checked: boolean) {
    setCheckedIds((previous) => {
      const next = new Set(previous)
      if (checked) {
        next.add(pointId)
      } else {
        next.delete(pointId)
      }
      return next
    })
  }

  function toggleExpanded(pointId: string) {
    setExpanded((previous) => {
      const next = new Set(previous)
      if (next.has(pointId)) {
        next.delete(pointId)
      } else {
        next.add(pointId)
      }
      return next
    })
  }

  const points = filterKnowledgeTree(
    data?.points ?? [],
    pointQuery,
    pointStatusFilter,
  )
  const stats = data?.stats
  const flatPoints = flattenKnowledgeTree(points)
  const document = data?.document ?? documentDetail
  const canExtract =
    document?.status === 'parsed' &&
    (documentDetail?.chunk_count ?? 0) > 0 &&
    Boolean(aiStatus?.configured)
  const jobRunning = isRunningJob(liveJob) || jobBusy

  if (status === 'loading') {
    return <div className="loading-block">正在加载知识点审核区…</div>
  }

  if (status === 'error' || !data) {
    return (
      <div className="review-page">
        <Link className="back-link" to={`/subjects`}>
          ← 返回学科列表
        </Link>
        <div className="error-panel">
          <Notice kind="error">无法加载知识点：{error}</Notice>
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
    <div className="review-page">
      <Link
        className="back-link"
        to={`/subjects/${documentDetail?.subject_id ?? ''}/documents`}
      >
        ← 返回资料库
      </Link>

      <header className="review-heading">
        <div>
          <p className="eyebrow">Knowledge review</p>
          <h1>{data.document.name}</h1>
          <p className="lede">
            知识树 · 编辑面板 · 原文依据。AI 结果先进入待审核区，通过后才算正式入库。
          </p>
        </div>
        <div className="review-heading-actions">
          <span className={`status-badge document-status-${document?.status}`}>
            {document?.status === 'parsed'
              ? '资料已解析'
              : document?.status === 'needs_ocr'
                ? '需要 OCR'
                : document?.status ?? '未知状态'}
          </span>
          <button
            type="button"
            className="button button-primary"
            onClick={() => openCreate(null)}
          >
            ＋ 新增知识点
          </button>
        </div>
      </header>

      <section className="review-stats" aria-label="知识点统计">
        <span className="stat-chip">
          总数 <strong>{stats?.total ?? 0}</strong>
        </span>
        <span className="stat-chip">
          待审核 <strong>{stats?.pending ?? 0}</strong>
        </span>
        <span className="stat-chip stat-approved">
          已通过 <strong>{stats?.approved ?? 0}</strong>
        </span>
        <span className="stat-chip">
          需修改 <strong>{stats?.needs_revision ?? 0}</strong>
        </span>
        <span className="stat-chip">
          已忽略 <strong>{stats?.ignored ?? 0}</strong>
        </span>
        <span className="stat-chip stat-warning">
          待确认 <strong>{stats?.needs_review ?? 0}</strong>
        </span>
        <span className="stat-chip">
          重复项 <strong>{stats?.duplicates ?? 0}</strong>
        </span>
        <span className="stat-chip">
          失败任务 <strong>{stats?.failed_jobs ?? 0}</strong>
        </span>
      </section>

      <section className="ai-panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">AI pipeline</p>
            <h2>AI 知识点识别</h2>
          </div>
          <span className="ai-config-status">
            {aiStatus?.configured ? 'AI 已配置' : 'AI 未配置'}
          </span>
        </div>

        {!aiStatus?.configured && (
          <Notice kind="info">
            {aiStatus?.message ??
              '请打开 AI 设置页填写 API Base、API Key 和模型。'}{' '}
            当前不会生成任何伪造的 AI 结果。
            <Link className="text-link" to="/settings/ai">
              打开 AI 设置
            </Link>
          </Notice>
        )}
        {document?.status !== 'parsed' && (
          <Notice kind="error">
            资料尚未成功解析，无法启动知识点提取。请回到资料库查看解析结果或重试。
          </Notice>
        )}

        <div className="ai-actions">
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void testAI()}
            disabled={testBusy || !aiStatus?.configured}
          >
            {testBusy ? '测试中…' : '测试模型连接'}
          </button>
          <button
            type="button"
            className="button button-primary"
            onClick={() => requestExtraction()}
            disabled={!canExtract || jobRunning}
          >
            {jobRunning
              ? 'AI 任务运行中…'
              : liveJob?.status === 'completed'
                ? '重新识别整章'
                : '开始 AI 识别'}
          </button>
          {liveJob?.status === 'failed' && (
            <button
              type="button"
              className="button button-ghost"
              onClick={() => void retryExtraction()}
              disabled={jobBusy}
            >
              重试失败任务
            </button>
          )}
          {isRunningJob(liveJob) && (
            <button
              type="button"
              className="button button-danger-ghost"
              onClick={() => void cancelExtraction()}
              disabled={cancelBusy || liveJob?.status === 'cancelling'}
            >
              {cancelBusy || liveJob?.status === 'cancelling'
                ? '正在停止…'
                : '停止 AI 识别'}
            </button>
          )}
        </div>

        {liveJob && (
          <div className="job-card">
            <div className="job-card-head">
              <strong>{jobStatusLabels[liveJob.status]}</strong>
              <span>{liveJob.stage}</span>
              {liveJob.status === 'extracting' && (
                <span>{liveJob.progress}%</span>
              )}
              {liveJob.status === 'merging' && <span>合并中</span>}
            </div>
            <div className="progress-track">
              <span style={{ width: `${liveJob.progress}%` }} />
            </div>
            <p className="form-hint">
              第 {liveJob.processed_chunks}/{liveJob.total_chunks} 块 · 提取{' '}
              {liveJob.extracted_count} · 合并 {liveJob.merged_count} · 重复{' '}
              {liveJob.duplicate_count} · 尝试 {liveJob.attempts}
            </p>
            {liveJob.error && <Notice kind="error">{liveJob.error}</Notice>}
          </div>
        )}

        <p className="form-hint">
          重新识别会替换未审核的 AI 草稿，保留已通过、需修改、已忽略和人工新增的知识点。
          停止识别会在当前模型请求返回后生效，不会删除已有草稿。
        </p>
      </section>

      {points.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">
            🧠
          </span>
          <h2>还没有知识点</h2>
          <p>
            配置 AI 后开始识别，或手动新增知识点。AI 输出会先进入待审核区，不会直接覆盖知识库。
          </p>
          <div className="empty-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={() => requestExtraction()}
              disabled={!canExtract || jobRunning}
            >
              开始 AI 识别
            </button>
            <button
              type="button"
              className="button button-ghost"
              onClick={() => openCreate(null)}
            >
              手动新增
            </button>
          </div>
        </div>
      ) : (
        <div className="review-grid">
          <section className="knowledge-tree-panel">
            <div className="panel-head">
              <div>
                <p className="eyebrow">Knowledge tree</p>
                <h2>知识点树</h2>
              </div>
              <span className="tree-total">{flatPoints.length} 个</span>
            </div>
            <div className="knowledge-filter-bar">
              <input
                type="search"
                aria-label="搜索知识点"
                placeholder="搜索名称或解释"
                value={pointQuery}
                onChange={(event) => setPointQuery(event.target.value)}
              />
              <select
                aria-label="按审核状态筛选"
                value={pointStatusFilter}
                onChange={(event) =>
                  setPointStatusFilter(event.target.value as ReviewStatus | '')
                }
              >
                <option value="">全部状态</option>
                <option value="pending">待审核</option>
                <option value="approved">已通过</option>
                <option value="needs_revision">需修改</option>
                <option value="ignored">已忽略</option>
              </select>
            </div>
            <div className="tree-toolbar">
              <button
                type="button"
                className="text-button"
                onClick={() =>
                  setCheckedIds(new Set(flatPoints.map(({ node }) => node.id)))
                }
              >
                全选
              </button>
              <button
                type="button"
                className="text-button"
                onClick={() => setCheckedIds(new Set())}
                disabled={checkedIds.size === 0}
              >
                清空
              </button>
              <span>{checkedIds.size} 已选</span>
            </div>
            {checkedIds.size > 0 && (
              <div className="bulk-bar">
                <button
                  type="button"
                  className="mini-button"
                  onClick={() => void bulkReview('approved')}
                >
                  批量通过
                </button>
                <button
                  type="button"
                  className="mini-button"
                  onClick={() => void bulkReview('needs_revision')}
                >
                  批量需修改
                </button>
                <button
                  type="button"
                  className="mini-button"
                  onClick={() => void bulkReview('ignored')}
                >
                  批量忽略
                </button>
                <button
                  type="button"
                  className="mini-button"
                  onClick={openMerge}
                  disabled={checkedIds.size < 2}
                >
                  合并选中
                </button>
              </div>
            )}
            <KnowledgePointTree
              nodes={points}
              selectedId={selectedId}
              checkedIds={checkedIds}
              expanded={expanded}
              onToggle={toggleExpanded}
              onSelect={setSelectedId}
              onCheck={toggleChecked}
            />
          </section>

          <section className="knowledge-editor-panel">
            {detailStatus === 'loading' && (
              <div className="loading-block">正在加载知识点…</div>
            )}
            {detailStatus === 'error' && (
              <Notice kind="error">{detailError}</Notice>
            )}
            {detailStatus === 'idle' && (
              <div className="panel-placeholder">
                <p className="eyebrow">Review editor</p>
                <h2>选择一个知识点</h2>
                <p>查看解释、核心要点和审核状态，或在这里编辑层级。</p>
              </div>
            )}
            {detailStatus === 'ready' && detail && (
              <div className="knowledge-editor">
                <div className="editor-title">
                  <span className="knowledge-type">
                    {knowledgeTypeLabels[detail.type]}
                  </span>
                  <h2>{detail.name}</h2>
                  <span className={`status-badge review-${detail.review_status}`}>
                    {reviewStatusLabels[detail.review_status]}
                  </span>
                </div>
                <p className="editor-explanation">{detail.explanation}</p>
                {detail.core_points.length > 0 && (
                  <div className="core-points">
                    <h3>核心要点</h3>
                    <ul>
                      {detail.core_points.map((point) => (
                        <li key={point}>{point}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {detail.conditions && (
                  <div className="conditions">
                    <h3>适用条件 / 例外</h3>
                    <p>{detail.conditions}</p>
                  </div>
                )}
                <dl className="meta-grid">
                  <div>
                    <dt>来源</dt>
                    <dd>{detail.origin === 'ai' ? 'AI 生成' : '人工新增'}</dd>
                  </div>
                  <div>
                    <dt>置信度</dt>
                    <dd>{formatConfidence(detail.confidence)}</dd>
                  </div>
                  <div>
                    <dt>所属学科</dt>
                    <dd>{detail.subject_name}</dd>
                  </div>
                  <div>
                    <dt>所属章节</dt>
                    <dd>{detail.chapter_name ?? '未指定'}</dd>
                  </div>
                  <div>
                    <dt>更新时间</dt>
                    <dd>{formatDate(detail.updated_at)}</dd>
                  </div>
                  <div>
                    <dt>正式入库</dt>
                    <dd>
                      {detail.review_status === 'approved'
                        ? `是 · ${formatDate(detail.published_at)}`
                        : '否'}
                    </dd>
                  </div>
                </dl>
                {detail.needs_review && (
                  <Notice kind="info">
                    此知识点被标记为待确认；置信度只是模型信号，不能作为正确性证明。
                  </Notice>
                )}
                {detail.review_note && (
                  <Notice kind="info">{detail.review_note}</Notice>
                )}
                <div className="editor-actions">
                  <button
                    type="button"
                    className="button button-small"
                    onClick={openEdit}
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    className="button button-small button-ghost"
                    onClick={() => openCreate(detail.id)}
                  >
                    ＋ 子知识点
                  </button>
                  <button
                    type="button"
                    className="button button-small button-primary"
                    onClick={() => void review('approved')}
                  >
                    通过并入库
                  </button>
                  <button
                    type="button"
                    className="button button-small button-ghost"
                    onClick={() => void review('needs_revision')}
                  >
                    需要修改
                  </button>
                  <button
                    type="button"
                    className="button button-small button-ghost"
                    onClick={() => void review('ignored')}
                  >
                    忽略
                  </button>
                  <button
                    type="button"
                    className="button button-small button-danger-ghost"
                    onClick={() => {
                      const node = findKnowledgeNode(points, detail.id)
                      if (node) {
                        setDeletingPoint(node)
                      }
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
            )}
          </section>

          <aside className="source-panel">
            <p className="eyebrow">Source evidence</p>
            <h2>原文依据</h2>
            {detail ? (
              <>
                <p className="source-locator">
                  {detail.source_locator ?? detail.source_chunk_heading ?? '未记录位置'}
                </p>
                {detail.source_quote ? (
                  <blockquote className="source-quote">
                    {detail.source_quote}
                    <span
                      className={`quote-check ${
                        detail.source_quote_verified ? 'is-verified' : ''
                      }`}
                    >
                      {detail.source_quote_verified
                        ? '✓ 原文匹配'
                        : '引文未匹配'}
                    </span>
                  </blockquote>
                ) : (
                  <Notice kind="info">
                    没有可核验的逐字引文；该系统不会编造引用。请查看下方原文分块。
                  </Notice>
                )}
                {detail.source_chunk_content ? (
                  <details className="source-chunk" open>
                    <summary>
                      {detail.source_chunk_heading ?? '原始分块'}
                    </summary>
                    <pre>{detail.source_chunk_content}</pre>
                  </details>
                ) : (
                  <p className="form-hint">该知识点没有关联的原文分块。</p>
                )}
              </>
            ) : (
              <p className="form-hint">选中知识点后显示原文依据。</p>
            )}
          </aside>
        </div>
      )}

      <Modal
        open={editor !== null}
        title={editor?.mode === 'edit' ? '编辑知识点' : '新增知识点'}
        busy={savingPoint}
        onClose={() => {
          if (!savingPoint) {
            setEditor(null)
          }
        }}
      >
        {editor && (
          <KnowledgePointForm
            key={
              editor.mode === 'edit'
                ? editor.point.id
                : `create-${editor.parentId ?? 'root'}`
            }
            mode={editor.mode}
            initial={editor.mode === 'edit' ? editor.point : null}
            tree={points}
            defaultParentId={
              editor.mode === 'create' ? editor.parentId : null
            }
            submitting={savingPoint}
            onSubmit={(values) => void savePoint(values)}
            onCancel={() => {
              if (!savingPoint) {
                setEditor(null)
              }
            }}
          />
        )}
      </Modal>

      <Modal
        open={mergeOpen}
        title="合并选中知识点"
        busy={mergeBusy}
        onClose={() => {
          if (!mergeBusy) {
            setMergeOpen(false)
          }
        }}
      >
        <div className="entity-form">
          <p className="form-hint">
            将合并 {checkedIds.size} 个知识点。合并结果会回到待审核状态，来源和核心要点会尽量保留。
          </p>
          <div className="field">
            <label htmlFor="merge-name">合并后名称</label>
            <input
              id="merge-name"
              value={mergeName}
              onChange={(event) => setMergeName(event.target.value)}
              maxLength={300}
            />
          </div>
          <div className="field">
            <label htmlFor="merge-explanation">合并后解释</label>
            <textarea
              id="merge-explanation"
              value={mergeExplanation}
              onChange={(event) => setMergeExplanation(event.target.value)}
              rows={5}
            />
          </div>
          <div className="form-actions">
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setMergeOpen(false)}
              disabled={mergeBusy}
            >
              取消
            </button>
            <button
              type="button"
              className="button button-primary"
              onClick={() => void mergeSelected()}
              disabled={mergeBusy}
            >
              {mergeBusy ? '合并中…' : '确认合并'}
            </button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={deletingPoint !== null}
        title="删除知识点"
        description={
          deletingPoint
            ? countPointDescendants(deletingPoint) > 0
              ? `「${deletingPoint.name}」下有 ${countPointDescendants(
                  deletingPoint,
                )} 个后代知识点。删除会移除整棵子树，且无法恢复。`
              : `删除「${deletingPoint.name}」后无法恢复。`
            : ''
        }
        confirmLabel="删除知识点"
        busy={deleteBusy}
        acknowledgement={
          deletingPoint && countPointDescendants(deletingPoint) > 0
            ? `我了解将同时删除 ${countPointDescendants(
                deletingPoint,
              )} 个后代知识点`
            : undefined
        }
        onConfirm={() => void deletePoint()}
        onCancel={() => {
          if (!deleteBusy) {
            setDeletingPoint(null)
          }
        }}
      />

      <ConfirmDialog
        open={reExtractConfirmOpen}
        title="重新识别整章"
        description="当前资料已有知识点。重新识别会替换未审核的 AI 草稿，保留已通过、需修改、已忽略和人工新增的知识点；运行中也可以停止。确定继续吗？"
        confirmLabel="开始识别"
        busy={jobBusy}
        onConfirm={() => {
          setReExtractConfirmOpen(false)
          void startExtraction()
        }}
        onCancel={() => {
          if (!jobBusy) {
            setReExtractConfirmOpen(false)
          }
        }}
      />
    </div>
  )
}
