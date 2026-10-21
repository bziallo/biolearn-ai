function resolveBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim()
  if (configured) {
    return configured.replace(/\/+$/, '')
  }
  // Same-origin deployment: FastAPI serves the built SPA on one port, so the
  // API lives under the same origin. Vite dev sets a fixed URL via .env.
  if (
    typeof window !== 'undefined' &&
    typeof window.location?.origin === 'string' &&
    window.location.origin.startsWith('http')
  ) {
    return `${window.location.origin}/api/v1`
  }
  return 'http://127.0.0.1:8000/api/v1'
}

export const API_BASE_URL = resolveBaseUrl()

export class ApiError extends Error {
  readonly status?: number
  readonly detail?: unknown

  constructor(message: string, status?: number, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 8_000,
): Promise<T> {
  const controller = new AbortController()
  const abortFromCaller = () => controller.abort()

  if (init.signal) {
    if (init.signal.aborted) {
      controller.abort()
    } else {
      init.signal.addEventListener('abort', abortFromCaller)
    }
  }

  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs)

  try {
    const headers = new Headers(init.headers)
    if (!headers.has('Accept')) {
      headers.set('Accept', 'application/json')
    }

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    })

    if (!response.ok) {
      const text = await response.text()
      let message = `请求失败（${response.status}）`
      let detail: unknown

      if (text) {
        try {
          const body = JSON.parse(text) as { detail?: unknown }
          detail = body.detail
          if (typeof detail === 'string') {
            message = detail
          } else if (
            detail &&
            typeof detail === 'object' &&
            'message' in detail &&
            typeof detail.message === 'string'
          ) {
            message = detail.message
          }
        } catch {
          // Keep the status-based fallback when the body is not JSON.
        }
      }

      throw new ApiError(message, response.status, detail)
    }

    if (response.status === 204) {
      return undefined as T
    }

    const text = await response.text()
    if (!text) {
      return undefined as T
    }

    return JSON.parse(text) as T
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    if (controller.signal.aborted) {
      throw new ApiError('请求超时或已取消')
    }
    throw new ApiError(
      error instanceof Error ? error.message : '网络请求失败',
    )
  } finally {
    globalThis.clearTimeout(timeoutId)
    init.signal?.removeEventListener('abort', abortFromCaller)
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  return '发生未知错误'
}

export function getErrorDetail(
  error: unknown,
): Record<string, unknown> | null {
  if (
    error instanceof ApiError &&
    error.detail &&
    typeof error.detail === 'object'
  ) {
    return error.detail as Record<string, unknown>
  }
  return null
}
