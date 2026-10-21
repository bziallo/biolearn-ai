import type { ChapterNode } from './api/chapters'

export interface FlatChapter {
  node: ChapterNode
  depth: number
}

export function flattenTree(
  nodes: ChapterNode[],
  depth = 0,
): FlatChapter[] {
  return nodes.flatMap((node) => [
    { node, depth },
    ...flattenTree(node.children, depth + 1),
  ])
}

export function countDescendants(node: ChapterNode): number {
  return node.children.reduce(
    (total, child) => total + 1 + countDescendants(child),
    0,
  )
}

export function findChapter(
  nodes: ChapterNode[],
  chapterId: string,
): ChapterNode | null {
  for (const node of nodes) {
    if (node.id === chapterId) {
      return node
    }
    const found = findChapter(node.children, chapterId)
    if (found) {
      return found
    }
  }
  return null
}

export function collectSubtreeIds(node: ChapterNode): Set<string> {
  const ids = new Set<string>([node.id])
  for (const child of node.children) {
    for (const id of collectSubtreeIds(child)) {
      ids.add(id)
    }
  }
  return ids
}
