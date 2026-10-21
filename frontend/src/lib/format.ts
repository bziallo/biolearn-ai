import type { DocumentStatus } from './api/documents'
import type {
  JobStatus,
  KnowledgePointType,
  ReviewStatus,
} from './api/knowledge'

export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDate(value: string | null): string {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export const documentStatusLabels: Record<DocumentStatus, string> = {
  uploaded: '等待解析',
  parsing: '解析中',
  parsed: '已解析',
  failed: '解析失败',
  needs_ocr: '需要 OCR',
}

export const knowledgeTypeLabels: Record<KnowledgePointType, string> = {
  basic_concept: '基本概念',
  structure: '结构组成',
  classification: '分类',
  mechanism: '原理机制',
  process: '过程步骤',
  causality: '因果关系',
  formula: '公式与计算',
  experiment: '实验方法',
  application: '应用',
  comparison: '对比辨析',
}

export const reviewStatusLabels: Record<ReviewStatus, string> = {
  pending: '待审核',
  approved: '已通过',
  needs_revision: '需要修改',
  ignored: '已忽略',
}

export const jobStatusLabels: Record<JobStatus, string> = {
  queued: '排队中',
  analyzing: '分析整章结构',
  extracting: '逐块提取',
  merging: '全章整合',
  cancelling: '正在停止',
  cancelled: '已停止',
  completed: '已完成',
  failed: '失败',
}

export function formatConfidence(value: number | null): string {
  return value === null ? '未提供置信度' : `置信度 ${Math.round(value * 100)}%`
}
