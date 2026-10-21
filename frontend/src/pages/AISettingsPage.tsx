import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { Notice } from '../components/Notice'
import {
  clearAIConfig,
  getAIStatus,
  getErrorMessage,
  saveAIConfig,
  testAIConnection,
  type AIStatus,
} from '../lib/api'
import { useToast } from '../lib/useToast'

type PageStatus = 'loading' | 'ready' | 'error'

const PROVIDER_OPTIONS = [
  { value: 'openai-compatible', label: 'OpenAI 兼容 API' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'custom', label: '自定义兼容网关' },
]

export function AISettingsPage() {
  const { notify } = useToast()
  const [status, setStatus] = useState<AIStatus | null>(null)
  const [pageStatus, setPageStatus] = useState<PageStatus>('loading')
  const [error, setError] = useState('')

  const [provider, setProvider] = useState('openai-compatible')
  const [apiBase, setApiBase] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [clearKey, setClearKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [clearing, setClearing] = useState(false)

  const applyStatus = useCallback((next: AIStatus) => {
    setStatus(next)
    setProvider(next.provider || 'openai-compatible')
    setApiBase(next.api_base || '')
    setModel(next.model || '')
  }, [])

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setPageStatus('loading')
      setError('')
      try {
        const next = await getAIStatus(signal)
        applyStatus(next)
        setPageStatus('ready')
      } catch (loadError) {
        if (signal?.aborted) {
          return
        }
        setPageStatus('error')
        setError(getErrorMessage(loadError))
      }
    },
    [applyStatus],
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    try {
      const next = await saveAIConfig({
        provider,
        api_base: apiBase.trim(),
        model: model.trim(),
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        ...(clearKey ? { clear_key: true } : {}),
      })
      applyStatus(next)
      setApiKey('')
      setClearKey(false)
      notify(
        'success',
        next.configured
          ? 'AI 配置已保存，可以测试连接或开始识别'
          : '配置已保存，但 API Base、Key 或模型仍不完整',
      )
    } catch (saveError) {
      notify('error', getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    setTesting(true)
    try {
      const result = await testAIConnection()
      notify('success', `${result.message}：${result.model ?? '模型可用'}`)
    } catch (testError) {
      notify('error', getErrorMessage(testError))
    } finally {
      setTesting(false)
    }
  }

  async function handleClear() {
    setClearing(true)
    try {
      const next = await clearAIConfig()
      applyStatus(next)
      setApiKey('')
      setClearKey(false)
      notify('success', '已移除页面保存的 AI 配置')
    } catch (clearError) {
      notify('error', getErrorMessage(clearError))
    } finally {
      setClearing(false)
    }
  }

  const sourceLabel =
    status?.source === 'runtime'
      ? '页面保存的服务器配置'
      : status?.source === 'environment'
        ? '后端环境变量'
        : '尚未配置'

  return (
    <div className="ai-settings-page">
      <Link className="back-link" to="/">
        ← 返回首页
      </Link>

      <header className="page-heading">
        <div>
          <p className="eyebrow">AI provider</p>
          <h1>AI 设置</h1>
          <p className="lede">
            在这里填写 OpenAI 兼容服务的 API Base、模型和 Key。Key 只发送到本机后端，
            保存在服务器本地配置文件中，不会回显到浏览器或提交到 Git。
          </p>
        </div>
      </header>

      {pageStatus === 'error' && (
        <div className="error-panel">
          <Notice kind="error">无法读取 AI 配置：{error}</Notice>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void load()}
          >
            重新加载
          </button>
        </div>
      )}

      {pageStatus === 'loading' && (
        <div className="loading-block">正在读取 AI 配置…</div>
      )}

      {pageStatus === 'ready' && status && (
        <>
          <section className={`ai-config-summary ${status.configured ? 'is-ready' : ''}`}>
            <div>
              <span className={`status-dot ${status.configured ? 'status-online' : 'status-offline'}`} />
              <strong>{status.configured ? 'AI 已配置' : 'AI 未配置'}</strong>
              <span>{sourceLabel}</span>
            </div>
            <p>{status.message}</p>
            {status.key_configured && (
              <span className="key-status">Key 已保存，但不会显示</span>
            )}
          </section>

          <form className="ai-config-form" onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="ai-provider">提供商类型</label>
              <select
                id="ai-provider"
                value={provider}
                onChange={(event) => setProvider(event.target.value)}
              >
                {PROVIDER_OPTIONS.map((option) => (
                  <option value={option.value} key={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="ai-api-base">API Base URL</label>
              <input
                id="ai-api-base"
                value={apiBase}
                onChange={(event) => setApiBase(event.target.value)}
                placeholder="例如：https://api.openai.com/v1"
                spellCheck={false}
                autoComplete="off"
              />
              <p className="form-hint">
                通常需要包含 /v1；后端会调用 {'{AI_API_BASE}'}/chat/completions。
              </p>
            </div>

            <div className="field">
              <label htmlFor="ai-model">模型名称</label>
              <input
                id="ai-model"
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="例如：gpt-4o-mini"
                spellCheck={false}
                autoComplete="off"
              />
            </div>

            <div className="field">
              <label htmlFor="ai-api-key">API Key</label>
              <input
                id="ai-api-key"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={
                  status.key_configured
                    ? '已配置；留空保持不变'
                    : '输入 API Key（不会回显）'
                }
                autoComplete="new-password"
                spellCheck={false}
              />
              <p className="form-hint">
                Key 只写入后端 backend/data/ai_config.json，该目录已被 Git 忽略。
              </p>
            </div>

            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={clearKey}
                onChange={(event) => setClearKey(event.target.checked)}
              />
              <span>清除已保存的 Key（如果环境变量里仍有 Key，会回退到环境变量）</span>
            </label>

            <div className="form-actions">
              <button
                type="button"
                className="button button-ghost"
                onClick={() => void handleTest()}
                disabled={testing || !status.configured}
              >
                {testing ? '测试中…' : '测试模型连接'}
              </button>
              <button
                type="submit"
                className="button button-primary"
                disabled={saving}
              >
                {saving ? '保存中…' : '保存 AI 配置'}
              </button>
            </div>
          </form>

          <section className="ai-config-help">
            <h2>保存后怎么用</h2>
            <ol>
              <li>先保存配置，再点“测试模型连接”。</li>
              <li>打开一个已解析的资料，进入“审核知识点”。</li>
              <li>点击“开始 AI 识别”，页面会显示结构分析、逐块提取和全章合并进度。</li>
            </ol>
            <div className="form-actions">
              <button
                type="button"
                className="button button-danger-ghost"
                onClick={() => void handleClear()}
                disabled={clearing}
              >
                {clearing ? '清除中…' : '移除页面保存的配置'}
              </button>
              <Link className="button button-ghost" to="/subjects">
                返回学科
              </Link>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
