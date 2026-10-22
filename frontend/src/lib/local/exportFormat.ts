import { LOCAL_DB_SCHEMA_VERSION } from './schema'
import type { LocalExportData, LocalExportPayload } from './types'

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(canonicalize)
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    return Object.keys(record)
      .sort()
      .reduce<Record<string, unknown>>((result, key) => {
        result[key] = canonicalize(record[key])
        return result
      }, {})
  }
  return value
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value))
}

export async function sha256Hex(value: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle
  if (!subtle) {
    throw new Error('当前环境不支持 Web Crypto SHA-256，无法校验导出文件')
  }
  const data = new TextEncoder().encode(value)
  const digest = await subtle.digest('SHA-256', data)
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

export async function checksumFor(
  schemaVersion: number,
  syntheticOnly: boolean,
  data: LocalExportData,
): Promise<string> {
  return sha256Hex(
    canonicalJson({
      format: 'biolearn.localdb.export',
      schemaVersion,
      syntheticOnly,
      data,
    }),
  )
}

export async function createExportPayload(
  schemaVersion: number,
  syntheticOnly: boolean,
  data: LocalExportData,
): Promise<LocalExportPayload> {
  return {
    format: 'biolearn.localdb.export',
    schemaVersion,
    exportedAt: new Date().toISOString(),
    syntheticOnly,
    checksumAlgorithm: 'SHA-256',
    checksum: await checksumFor(schemaVersion, syntheticOnly, data),
    data,
  }
}

export async function verifyExportPayload(
  payload: LocalExportPayload,
): Promise<{ ok: boolean; reason?: string }> {
  if (payload.format !== 'biolearn.localdb.export') {
    return { ok: false, reason: '不是 BioLearn 本地数据库导出文件' }
  }
  if (payload.schemaVersion !== LOCAL_DB_SCHEMA_VERSION) {
    return { ok: false, reason: `不支持的 schema 版本：${payload.schemaVersion}` }
  }
  if (payload.checksumAlgorithm !== 'SHA-256' || !payload.checksum) {
    return { ok: false, reason: '缺少 SHA-256 校验值' }
  }
  const expected = await checksumFor(
    payload.schemaVersion,
    payload.syntheticOnly,
    payload.data,
  )
  if (expected !== payload.checksum) {
    return { ok: false, reason: '导出文件 checksum 不匹配，文件可能被修改' }
  }
  return { ok: true }
}
