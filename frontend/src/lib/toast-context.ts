import { createContext } from 'react'

export type ToastKind = 'success' | 'error' | 'info'

export interface ToastContextValue {
  notify: (kind: ToastKind, message: string) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)
