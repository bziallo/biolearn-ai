/**
 * Connection settings shared by the browser build and the Android APK.
 *
 * Resolution order (first match wins):
 * 1. VITE_API_BASE_URL / VITE_DEFAULT_API_BASE_URL baked in at build time
 *    (development and desktop production builds keep their own value);
 * 2. a runtime override saved in the app settings screen (localStorage);
 * 3. the same origin, when the SPA is served by FastAPI or by the Android shell.
 *
 * The Android shell loads the bundle from https://localhost, which is *not* a
 * server, so it never falls back to the device localhost. When nothing is
 * configured the APK shows a clear "not connected" state instead of silently
 * failing.
 */

export type ClientEnvironment = 'browser' | 'android'

const RUNTIME_KEY = 'biolearn.api_base_url'
const TOKEN_KEY = 'biolearn.access_token'

export function isAndroidShell(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const { protocol, hostname } = window.location
  return (
    protocol === 'capacitor:' ||
    (protocol === 'https:' && hostname === 'localhost' && isCapacitorNative())
  )
}

function isCapacitorNative(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const scope = window as unknown as {
    Capacitor?: { isNativePlatform?: () => boolean }
    androidBridge?: unknown
  }
  return Boolean(
    scope.androidBridge ||
      scope.Capacitor?.isNativePlatform?.() === true,
  )
}

function trimBase(value: string | null | undefined): string {
  return (value ?? '').trim().replace(/\/+$/, '')
}

function readStorage(key: string): string {
  try {
    return typeof window === 'undefined'
      ? ''
      : trimBase(window.localStorage.getItem(key))
  } catch {
    return ''
  }
}

function writeStorage(key: string, value: string): void {
  try {
    if (typeof window === 'undefined') {
      return
    }
    if (value) {
      window.localStorage.setItem(key, value)
    } else {
      window.localStorage.removeItem(key)
    }
  } catch {
    // Storage can be disabled; the setting simply will not persist.
  }
}

function buildTimeDefault(): string {
  const explicit = trimBase(
    import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_DEFAULT_API_BASE_URL,
  )
  return explicit
}

export function currentRuntimeBaseUrl(): string {
  return readStorage(RUNTIME_KEY)
}

export function resolveApiBaseUrl(): string {
  const runtime = currentRuntimeBaseUrl()
  if (runtime) {
    return runtime
  }
  const baked = buildTimeDefault()
  if (baked && !isAndroidShell()) {
    return baked
  }
  if (isAndroidShell()) {
    // Never treat the packaged asset origin as the backend.
    return ''
  }
  if (
    typeof window !== 'undefined' &&
    typeof window.location?.origin === 'string' &&
    window.location.origin.startsWith('http')
  ) {
    return `${window.location.origin}/api/v1`
  }
  return baked || 'http://127.0.0.1:8000/api/v1'
}

export function setRuntimeBaseUrl(value: string): void {
  writeStorage(RUNTIME_KEY, trimBase(value))
}

export function getAccessToken(): string {
  return readStorage(TOKEN_KEY)
}

export function setAccessToken(value: string): void {
  writeStorage(TOKEN_KEY, value.trim())
}

export function clientEnvironment(): ClientEnvironment {
  return isAndroidShell() ? 'android' : 'browser'
}

export function describeConnection(): {
  baseUrl: string
  environment: ClientEnvironment
  configured: boolean
  source: 'runtime' | 'build' | 'same-origin' | 'unset'
} {
  const runtime = currentRuntimeBaseUrl()
  const baked = buildTimeDefault()
  const environment = clientEnvironment()
  if (runtime) {
    return { baseUrl: runtime, environment, configured: true, source: 'runtime' }
  }
  if (environment === 'android') {
    return { baseUrl: '', environment, configured: Boolean(baked), source: baked ? 'build' : 'unset' }
  }
  if (baked) {
    return { baseUrl: baked, environment, configured: true, source: 'build' }
  }
  return {
    baseUrl: resolveApiBaseUrl(),
    environment,
    configured: true,
    source: 'same-origin',
  }
}
