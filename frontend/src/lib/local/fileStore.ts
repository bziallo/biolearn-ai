import { Capacitor } from '@capacitor/core'
import { Directory, Filesystem } from '@capacitor/filesystem'

export const LOCAL_FILE_ROOT = 'biolearn/files'
export const MAX_LOCAL_TEXT_BYTES = 5 * 1024 * 1024

export class FileStorageError extends Error {
  constructor(
    message: string,
    public readonly code:
      | 'native_only'
      | 'unsupported_type'
      | 'empty'
      | 'too_large'
      | 'read_failed'
      | 'write_failed'
      | 'verify_failed'
      | 'path_invalid' = 'write_failed',
  ) {
    super(message)
    this.name = 'FileStorageError'
  }
}

export interface StoredFile {
  id: string
  relativePath: string
  originalFilename: string
  mimeType: string
  sizeBytes: number
  sha256: string
}

function extensionOf(filename: string): string {
  const lower = filename.toLowerCase()
  if (lower.endsWith('.markdown')) {
    return '.md'
  }
  if (lower.endsWith('.txt')) {
    return '.txt'
  }
  if (lower.endsWith('.md')) {
    return '.md'
  }
  return ''
}

function mimeFor(extension: string): string {
  return extension === '.md' ? 'text/markdown' : 'text/plain'
}

export function isNativeFileStorageAvailable(): boolean {
  return Capacitor.isNativePlatform()
}

export function validateLocalRelativePath(path: string): void {
  if (
    !/^biolearn\/files\/[A-Za-z0-9._-]+$/.test(path) ||
    path.includes('..') ||
    path.startsWith('/')
  ) {
    throw new FileStorageError('非法的本地文件路径', 'path_invalid')
  }
}

function bytesToBase64(bytes: Uint8Array): string {
  const chunkSize = 0x8000
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(
      ...bytes.subarray(offset, offset + chunkSize),
    )
  }
  return btoa(binary)
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes
}

async function digestSha256(bytes: Uint8Array): Promise<string> {
  const subtle = globalThis.crypto?.subtle
  if (!subtle) {
    throw new FileStorageError('当前环境不支持 SHA-256 校验', 'verify_failed')
  }
  const copy = new Uint8Array(bytes.length)
  copy.set(bytes)
  const digest = await subtle.digest('SHA-256', copy.buffer)
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

function newFileId(): string {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID()
  }
  return `file-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

async function removeQuietly(path: string): Promise<void> {
  try {
    await Filesystem.deleteFile({ path, directory: Directory.Data })
  } catch {
    // Cleanup is best-effort; the caller already reports the primary error.
  }
}

export async function storeTextFile(file: File): Promise<StoredFile> {
  if (!isNativeFileStorageAvailable()) {
    throw new FileStorageError(
      '私有文件存储只在 Android 原生环境可用；浏览器继续使用 FastAPI 上传。',
      'native_only',
    )
  }
  const extension = extensionOf(file.name)
  if (!extension) {
    throw new FileStorageError(
      '本地解析目前只支持 .txt/.md/.markdown；PDF/DOCX/PPTX 请走 FastAPI。',
      'unsupported_type',
    )
  }
  if (file.size === 0) {
    throw new FileStorageError('文件为空，无法保存', 'empty')
  }
  if (file.size > MAX_LOCAL_TEXT_BYTES) {
    throw new FileStorageError(
      `本地文本文件上限为 ${MAX_LOCAL_TEXT_BYTES / (1024 * 1024)} MB；更大的文件请走 FastAPI。`,
      'too_large',
    )
  }

  let bytes: Uint8Array
  try {
    bytes = new Uint8Array(await file.arrayBuffer())
  } catch {
    throw new FileStorageError('读取所选文件失败，文件可能已被移动或权限失效', 'read_failed')
  }
  if (bytes.length === 0) {
    throw new FileStorageError('文件为空，无法保存', 'empty')
  }
  const sha256 = await digestSha256(bytes)
  const id = newFileId()
  const relativePath = `${LOCAL_FILE_ROOT}/${id}${extension}`
  const temporaryPath = `${relativePath}.part`
  validateLocalRelativePath(relativePath)
  validateLocalRelativePath(temporaryPath)

  try {
    await Filesystem.writeFile({
      path: temporaryPath,
      data: bytesToBase64(bytes),
      directory: Directory.Data,
      recursive: true,
    })
    const stat = await Filesystem.stat({
      path: temporaryPath,
      directory: Directory.Data,
    })
    if (Number(stat.size) !== bytes.length) {
      throw new FileStorageError('文件写入大小校验失败', 'verify_failed')
    }
    await Filesystem.rename({
      from: temporaryPath,
      to: relativePath,
      directory: Directory.Data,
      toDirectory: Directory.Data,
    })
    return {
      id,
      relativePath,
      originalFilename: file.name,
      mimeType: mimeFor(extension),
      sizeBytes: bytes.length,
      sha256,
    }
  } catch (error) {
    await removeQuietly(temporaryPath)
    await removeQuietly(relativePath)
    if (error instanceof FileStorageError) {
      throw error
    }
    throw new FileStorageError(
      `写入应用私有目录失败：${error instanceof Error ? error.message : String(error)}`,
      'write_failed',
    )
  }
}

export async function readStoredText(relativePath: string): Promise<Uint8Array> {
  validateLocalRelativePath(relativePath)
  if (!isNativeFileStorageAvailable()) {
    throw new FileStorageError('私有文件存储只在 Android 原生环境可用', 'native_only')
  }
  try {
    const result = await Filesystem.readFile({
      path: relativePath,
      directory: Directory.Data,
    })
    if (typeof result.data !== 'string') {
      return new Uint8Array(await result.data.arrayBuffer())
    }
    return base64ToBytes(result.data)
  } catch (error) {
    throw new FileStorageError(
      `读取私有文件失败：${error instanceof Error ? error.message : String(error)}`,
      'read_failed',
    )
  }
}

export async function readStoredTextAsString(relativePath: string): Promise<string> {
  const bytes = await readStoredText(relativePath)
  return new TextDecoder('utf-8', { fatal: false }).decode(bytes)
}

export async function deleteStoredFile(relativePath: string): Promise<void> {
  validateLocalRelativePath(relativePath)
  if (!isNativeFileStorageAvailable()) {
    throw new FileStorageError('私有文件存储只在 Android 原生环境可用', 'native_only')
  }
  await Filesystem.deleteFile({ path: relativePath, directory: Directory.Data })
}

export async function cleanupTemporaryFiles(): Promise<number> {
  if (!isNativeFileStorageAvailable()) {
    return 0
  }
  try {
    await Filesystem.mkdir({
      path: LOCAL_FILE_ROOT,
      directory: Directory.Data,
      recursive: true,
    })
    const listing = await Filesystem.readdir({
      path: LOCAL_FILE_ROOT,
      directory: Directory.Data,
    })
    let removed = 0
    for (const entry of listing.files) {
      if (entry.type === 'file' && entry.name.endsWith('.part')) {
        await removeQuietly(`${LOCAL_FILE_ROOT}/${entry.name}`)
        removed += 1
      }
    }
    return removed
  } catch {
    return 0
  }
}
