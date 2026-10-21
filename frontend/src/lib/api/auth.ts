import { apiRequest } from './client'

export interface AuthStatus {
  required: boolean
  authenticated: boolean
}

/**
 * Ask the configured server whether it needs a shared access token.
 * `/api/v1/auth` is deliberately public so the settings screen can explain
 * the state before a token has been entered.
 */
export function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return apiRequest<AuthStatus>('/auth', { signal }, 8_000)
}
