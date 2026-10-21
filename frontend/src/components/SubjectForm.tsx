import { useState, type FormEvent } from 'react'

import type { Subject, SubjectInput } from '../lib/api/subjects'

const ICONS = ['🧬', '🦠', '🧫', '🧪', '🛡️', '❤️', '💻', '🌱', '💊', '📚']

interface SubjectFormProps {
  initial?: Subject | null
  submitting: boolean
  onSubmit: (input: SubjectInput) => void
  onCancel: () => void
}

export function SubjectForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: SubjectFormProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [color, setColor] = useState(initial?.color ?? '#5fe3a6')
  const [icon, setIcon] = useState(initial?.icon ?? '🧬')
  const [nameError, setNameError] = useState('')

  const iconOptions =
    initial?.icon && !ICONS.includes(initial.icon)
      ? [initial.icon, ...ICONS]
      : ICONS

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedName = name.trim()

    if (!trimmedName) {
      setNameError('请输入学科名称')
      return
    }
    if (trimmedName.length > 120) {
      setNameError('学科名称不能超过 120 个字符')
      return
    }

    onSubmit({
      name: trimmedName,
      description: description.trim(),
      color,
      icon: icon || null,
    })
  }

  return (
    <form className="entity-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="subject-name">
          学科名称 <span className="required">*</span>
        </label>
        <input
          id="subject-name"
          value={name}
          onChange={(event) => {
            setName(event.target.value)
            if (nameError) {
              setNameError('')
            }
          }}
          maxLength={120}
          autoFocus
          aria-invalid={Boolean(nameError)}
          aria-describedby={nameError ? 'subject-name-error' : undefined}
          placeholder="例如：分子生物学"
        />
        {nameError && (
          <p className="field-error" id="subject-name-error">
            {nameError}
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="subject-description">学科简介</label>
        <textarea
          id="subject-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={4}
          maxLength={4000}
          placeholder="这门学科关注什么？之后会显示在学科卡片上。"
        />
      </div>

      <div className="form-row">
        <div className="field">
          <label htmlFor="subject-color">展示颜色</label>
          <div className="color-field">
            <input
              id="subject-color"
              type="color"
              value={color}
              onChange={(event) => setColor(event.target.value)}
            />
            <code>{color}</code>
          </div>
        </div>

        <div className="field">
          <label htmlFor="subject-icon">图标</label>
          <select
            id="subject-icon"
            value={icon}
            onChange={(event) => setIcon(event.target.value)}
          >
            <option value="">无图标</option>
            {iconOptions.map((option) => (
              <option value={option} key={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="form-hint">
        颜色和图标会显示在学科卡片与章节详情中，之后仍可修改。
      </p>

      <div className="form-actions">
        <button
          type="button"
          className="button button-ghost"
          onClick={onCancel}
          disabled={submitting}
        >
          取消
        </button>
        <button
          type="submit"
          className="button button-primary"
          disabled={submitting}
        >
          {submitting ? '保存中…' : '保存学科'}
        </button>
      </div>
    </form>
  )
}
