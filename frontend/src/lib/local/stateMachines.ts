import type {
  LocalFileStatus,
  LocalParseStatus,
  LocalUploadStatus,
} from './types'

export const FILE_TRANSITIONS: Record<LocalFileStatus, LocalFileStatus[]> = {
  selected: ['copying', 'failed'],
  copying: ['stored', 'failed'],
  stored: ['deleted', 'failed'],
  failed: ['deleted'],
  deleted: [],
}

export const PARSE_TRANSITIONS: Record<LocalParseStatus, LocalParseStatus[]> = {
  queued: ['parsing', 'failed'],
  parsing: ['parsed', 'failed'],
  parsed: [],
  failed: ['queued'],
}

export const UPLOAD_TRANSITIONS: Record<LocalUploadStatus, LocalUploadStatus[]> = {
  queued: ['uploading', 'failed', 'needs_verification'],
  uploading: ['uploaded', 'failed', 'needs_verification'],
  uploaded: [],
  failed: ['queued'],
  needs_verification: ['queued', 'uploaded'],
}

export function canTransition<T extends string>(
  transitions: Record<T, T[]>,
  from: T,
  to: T,
): boolean {
  return transitions[from]?.includes(to) ?? false
}

export function assertTransition<T extends string>(
  transitions: Record<T, T[]>,
  from: T,
  to: T,
  label: string,
): void {
  if (!canTransition(transitions, from, to)) {
    throw new Error(`${label} 非法状态转换：${from} → ${to}`)
  }
}
