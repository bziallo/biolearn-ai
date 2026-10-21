import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { Notice } from '../components/Notice'
import { acceptInvitation } from '../lib/api'
import { getErrorMessage } from '../lib/api/client'

export function JoinPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [token, setToken] = useState(params.get('token') ?? '')
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (password.length < 10) {
      setError('密码至少需要 10 个字符')
      return
    }
    if (password !== confirm) {
      setError('两次输入的密码不一致')
      return
    }
    setBusy(true)
    try {
      await acceptInvitation({
        token: token.trim(),
        username: username.trim(),
        password,
        display_name: displayName.trim(),
      })
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
        <p className="eyebrow">Invitation</p>
        <h1>接受邀请</h1>
        <p className="lede">邀请链接只能使用一次。设置用户名和密码后即可进入被授权的学科。</p>
      </header>

      <form className="panel form-panel" onSubmit={(event) => void submit(event)}>
        {error && <Notice kind="error">{error}</Notice>}
        <div className="field">
          <label htmlFor="join-token">邀请令牌</label>
          <input
            id="join-token"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="join-username">用户名</label>
          <input
            id="join-username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="join-display">显示名（可选）</label>
          <input
            id="join-display"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="join-password">密码（至少 10 位）</label>
          <input
            id="join-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="join-confirm">确认密码</label>
          <input
            id="join-confirm"
            type="password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            autoComplete="new-password"
            required
          />
        </div>
        <div className="form-actions">
          <button type="submit" className="button button-primary" disabled={busy}>
            {busy ? '创建中…' : '创建账号并登录'}
          </button>
          <Link className="button button-ghost" to="/login">
            已有账号
          </Link>
        </div>
      </form>
    </div>
  )
}
