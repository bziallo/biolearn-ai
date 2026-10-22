import { beforeEach, describe, expect, it, vi } from 'vitest'

const fs = vi.hoisted(() => ({
  writeFile: vi.fn(),
  stat: vi.fn(),
  rename: vi.fn(),
  readFile: vi.fn(),
  deleteFile: vi.fn(),
  mkdir: vi.fn(),
  readdir: vi.fn(),
}))

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: vi.fn(() => true) },
}))

vi.mock('@capacitor/filesystem', () => ({
  Directory: { Data: 'DATA' },
  Filesystem: fs,
}))

import { Capacitor } from '@capacitor/core'
import {
  FileStorageError,
  cleanupTemporaryFiles,
  isNativeFileStorageAvailable,
  readStoredText,
  storeTextFile,
  validateLocalRelativePath,
} from './fileStore'

function textFile(content: string, filename: string, type = 'text/plain'): File {
  const bytes = new TextEncoder().encode(content)
  return {
    name: filename,
    type,
    size: bytes.length,
    arrayBuffer: async () =>
      bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
  } as File
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(Capacitor.isNativePlatform).mockReturnValue(true)
  fs.writeFile.mockResolvedValue({ uri: 'file:///private/x' })
  fs.stat.mockImplementation(({ path }: { path: string }) =>
    Promise.resolve({ size: path.endsWith('.part') ? 5 : 5 }),
  )
  fs.rename.mockResolvedValue(undefined)
  fs.readFile.mockResolvedValue({ data: 'aGVsbG8=' })
  fs.deleteFile.mockResolvedValue(undefined)
  fs.mkdir.mockResolvedValue(undefined)
  fs.readdir.mockResolvedValue({ files: [] })
})

describe('private file store', () => {
  it('copies through a temp file, verifies size and SHA-256, then renames', async () => {
    const file = textFile('hello', 'notes.txt')
    const stored = await storeTextFile(file)

    expect(stored.relativePath).toMatch(/^biolearn\/files\/.+\.txt$/)
    expect(stored.sizeBytes).toBe(5)
    expect(stored.sha256).toMatch(/^[a-f0-9]{64}$/)
    expect(fs.writeFile).toHaveBeenCalledWith(
      expect.objectContaining({
        path: expect.stringMatching(/\.part$/),
        directory: 'DATA',
      }),
    )
    expect(fs.stat).toHaveBeenCalledWith(
      expect.objectContaining({ path: expect.stringMatching(/\.part$/) }),
    )
    expect(fs.rename).toHaveBeenCalledWith(
      expect.objectContaining({
        from: expect.stringMatching(/\.part$/),
        to: stored.relativePath,
      }),
    )
    expect(fs.deleteFile).not.toHaveBeenCalled()
  })

  it('cleans the temp file when the size check fails', async () => {
    fs.stat.mockResolvedValue({ size: 4 })
    await expect(
      storeTextFile(textFile('hello', 'notes.txt')),
    ).rejects.toMatchObject({ code: 'verify_failed' })
    expect(fs.deleteFile).toHaveBeenCalled()
    expect(fs.rename).not.toHaveBeenCalled()
  })

  it('rejects unsupported, empty and oversized files before writing', async () => {
    await expect(
      storeTextFile(textFile('x', 'slides.pdf', 'application/pdf')),
    ).rejects.toMatchObject({ code: 'unsupported_type' })
    await expect(
      storeTextFile(textFile('', 'empty.txt')),
    ).rejects.toMatchObject({ code: 'empty' })
    const big = textFile('x', 'big.txt')
    Object.defineProperty(big, 'size', { value: 5 * 1024 * 1024 + 1 })
    await expect(storeTextFile(big)).rejects.toMatchObject({ code: 'too_large' })
  })

  it('degrades clearly when not running on Android', async () => {
    vi.mocked(Capacitor.isNativePlatform).mockReturnValue(false)
    expect(isNativeFileStorageAvailable()).toBe(false)
    await expect(storeTextFile(textFile('hello', 'notes.txt'))).rejects.toMatchObject(
      { code: 'native_only' },
    )
  })

  it('rejects arbitrary or traversal paths', () => {
    expect(() => validateLocalRelativePath('/data/files/x.txt')).toThrow(
      FileStorageError,
    )
    expect(() => validateLocalRelativePath('biolearn/files/../secret')).toThrow(
      FileStorageError,
    )
  })

  it('reads stored bytes and cleans only .part files in the private root', async () => {
    const bytes = await readStoredText('biolearn/files/abc.txt')
    expect(new TextDecoder().decode(bytes)).toBe('hello')

    fs.readdir.mockResolvedValue({
      files: [
        { name: 'abc.txt.part', type: 'file' },
        { name: 'abc.txt', type: 'file' },
      ],
    })
    await cleanupTemporaryFiles()
    expect(fs.deleteFile).toHaveBeenCalledTimes(1)
    expect(fs.deleteFile).toHaveBeenCalledWith(
      expect.objectContaining({ path: 'biolearn/files/abc.txt.part' }),
    )
  })
})
