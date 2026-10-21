import type { ReactNode } from 'react'

interface NoticeProps {
  kind?: 'info' | 'success' | 'error'
  children: ReactNode
  onDismiss?: () => void
}

export function Notice({
  kind = 'info',
  children,
  onDismiss,
}: NoticeProps) {
  return (
    <div
      className={`notice notice-${kind}`}
      role={kind === 'error' ? 'alert' : 'status'}
    >
      <span>{children}</span>
      {onDismiss && (
        <button
          type="button"
          className="notice-close"
          aria-label="关闭提示"
          onClick={onDismiss}
        >
          ×
        </button>
      )}
    </div>
  )
}
