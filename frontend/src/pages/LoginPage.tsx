import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Notice } from '../components/Notice'
import { login } from '../lib/api'
import { getErrorMessage } from '../lib/api/client'

export function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username.trim(), password)
      navigate('/')
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <header className="page-heading">
        <p className="eyebrow">Account</p>
        <h1>登录 BioLearn AI</h1>
        <p className="lede">使用 Owner 或受邀账号登录。共享访问口令只用于旧版本兼容，不再作为用户身份。</p>
      </header>

      <form className="panel form-panel" onSubmit={(event) => void submit(event)}>
        {error && <Notice kind="error">{error}</Notice>}
        <div className="field">
          <label htmlFor="login-username">用户名</label>
          <input
            id="login-username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="login-password">密码</label>
          <input
            id="login-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <div className="form-actions">
          <button type="submit" className="button button-primary" disabled={busy}>
            {busy ? '登录中…' : '登录'}
          </button>
          <Link className="button button-ghost" to="/">
            返回首页
          </Link>
        </div>
      </form>
    </div>
  )
}
