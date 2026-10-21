import {
  getAccessToken,
  resolveApiBaseUrl,
} from './connection'

export let API_BASE_URL = resolveApiBaseUrl()

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
  const baseUrl = resolveApiBaseUrl()
  if (!baseUrl) {
    throw new ApiError(
      '尚未连接服务器：请打开“连接设置”，填写电脑后端的局域网地址，例如 http://192.168.1.10:8000/api/v1',
    )
  }
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
    const token = getAccessToken()
    if (token && !headers.has('X-BioLearn-Token')) {
      headers.set('X-BioLearn-Token', token)
    }

    let response: Response
    try {
      response = await fetch(`${baseUrl}${path}`, {
        ...init,
        headers,
        signal: controller.signal,
      })
    } catch (networkError) {
      if (controller.signal.aborted) {
        throw networkError
      }
      throw new ApiError(
        `无法连接服务器 ${baseUrl}。请确认电脑端后端已启动、手机与电脑在同一 Wi-Fi，并检查局域网监听与防火墙设置。`,
      )
    }

    if (response.status === 401) {
      throw new ApiError(
        '需要访问口令：请在“连接设置”中填写与电脑端一致的共享口令',
        401,
      )
    }

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

/** Re-read the connection settings after the user edits them. */
export function refreshConnection(): void {
  const next = resolveApiBaseUrl()
  if (next) {
    // Keep the exported constant useful for diagnostics in settings screens.
    API_BASE_URL = next
  }
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
