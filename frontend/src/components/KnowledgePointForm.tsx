import { useState, type FormEvent } from 'react'

import type {
  KnowledgePointNode,
  KnowledgePointType,
} from '../lib/api/knowledge'
import { knowledgeTypeLabels } from '../lib/format'
import {
  collectPointSubtreeIds,
  flattenKnowledgeTree,
} from '../lib/knowledgeTree'

export interface KnowledgeFormValues {
  name: string
  type: KnowledgePointType
  explanation: string
  core_points: string[]
  conditions: string | null
  parent_id: string | null
}

interface KnowledgePointFormProps {
  mode: 'create' | 'edit'
  initial?: KnowledgePointNode | null
  tree: KnowledgePointNode[]
  defaultParentId?: string | null
  submitting: boolean
  onSubmit: (values: KnowledgeFormValues) => void
  onCancel: () => void
}

const TYPES = Object.keys(knowledgeTypeLabels) as KnowledgePointType[]

export function KnowledgePointForm({
  mode,
  initial,
  tree,
  defaultParentId = null,
  submitting,
  onSubmit,
  onCancel,
}: KnowledgePointFormProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [type, setType] = useState<KnowledgePointType>(
    initial?.type ?? 'basic_concept',
  )
  const [explanation, setExplanation] = useState(initial?.explanation ?? '')
  const [corePoints, setCorePoints] = useState(
    (initial?.core_points ?? []).join('\n'),
  )
  const [conditions, setConditions] = useState(initial?.conditions ?? '')
  const [parentId, setParentId] = useState(
    initial?.parent_id ?? defaultParentId ?? '',
  )
  const [nameError, setNameError] = useState('')
  const [explanationError, setExplanationError] = useState('')

  const excluded = initial
    ? collectPointSubtreeIds(initial)
    : new Set<string>()
  const parentOptions = flattenKnowledgeTree(tree).filter(
    ({ node }) => !excluded.has(node.id),
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim()) {
      setNameError('请输入知识点名称')
      return
    }
    if (!explanation.trim()) {
      setExplanationError('请输入知识点解释')
      return
    }
    onSubmit({
      name: name.trim(),
      type,
      explanation: explanation.trim(),
      core_points: corePoints
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
      conditions: conditions.trim() || null,
      parent_id: parentId || null,
    })
  }

  return (
    <form className="entity-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="knowledge-name">
          知识点名称 <span className="required">*</span>
        </label>
        <input
          id="knowledge-name"
          value={name}
          onChange={(event) => {
            setName(event.target.value)
            setNameError('')
          }}
          maxLength={300}
          autoFocus
          aria-invalid={Boolean(nameError)}
          placeholder="例如：蛋白质一级结构"
        />
        {nameError && <p className="field-error">{nameError}</p>}
      </div>

      <div className="form-row">
        <div className="field">
          <label htmlFor="knowledge-type">类型</label>
          <select
            id="knowledge-type"
            value={type}
            onChange={(event) =>
              setType(event.target.value as KnowledgePointType)
            }
          >
            {TYPES.map((item) => (
              <option value={item} key={item}>
                {knowledgeTypeLabels[item]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="knowledge-parent">父知识点</label>
          <select
            id="knowledge-parent"
            value={parentId}
            onChange={(event) => setParentId(event.target.value)}
          >
            <option value="">作为根知识点</option>
            {parentOptions.map(({ node, depth }) => (
              <option value={node.id} key={node.id}>
                {'— '.repeat(depth)}
                {node.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="field">
        <label htmlFor="knowledge-explanation">
          解释 <span className="required">*</span>
        </label>
        <textarea
          id="knowledge-explanation"
          value={explanation}
          onChange={(event) => {
            setExplanation(event.target.value)
            setExplanationError('')
          }}
          rows={6}
          autoFocus={Boolean(name)}
          aria-invalid={Boolean(explanationError)}
          placeholder="用清晰、准确的语言解释这个知识点。"
        />
        {explanationError && <p className="field-error">{explanationError}</p>}
      </div>

      <div className="field">
        <label htmlFor="knowledge-core-points">核心要点</label>
        <textarea
          id="knowledge-core-points"
          value={corePoints}
          onChange={(event) => setCorePoints(event.target.value)}
          rows={4}
          placeholder="每行一个要点"
        />
      </div>

      <div className="field">
        <label htmlFor="knowledge-conditions">适用条件 / 例外</label>
        <textarea
          id="knowledge-conditions"
          value={conditions}
          onChange={(event) => setConditions(event.target.value)}
          rows={3}
          placeholder="没有则留空"
        />
      </div>

      <p className="form-hint">
        {mode === 'edit'
          ? '父级选项已排除自己和后代，后端仍会做循环校验。'
          : '人工新增的知识点会直接进入审核列表，正式入库前仍需审核。'}
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
          {submitting ? '保存中…' : '保存知识点'}
        </button>
      </div>
    </form>
  )
}
