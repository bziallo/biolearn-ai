import { apiRequest } from './client'
import { setAccessToken } from './connection'

export interface AuthUser {
  id: string
  username: string
  display_name: string
  role: 'owner' | 'user'
  status: 'active' | 'disabled'
  created_at: string
  last_login_at: string | null
}

export interface AuthStatus {
  required: boolean
  authenticated: boolean
}

export interface InvitationCreated {
  id: string
  note: string
  role: string
  created_at: string
  expires_at: string
  used_at: string | null
  revoked_at: string | null
  invitation_token: string | null
}

export interface SubjectGrant {
  id: string
  subject_id: string
  grantee_user_id: string
  permission: string
  created_at: string
}

export function login(username: string, password: string): Promise<{ token: string; user: AuthUser }> {
  return apiRequest('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  }).then((result) => {
    const data = result as { token: string; user: AuthUser }
    setAccessToken(data.token)
    return data
  })
}

export function logout(): Promise<{ ok: boolean }> {
  return apiRequest('/auth/logout', { method: 'POST' }).finally(() => {
    setAccessToken('')
  }) as Promise<{ ok: boolean }>
}

export function me(): Promise<AuthUser> {
  return apiRequest('/auth/me')
}

export function acceptInvitation(payload: {
  token: string
  username: string
  password: string
  display_name?: string
}): Promise<{ token: string; user: AuthUser }> {
  return apiRequest('/auth/invitations/accept', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then((result) => {
    const data = result as { token: string; user: AuthUser }
    setAccessToken(data.token)
    return data
  })
}

export function listUsers(): Promise<AuthUser[]> {
  return apiRequest('/admin/users')
}

export function setUserStatus(id: string, status: 'active' | 'disabled'): Promise<AuthUser> {
  return apiRequest(`/admin/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

export function listInvitations(): Promise<InvitationCreated[]> {
  return apiRequest('/admin/invitations')
}

export function createInvitation(note = ''): Promise<InvitationCreated> {
  return apiRequest('/admin/invitations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note }),
  })
}

export function revokeInvitation(id: string): Promise<void> {
  return apiRequest(`/admin/invitations/${id}`, { method: 'DELETE' })
}

export function listGrants(): Promise<SubjectGrant[]> {
  return apiRequest('/admin/grants')
}

export function createGrant(payload: {
  subject_id: string
  grantee_user_id: string
  permission: string
}): Promise<SubjectGrant> {
  return apiRequest('/admin/grants', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function revokeGrant(id: string): Promise<void> {
  return apiRequest(`/admin/grants/${id}`, { method: 'DELETE' })
}

/** Server auth state used by the connection settings screen. */
export function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return apiRequest('/auth', { signal }, 8_000)
}
