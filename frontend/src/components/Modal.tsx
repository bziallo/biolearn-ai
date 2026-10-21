import {
  useEffect,
  useId,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

interface ModalProps {
  open: boolean
  title: string
  busy?: boolean
  onClose: () => void
  children: ReactNode
}

export function Modal({
  open,
  title,
  busy = false,
  onClose,
  children,
}: ModalProps) {
  const titleId = useId()

  useEffect(() => {
    if (!open) {
      return
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) {
        onClose()
      }
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, busy, onClose])

  if (!open) {
    return null
  }

  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) {
          onClose()
        }
      }}
    >
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="modal-header">
          <h2 id={titleId}>{title}</h2>
          <button
            type="button"
            className="modal-close"
            aria-label="关闭对话框"
            onClick={onClose}
            disabled={busy}
          >
            ×
          </button>
        </header>
        <div className="modal-body">{children}</div>
      </section>
    </div>,
    document.body,
  )
}
