import type { ChapterNode } from '../lib/api/chapters'
import { countDescendants } from '../lib/chapterTree'

interface ChapterTreeProps {
  nodes: ChapterNode[]
  depth?: number
  selectedId: string | null
  expanded: Set<string>
  onToggle: (chapterId: string) => void
  onSelect: (chapterId: string) => void
  onAddChild: (node: ChapterNode) => void
  onEdit: (node: ChapterNode) => void
  onDelete: (node: ChapterNode) => void
  onMove: (node: ChapterNode, direction: 'up' | 'down') => void
}

export function ChapterTree({
  nodes,
  depth = 0,
  selectedId,
  expanded,
  onToggle,
  onSelect,
  onAddChild,
  onEdit,
  onDelete,
  onMove,
}: ChapterTreeProps) {
  return (
    <ul className={`chapter-tree ${depth > 0 ? 'chapter-tree-nested' : ''}`}>
      {nodes.map((node, index) => {
        const hasChildren = node.children.length > 0
        const isExpanded = expanded.has(node.id)

        return (
          <li className="chapter-tree-item" key={node.id}>
            <div
              className={`chapter-row ${
                selectedId === node.id ? 'is-selected' : ''
              }`}
            >
              <button
                type="button"
                className="tree-toggle"
                onClick={() => onToggle(node.id)}
                disabled={!hasChildren}
                aria-label={
                  hasChildren
                    ? `${isExpanded ? '收起' : '展开'}${node.name}`
                    : `${node.name}没有子章节`
                }
                aria-expanded={hasChildren ? isExpanded : undefined}
              >
                {hasChildren ? (isExpanded ? '▾' : '▸') : '·'}
              </button>

              <button
                type="button"
                className="chapter-select"
                onClick={() => onSelect(node.id)}
              >
                <span className="chapter-name">{node.name}</span>
                <span className="chapter-meta">
                  {hasChildren
                    ? `${countDescendants(node)} 个子章节`
                    : '末级章节'}
                </span>
              </button>

              <div className="chapter-actions">
                <button
                  type="button"
                  className="mini-button"
                  onClick={() => onMove(node, 'up')}
                  disabled={index === 0}
                  aria-label={`上移${node.name}`}
                  title="上移"
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="mini-button"
                  onClick={() => onMove(node, 'down')}
                  disabled={index === nodes.length - 1}
                  aria-label={`下移${node.name}`}
                  title="下移"
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="mini-button"
                  onClick={() => onAddChild(node)}
                >
                  ＋子章节
                </button>
                <button
                  type="button"
                  className="mini-button"
                  onClick={() => onEdit(node)}
                >
                  编辑
                </button>
                <button
                  type="button"
                  className="mini-button danger"
                  onClick={() => onDelete(node)}
                >
                  删除
                </button>
              </div>
            </div>

            {hasChildren && isExpanded && (
              <ChapterTree
                nodes={node.children}
                depth={depth + 1}
                selectedId={selectedId}
                expanded={expanded}
                onToggle={onToggle}
                onSelect={onSelect}
                onAddChild={onAddChild}
                onEdit={onEdit}
                onDelete={onDelete}
                onMove={onMove}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}
