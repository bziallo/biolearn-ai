import { useState, type FormEvent } from 'react'

import type {
  ChapterInput,
  ChapterNode,
} from '../lib/api/chapters'
import {
  collectSubtreeIds,
  flattenTree,
} from '../lib/chapterTree'

interface ChapterFormProps {
  initial?: ChapterNode | null
  tree: ChapterNode[]
  defaultParentId?: string | null
  submitting: boolean
  onSubmit: (input: ChapterInput) => void
  onCancel: () => void
}

export function ChapterForm({
  initial,
  tree,
  defaultParentId = null,
  submitting,
  onSubmit,
  onCancel,
}: ChapterFormProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [parentId, setParentId] = useState(
    initial?.parent_id ?? defaultParentId ?? '',
  )
  const [nameError, setNameError] = useState('')

  const excludedIds = initial ? collectSubtreeIds(initial) : new Set<string>()
  const parentOptions = flattenTree(tree).filter(
    ({ node }) => !excludedIds.has(node.id),
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedName = name.trim()

    if (!trimmedName) {
      setNameError('请输入章节名称')
      return
    }
    if (trimmedName.length > 160) {
      setNameError('章节名称不能超过 160 个字符')
      return
    }

    onSubmit({
      name: trimmedName,
      description: description.trim(),
      parent_id: parentId || null,
    })
  }

  return (
    <form className="entity-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="chapter-name">
          章节名称 <span className="required">*</span>
        </label>
        <input
          id="chapter-name"
          value={name}
          onChange={(event) => {
            setName(event.target.value)
            if (nameError) {
              setNameError('')
            }
          }}
          maxLength={160}
          autoFocus
          aria-invalid={Boolean(nameError)}
          aria-describedby={nameError ? 'chapter-name-error' : undefined}
          placeholder="例如：细胞膜运输"
        />
        {nameError && (
          <p className="field-error" id="chapter-name-error">
            {nameError}
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="chapter-parent">父章节</label>
        <select
          id="chapter-parent"
          value={parentId}
          onChange={(event) => setParentId(event.target.value)}
        >
          <option value="">无（作为根章节）</option>
          {parentOptions.map(({ node, depth }) => (
            <option value={node.id} key={node.id}>
              {'— '.repeat(depth)}
              {node.name}
            </option>
          ))}
        </select>
        <p className="form-hint">
          编辑章节时不能选择自己或自己的后代，后端会再次校验循环引用。
        </p>
      </div>

      <div className="field">
        <label htmlFor="chapter-description">章节简介</label>
        <textarea
          id="chapter-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={4}
          maxLength={4000}
          placeholder="这个章节会覆盖哪些内容？"
        />
      </div>

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
          {submitting ? '保存中…' : '保存章节'}
        </button>
      </div>
    </form>
  )
}
