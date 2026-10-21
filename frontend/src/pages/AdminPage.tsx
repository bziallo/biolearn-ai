import { useCallback, useEffect, useState } from 'react'

import { Notice } from '../components/Notice'
import {
  createGrant,
  createInvitation,
  listGrants,
  listInvitations,
  listSubjects,
  listUsers,
  revokeGrant,
  revokeInvitation,
  setUserStatus,
  type AuthUser,
  type InvitationCreated,
  type Subject,
  type SubjectGrant,
} from '../lib/api'
import { getErrorMessage } from '../lib/api/client'
import { useToast } from '../lib/useToast'

export function AdminPage() {
  const { notify } = useToast()
  const [users, setUsers] = useState<AuthUser[]>([])
  const [invitations, setInvitations] = useState<InvitationCreated[]>([])
  const [grants, setGrants] = useState<SubjectGrant[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [inviteNote, setInviteNote] = useState('')
  const [createdLink, setCreatedLink] = useState('')
  const [grantUser, setGrantUser] = useState('')
  const [grantSubject, setGrantSubject] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      const [nextUsers, nextInvites, nextGrants, nextSubjects] = await Promise.all([
        listUsers(),
        listInvitations(),
        listGrants(),
        listSubjects(),
      ])
      setUsers(nextUsers)
      setInvitations(nextInvites)
      setGrants(nextGrants)
      setSubjects(nextSubjects)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function invite() {
    setBusy(true)
    try {
      const created = await createInvitation(inviteNote)
      if (created.invitation_token) {
        setCreatedLink(`${window.location.origin}/join?token=${created.invitation_token}`)
      }
      setInviteNote('')
      notify('success', '邀请已创建；链接只显示一次')
      await load()
    } catch (err) {
      notify('error', getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function grant() {
    if (!grantUser || !grantSubject) {
      notify('error', '请选择用户和学科')
      return
    }
    setBusy(true)
    try {
      await createGrant({
        grantee_user_id: grantUser,
        subject_id: grantSubject,
        permission: 'read',
      })
      notify('success', '授权已保存')
      await load()
    } catch (err) {
      notify('error', getErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-page">
      <header className="page-heading">
        <p className="eyebrow">Owner</p>
        <h1>成员与共享</h1>
        <p className="lede">邀请可信用户，并只把指定学科共享给他们。普通用户默认只读并只能查看自己的练习记录。</p>
      </header>

      {error && <Notice kind="error">{error}</Notice>}

      <section className="panel">
        <h2>邀请新成员</h2>
        <div className="field">
          <label htmlFor="invite-note">备注（可选）</label>
          <input
            id="invite-note"
            value={inviteNote}
            onChange={(event) => setInviteNote(event.target.value)}
            placeholder="例如：实验室同学"
          />
        </div>
        <div className="form-actions">
          <button type="button" className="button button-primary" onClick={() => void invite()} disabled={busy}>
            生成一次性邀请链接
          </button>
        </div>
        {createdLink && (
          <Notice kind="success">
            <div>邀请链接（只显示一次，请通过可信渠道发送）：</div>
            <code className="invite-link">{createdLink}</code>
            <button
              type="button"
              className="text-button"
              onClick={() => {
                void navigator.clipboard?.writeText(createdLink)
                notify('success', '已复制')
              }}
            >
              复制链接
            </button>
          </Notice>
        )}
        {invitations.length > 0 && (
          <ul className="admin-list">
            {invitations.map((item) => (
              <li key={item.id}>
                <span>
                  {item.note || '未命名邀请'} · {new Date(item.expires_at).toLocaleString('zh-CN')}
                  {item.used_at ? ' · 已使用' : item.revoked_at ? ' · 已撤销' : ''}
                </span>
                {!item.used_at && !item.revoked_at && (
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      void revokeInvitation(item.id)
                        .then(load)
                        .catch((err) => notify('error', getErrorMessage(err)))
                    }
                  >
                    撤销
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h2>成员</h2>
        <ul className="admin-list">
          {users.map((user) => (
            <li key={user.id}>
              <span>
                {user.display_name || user.username} · @{user.username} · {user.role} · {user.status}
              </span>
              {user.role !== 'owner' && (
                <button
                  type="button"
                  className="text-button"
                  onClick={() =>
                    void setUserStatus(
                      user.id,
                      user.status === 'active' ? 'disabled' : 'active',
                    )
                      .then(load)
                      .catch((err) => notify('error', getErrorMessage(err)))
                  }
                >
                  {user.status === 'active' ? '停用' : '启用'}
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>共享授权</h2>
        <div className="inline-form">
          <select value={grantUser} onChange={(event) => setGrantUser(event.target.value)}>
            <option value="">选择用户</option>
            {users
              .filter((user) => user.role !== 'owner' && user.status === 'active')
              .map((user) => (
                <option key={user.id} value={user.id}>
                  {user.display_name || user.username}
                </option>
              ))}
          </select>
          <select value={grantSubject} onChange={(event) => setGrantSubject(event.target.value)}>
            <option value="">选择学科</option>
            {subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))}
          </select>
          <button type="button" className="button button-primary" onClick={() => void grant()} disabled={busy}>
            授权只读
          </button>
        </div>
        {grants.length === 0 ? (
          <p className="form-hint">尚未共享任何学科。</p>
        ) : (
          <ul className="admin-list">
            {grants.map((item) => {
              const user = users.find((candidate) => candidate.id === item.grantee_user_id)
              const subject = subjects.find((candidate) => candidate.id === item.subject_id)
              return (
                <li key={item.id}>
                  <span>
                    {subject?.name ?? item.subject_id} → {user?.username ?? item.grantee_user_id}（{item.permission}）
                  </span>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      void revokeGrant(item.id)
                        .then(load)
                        .catch((err) => notify('error', getErrorMessage(err)))
                    }
                  >
                    撤销
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
