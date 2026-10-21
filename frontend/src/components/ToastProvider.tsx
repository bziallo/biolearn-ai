import { useCallback, useRef, useState, type ReactNode } from 'react'

import {
  ToastContext,
  type ToastKind,
} from '../lib/toast-context'

interface ToastItem {
  id: number
  kind: ToastKind
  message: string
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)

  const notify = useCallback((kind: ToastKind, message: string) => {
    const id = ++nextId.current
    setToasts((items) => [...items, { id, kind, message }])
    globalThis.setTimeout(() => {
      setToasts((items) => items.filter((item) => item.id !== id))
    }, 4200)
  }, [])

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="toast-viewport" aria-live="polite">
        {toasts.map((toast) => (
          <div
            className={`toast toast-${toast.kind}`}
            key={toast.id}
            role={toast.kind === 'error' ? 'alert' : 'status'}
          >
            <span>{toast.message}</span>
            <button
              type="button"
              aria-label="关闭提示"
              onClick={() =>
                setToasts((items) =>
                  items.filter((item) => item.id !== toast.id),
                )
              }
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
