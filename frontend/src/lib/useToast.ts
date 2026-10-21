import { useContext } from 'react'

import { ToastContext } from './toast-context'

export function useToast() {
  const value = useContext(ToastContext)
  if (!value) {
    throw new Error('useToast 必须在 ToastProvider 内使用')
  }
  return value
}
