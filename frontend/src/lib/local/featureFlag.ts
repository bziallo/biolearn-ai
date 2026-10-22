export const LOCAL_DB_FLAG_KEY = 'biolearn.mobile_local_db'

/**
 * Default is remote FastAPI. Set VITE_MOBILE_LOCAL_DB=true at build time or
 * toggle the runtime key from the local database diagnostics page. 7B never
 * switches existing pages automatically.
 */
export function isLocalDbEnabled(): boolean {
  try {
    const runtime = window.localStorage.getItem(LOCAL_DB_FLAG_KEY)
    if (runtime === '1') {
      return true
    }
    if (runtime === '0') {
      return false
    }
  } catch {
    // storage disabled: fall back to build flag
  }
  return import.meta.env.VITE_MOBILE_LOCAL_DB === 'true'
}

export function setLocalDbEnabled(enabled: boolean): void {
  try {
    window.localStorage.setItem(LOCAL_DB_FLAG_KEY, enabled ? '1' : '0')
  } catch {
    // The UI will still reflect the current session's in-memory use.
  }
}

export function localDbFlagSource(): 'runtime' | 'build' | 'default' {
  try {
    const runtime = window.localStorage.getItem(LOCAL_DB_FLAG_KEY)
    if (runtime === '1' || runtime === '0') {
      return 'runtime'
    }
  } catch {
    // ignore
  }
  return import.meta.env.VITE_MOBILE_LOCAL_DB === 'true' ? 'build' : 'default'
}
