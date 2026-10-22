import { useEffect, useState } from 'react'

import { ApiError } from '../api/client'

export function isOfflineError(error: unknown): boolean {
  if (error instanceof ApiError) {
    // status is undefined for DNS / refused connection / timeout / unset base.
    return error.status === undefined
  }
  return error instanceof TypeError
}

export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine,
  )

  useEffect(() => {
    const markOnline = () => setOnline(true)
    const markOffline = () => setOnline(false)
    window.addEventListener('online', markOnline)
    window.addEventListener('offline', markOffline)
    return () => {
      window.removeEventListener('online', markOnline)
      window.removeEventListener('offline', markOffline)
    }
  }, [])

  return online
}
