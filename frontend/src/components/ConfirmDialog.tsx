import { useEffect, useState } from 'react'

import { Modal } from './Modal'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  busy?: boolean
  acknowledgement?: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  acknowledgement,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [acknowledged, setAcknowledged] = useState(false)

  useEffect(() => {
    if (open) {
      setAcknowledged(false)
    }
  }, [open])

  return (
    <Modal
      open={open}
      title={title}
      busy={busy}
      onClose={onCancel}
    >
      <p className="confirm-description">{description}</p>
      {acknowledgement && (
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
          />
          <span>{acknowledgement}</span>
        </label>
      )}
      <div className="form-actions">
        <button
          type="button"
          className="button button-ghost"
          onClick={onCancel}
          disabled={busy}
        >
          取消
        </button>
        <button
          type="button"
          className="button button-danger"
          onClick={onConfirm}
          disabled={busy || (Boolean(acknowledgement) && !acknowledged)}
        >
          {busy ? '处理中…' : confirmLabel}
        </button>
      </div>
    </Modal>
  )
}
