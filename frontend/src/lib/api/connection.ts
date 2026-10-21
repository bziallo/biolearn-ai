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

function isAndroidShell(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const { protocol, hostname } = window.location
  if (protocol === 'capacitor:') {
    return true
  }
  // Capacitor serves the bundle from https://localhost: that exact origin can
  // never be a valid backend address, so treat it as the native shell too.
  // This must not depend on injected bridges, which are absent at module load.
  if (protocol === 'android-app:' || (protocol === 'https:' && hostname === 'localhost')) {
    return true
  }
  return isCapacitorNative()
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
  // VITE_API_BASE_URL is the browser/dev value from the root .env and must
  // never leak into the APK (it points at the developer machine's loopback).
  // The Android shell only honours VITE_DEFAULT_API_BASE_URL, which is set
  // explicitly for a LAN or remote deployment build.
  const explicit = trimBase(import.meta.env.VITE_DEFAULT_API_BASE_URL)
  if (isAndroidShell()) {
    return explicit
  }
  return trimBase(import.meta.env.VITE_API_BASE_URL) || explicit
}

export function currentRuntimeBaseUrl(): string {
  return readStorage(RUNTIME_KEY)
}

export function resolveApiBaseUrl(): string {
  const runtime = currentRuntimeBaseUrl()
  if (runtime) {
    return runtime
  }
  // A build-time default is an explicit operator decision (LAN server or a
  // deployment domain) and is valid in the Android shell too. Only the
  // implicit same-origin fallback is unsafe there, because the shell origin is
  // https://localhost rather than a backend.
  const baked = buildTimeDefault()
  if (baked) {
    return baked
  }
  if (isAndroidShell()) {
    return ''
  }
  if (
    typeof window !== 'undefined' &&
    typeof window.location?.origin === 'string' &&
    window.location.origin.startsWith('http')
  ) {
    return `${window.location.origin}/api/v1`
  }
  // No implicit loopback: a packaged/embedded client must never assume the
  // developer machine. The UI asks the user to configure a server instead.
  return ''
}

export function setRuntimeBaseUrl(value: string): void {
  writeStorage(RUNTIME_KEY, trimBase(value))
}

function readSessionValue(key: string): string {
  try {
    return typeof window === 'undefined'
      ? ''
      : (window.sessionStorage.getItem(key) ?? '')
  } catch {
    return ''
  }
}

function writeSessionValue(key: string, value: string): void {
  try {
    if (typeof window === 'undefined') {
      return
    }
    if (value) {
      window.sessionStorage.setItem(key, value)
    } else {
      window.sessionStorage.removeItem(key)
    }
  } catch {
    // Storage can be disabled; the session simply will not persist.
  }
}

export function getAccessToken(): string {
  // Session storage limits persistence on shared browsers; Android release
  // keeps the value inside the app WebView sandbox.
  return readSessionValue(TOKEN_KEY) || readStorage(TOKEN_KEY)
}

export function setAccessToken(value: string): void {
  const next = value.trim()
  writeSessionValue(TOKEN_KEY, next)
  writeStorage(TOKEN_KEY, '')
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
  if (baked) {
    return { baseUrl: baked, environment, configured: true, source: 'build' }
  }
  if (environment === 'android') {
    return { baseUrl: '', environment, configured: false, source: 'unset' }
  }
  return {
    baseUrl: resolveApiBaseUrl(),
    environment,
    configured: true,
    source: 'same-origin',
  }
}
