import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Notice } from '../components/Notice'
import {
  describeConnection,
  getAccessToken,
  setAccessToken,
  setRuntimeBaseUrl,
  type ClientEnvironment,
} from '../lib/api/connection'
import { getAuthStatus, logout, refreshConnection } from '../lib/api'
import { useToast } from '../lib/useToast'

function normalize(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, '')
  if (!trimmed) {
    return ''
  }
  if (!/^https?:\/\//i.test(trimmed)) {
    return `http://${trimmed}`
  }
  return trimmed
}

function withApiSuffix(value: string): string {
  if (!value) {
    return ''
  }
  return /\/api\/v1$/i.test(value) ? value : `${value}/api/v1`
}

const ENVIRONMENT_HINTS: Record<ClientEnvironment, string> = {
  browser: '浏览器访问：留空即使用当前网页同源的 /api/v1。',
  android: '手机 App：必须填写电脑的局域网地址（手机不能访问电脑的 localhost）。',
}

export function ConnectionSettingsPage() {
  const { notify } = useToast()
  const navigate = useNavigate()
  const initial = describeConnection()
  const [environment] = useState<ClientEnvironment>(initial.environment)
  const [baseUrl, setBaseUrl] = useState(
    initial.source === 'runtime' ? initial.baseUrl : '',
  )
  const [token, setToken] = useState(getAccessToken())
  const [status, setStatus] = useState<'idle' | 'checking' | 'ok' | 'failed' | 'auth'>('idle')
  const [message, setMessage] = useState('')
  const [serverAuth, setServerAuth] = useState<{ required: boolean; authenticated: boolean } | null>(null)

  const test = useCallback(async () => {
    setStatus('checking')
    setMessage('')
    try {
      const auth = await getAuthStatus()
      setServerAuth(auth)
      if (auth.required && !auth.authenticated) {
        setStatus('auth')
        setMessage('服务器已启用账户登录，请先在登录页登录。')
        return
      }
      setStatus('ok')
      setMessage('连接成功，可以正常读写数据。')
    } catch (error) {
      setStatus('failed')
      setMessage(error instanceof Error ? error.message : '连接失败')
    }
  }, [])

  useEffect(() => {
    // Show the current state once, using the already configured URL.
    const timer = globalThis.setTimeout(() => {
      void test()
    }, 0)
    return () => globalThis.clearTimeout(timer)
  }, [test])

  function save() {
    const next = withApiSuffix(normalize(baseUrl))
    if (next && !/^https?:\/\//i.test(next)) {
      notify('error', '地址必须以 http:// 或 https:// 开头')
      return
    }
    setRuntimeBaseUrl(next)
    setAccessToken(token)
    refreshConnection()
    setBaseUrl(next)
    notify('success', next ? '连接设置已保存' : '已恢复默认（同源）连接')
    void test()
  }

  const connection = describeConnection()

  return (
    <div className="connection-page">
      <header className="page-heading">
        <p className="eyebrow">Connection</p>
        <h1>连接设置</h1>
        <p className="lede">
          电脑端与手机端都连接同一台电脑后端，数据只保存在电脑上的 SQLite。
          手机不能使用 localhost，必须填写电脑的局域网地址。
        </p>
      </header>

      <section className="panel connection-panel">
        <dl className="meta-grid">
          <div>
            <dt>当前环境</dt>
            <dd>{environment === 'android' ? '手机 App' : '浏览器'}</dd>
          </div>
          <div>
            <dt>当前 API 地址</dt>
            <dd>{connection.baseUrl || '未设置'}</dd>
          </div>
        </dl>
        <p className="form-hint">{ENVIRONMENT_HINTS[environment]}</p>

        <div className="field">
          <label htmlFor="connection-base-url">服务器地址（含 /api/v1）</label>
          <input
            id="connection-base-url"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder="http://192.168.1.10:8000/api/v1"
            inputMode="url"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
          />
          <p className="form-hint">
            电脑端启动后运行 <code>ipconfig</code> 查看 IPv4 地址；同机浏览器测试可留空。
          </p>
        </div>

        <div className="field">
          <label htmlFor="connection-token">登录 token（通常由登录页保存）</label>
          <input
            id="connection-token"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="未启用可留空"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
          />
          <p className="form-hint">
            登录 token 只保存在本设备会话中；旧版共享口令仅用于兼容，不再作为用户身份。
          </p>
        </div>

        <div className="form-actions">
          <button type="button" className="button button-primary" onClick={save}>
            保存并测试
          </button>
          {token && (
            <button
              type="button"
              className="button button-ghost"
              onClick={() => {
                void logout()
                  .finally(() => {
                    setToken('')
                    setServerAuth(null)
                    notify('success', '已退出登录')
                    navigate('/login')
                  })
              }}
            >
              退出登录
            </button>
          )}
          <button
            type="button"
            className="button button-ghost"
            onClick={() => void test()}
            disabled={status === 'checking'}
          >
            {status === 'checking' ? '测试中…' : '重新测试'}
          </button>
        </div>

        {status === 'ok' && <Notice kind="success">{message}</Notice>}
        {status === 'failed' && <Notice kind="error">{message}</Notice>}
        {status === 'auth' && <Notice kind="error">{message}</Notice>}
        {serverAuth?.required && (
          <p className="form-hint">
            服务器访问控制：已启用（{serverAuth.authenticated ? '当前已登录' : '当前未登录'}）
          </p>
        )}
        {serverAuth && !serverAuth.required && (
          <p className="form-hint">服务器访问控制：未启用（仅建议在本机或可信局域网使用）</p>
        )}
        <p className="form-hint">
          <Link to="/login">登录账号</Link> · <Link to="/admin">成员与共享</Link> ·{' '}
          <Link to="/settings/local-db">本地数据库（7B）</Link>
        </p>
      </section>
    </div>
  )
}
