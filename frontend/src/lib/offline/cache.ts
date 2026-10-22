/**
 * Small offline cache for read-only snapshots.
 *
 * The Android WebView has IndexedDB; browsers without it (and jsdom tests) fall
 * back to localStorage. Only public course metadata is stored here. Auth tokens
 * are never written to this store, and the whole store is cleared on login /
 * logout so two accounts on one device cannot read each other's cached data.
 */

const DB_NAME = 'biolearn-offline'
const DB_VERSION = 1
const STORE = 'snapshots'
const FALLBACK_PREFIX = 'biolearn.offline.v1.'

export interface CachedValue<T> {
  data: T
  savedAt: string
}

function fallbackKey(key: string): string {
  return `${FALLBACK_PREFIX}${key}`
}

function openDatabase(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === 'undefined') {
    return Promise.resolve(null)
  }
  return new Promise((resolve) => {
    let request: IDBOpenDBRequest
    try {
      request = indexedDB.open(DB_NAME, DB_VERSION)
    } catch {
      resolve(null)
      return
    }
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE)
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => resolve(null)
    request.onblocked = () => resolve(null)
  })
}

export async function readOfflineCache<T>(
  key: string,
): Promise<CachedValue<T> | null> {
  const db = await openDatabase()
  if (db) {
    try {
      const value = await new Promise<CachedValue<T> | null>((resolve) => {
        const transaction = db.transaction(STORE, 'readonly')
        const request = transaction.objectStore(STORE).get(key)
        request.onsuccess = () =>
          resolve((request.result as CachedValue<T> | undefined) ?? null)
        request.onerror = () => resolve(null)
      })
      db.close()
      if (value) {
        return value
      }
    } catch {
      db.close()
    }
  }
  try {
    const raw = localStorage.getItem(fallbackKey(key))
    if (!raw) {
      return null
    }
    return JSON.parse(raw) as CachedValue<T>
  } catch {
    return null
  }
}

export async function writeOfflineCache<T>(
  key: string,
  data: T,
): Promise<void> {
  const value: CachedValue<T> = {
    data,
    savedAt: new Date().toISOString(),
  }
  const db = await openDatabase()
  if (db) {
    try {
      await new Promise<void>((resolve) => {
        const transaction = db.transaction(STORE, 'readwrite')
        transaction.objectStore(STORE).put(value, key)
        transaction.oncomplete = () => resolve()
        transaction.onerror = () => resolve()
        transaction.onabort = () => resolve()
      })
      db.close()
      return
    } catch {
      db.close()
    }
  }
  try {
    localStorage.setItem(fallbackKey(key), JSON.stringify(value))
  } catch {
    // Quota or disabled storage: caching is best-effort.
  }
}

export async function clearOfflineCache(): Promise<void> {
  if (typeof indexedDB !== 'undefined') {
    try {
      await new Promise<void>((resolve) => {
        const request = indexedDB.deleteDatabase(DB_NAME)
        request.onsuccess = () => resolve()
        request.onerror = () => resolve()
        request.onblocked = () => resolve()
      })
    } catch {
      // Ignore and still clear the fallback.
    }
  }
  try {
    const keys: string[] = []
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index)
      if (key?.startsWith(FALLBACK_PREFIX)) {
        keys.push(key)
      }
    }
    keys.forEach((key) => localStorage.removeItem(key))
  } catch {
    // Ignore storage errors.
  }
}
