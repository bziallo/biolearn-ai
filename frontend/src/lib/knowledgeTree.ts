import type { KnowledgePointNode } from './api/knowledge'

export interface FlatKnowledgePoint {
  node: KnowledgePointNode
  depth: number
}

export function flattenKnowledgeTree(
  nodes: KnowledgePointNode[],
  depth = 0,
): FlatKnowledgePoint[] {
  return nodes.flatMap((node) => [
    { node, depth },
    ...flattenKnowledgeTree(node.children, depth + 1),
  ])
}

export function findKnowledgeNode(
  nodes: KnowledgePointNode[],
  pointId: string,
): KnowledgePointNode | null {
  for (const node of nodes) {
    if (node.id === pointId) {
      return node
    }
    const found = findKnowledgeNode(node.children, pointId)
    if (found) {
      return found
    }
  }
  return null
}

export function collectPointSubtreeIds(node: KnowledgePointNode): Set<string> {
  const ids = new Set<string>([node.id])
  for (const child of node.children) {
    for (const id of collectPointSubtreeIds(child)) {
      ids.add(id)
    }
  }
  return ids
}

export function countPointDescendants(node: KnowledgePointNode): number {
  return node.children.reduce(
    (total, child) => total + 1 + countPointDescendants(child),
    0,
  )
}

export function collectExpandablePointIds(
  nodes: KnowledgePointNode[],
  target = new Set<string>(),
): Set<string> {
  for (const node of nodes) {
    if (node.children.length > 0) {
      target.add(node.id)
      collectExpandablePointIds(node.children, target)
    }
  }
  return target
}
