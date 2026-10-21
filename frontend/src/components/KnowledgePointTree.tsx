import type { KnowledgePointNode } from '../lib/api/knowledge'
import {
  formatConfidence,
  knowledgeTypeLabels,
  reviewStatusLabels,
} from '../lib/format'

interface KnowledgePointTreeProps {
  nodes: KnowledgePointNode[]
  selectedId: string | null
  checkedIds: Set<string>
  expanded: Set<string>
  onToggle: (pointId: string) => void
  onSelect: (pointId: string) => void
  onCheck: (pointId: string, checked: boolean) => void
}

export function KnowledgePointTree({
  nodes,
  selectedId,
  checkedIds,
  expanded,
  onToggle,
  onSelect,
  onCheck,
}: KnowledgePointTreeProps) {
  return (
    <ul className="knowledge-tree">
      {nodes.map((node) => {
        const hasChildren = node.children.length > 0
        const isExpanded = expanded.has(node.id)
        return (
          <li className="knowledge-tree-item" key={node.id}>
            <div
              className={`knowledge-row ${
                selectedId === node.id ? 'is-selected' : ''
              }`}
            >
              <input
                type="checkbox"
                className="knowledge-check"
                checked={checkedIds.has(node.id)}
                onChange={(event) => onCheck(node.id, event.target.checked)}
                aria-label={`选择知识点 ${node.name}`}
              />
              <button
                type="button"
                className="tree-toggle"
                onClick={() => onToggle(node.id)}
                disabled={!hasChildren}
                aria-label={`${isExpanded ? '收起' : '展开'}${node.name}`}
                aria-expanded={hasChildren ? isExpanded : undefined}
              >
                {hasChildren ? (isExpanded ? '▾' : '▸') : '·'}
              </button>
              <button
                type="button"
                className="knowledge-select"
                onClick={() => onSelect(node.id)}
              >
                <span className="knowledge-name">{node.name}</span>
                <span className="knowledge-meta">
                  {knowledgeTypeLabels[node.type]} ·{' '}
                  {formatConfidence(node.confidence)}
                </span>
              </button>
              <div className="knowledge-badges">
                <span className={`status-badge review-${node.review_status}`}>
                  {reviewStatusLabels[node.review_status]}
                </span>
                {node.needs_review && (
                  <span className="status-badge badge-warning">待确认</span>
                )}
                {node.duplicate_of_id && (
                  <span className="status-badge badge-duplicate">可能重复</span>
                )}
              </div>
            </div>
            {hasChildren && isExpanded && (
              <KnowledgePointTree
                nodes={node.children}
                selectedId={selectedId}
                checkedIds={checkedIds}
                expanded={expanded}
                onToggle={onToggle}
                onSelect={onSelect}
                onCheck={onCheck}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}
