import { sha256Hex } from './exportFormat'

export const MAX_LOCAL_TEXT_CHARS = 1_000_000
export const MAX_CHUNK_CHARS = 2000

export class TextParseError extends Error {
  constructor(
    message: string,
    public readonly code:
      | 'empty'
      | 'too_large'
      | 'encoding'
      | 'no_content' = 'no_content',
  ) {
    super(message)
    this.name = 'TextParseError'
  }
}

export interface ParsedTextChunk {
  id: string
  index: number
  headingPath: string | null
  headingLevel: number | null
  content: string
  pageStart: null
  pageEnd: null
  slideNumber: null
  charStart: number
  charEnd: number
  locationLabel: string
}

export interface ParsedTextDocument {
  title: string
  encoding: 'utf-8' | 'gb18030'
  normalizedText: string
  chunks: ParsedTextChunk[]
  charCount: number
}

function stripUtf8Bom(bytes: Uint8Array): Uint8Array {
  if (
    bytes.length >= 3 &&
    bytes[0] === 0xef &&
    bytes[1] === 0xbb &&
    bytes[2] === 0xbf
  ) {
    return bytes.subarray(3)
  }
  return bytes
}

function decodeBytes(bytes: Uint8Array): {
  text: string
  encoding: 'utf-8' | 'gb18030'
} {
  const withoutBom = stripUtf8Bom(bytes)
  try {
    return {
      text: new TextDecoder('utf-8', { fatal: true }).decode(withoutBom),
      encoding: 'utf-8',
    }
  } catch {
    try {
      return {
        text: new TextDecoder('gb18030', { fatal: true }).decode(withoutBom),
        encoding: 'gb18030',
      }
    } catch {
      throw new TextParseError(
        '无法识别文本编码；请使用 UTF-8（可带 BOM）或 GB18030 编码。',
        'encoding',
      )
    }
  }
}

function normalizeNewlines(text: string): string {
  return text.replace(/\r\n?/g, '\n')
}

function fileStem(filename: string): string {
  return filename.replace(/\.[^.]+$/, '').trim() || '未命名文本'
}

export async function parseTextDocument(
  bytes: Uint8Array,
  originalFilename: string,
  documentId: string,
): Promise<ParsedTextDocument> {
  if (bytes.length === 0) {
    throw new TextParseError('文件为空，无法解析。', 'empty')
  }
  const decoded = decodeBytes(bytes)
  if (decoded.text.length > MAX_LOCAL_TEXT_CHARS) {
    throw new TextParseError(
      `文本超过 ${MAX_LOCAL_TEXT_CHARS.toLocaleString()} 字符上限；请拆分后再导入。`,
      'too_large',
    )
  }
  const normalizedText = normalizeNewlines(decoded.text)
  if (!normalizedText.trim()) {
    throw new TextParseError('文件只有空白内容，无法解析。', 'empty')
  }

  const lines = normalizedText.split('\n')
  const chunks: ParsedTextChunk[] = []
  const headingStack: Array<{ level: number; text: string }> = []
  let buffer = ''
  let bufferStart = 0
  let offset = 0
  let title = fileStem(originalFilename)

  const flush = async (endOffset: number): Promise<void> => {
    if (!buffer.trim()) {
      buffer = ''
      bufferStart = endOffset
      return
    }
    const content = buffer.trimEnd()
    const index = chunks.length
    const headingPath = headingStack.map((item) => item.text).join(' > ') || null
    const headingLevel =
      headingStack.length > 0 ? headingStack[headingStack.length - 1].level : null
    chunks.push({
      id: `chunk-${documentId}-${index}-${(await sha256Hex(content)).slice(0, 12)}`,
      index,
      headingPath,
      headingLevel,
      content,
      pageStart: null,
      pageEnd: null,
      slideNumber: null,
      charStart: bufferStart,
      charEnd: endOffset,
      locationLabel: `文本片段 ${index + 1}`,
    })
    buffer = ''
    bufferStart = endOffset
  }

  for (const line of lines) {
    const heading = /^(#{1,6})\s+(.+?)\s*$/.exec(line)
    if (heading) {
      const level = heading[1].length
      const text = heading[2].trim()
      while (
        headingStack.length > 0 &&
        headingStack[headingStack.length - 1].level >= level
      ) {
        headingStack.pop()
      }
      headingStack.push({ level, text })
      if (level === 1 && title === fileStem(originalFilename)) {
        title = text
      }
    }

    if (buffer && buffer.length + line.length + 1 > MAX_CHUNK_CHARS) {
      await flush(offset)
    }

    if (line.length > MAX_CHUNK_CHARS) {
      for (let start = 0; start < line.length; start += MAX_CHUNK_CHARS) {
        const part = line.slice(start, start + MAX_CHUNK_CHARS)
        if (buffer) {
          buffer += '\n'
        }
        buffer += part
        offset += part.length
        await flush(offset)
      }
      continue
    }

    if (buffer) {
      buffer += '\n'
    }
    buffer += line
    offset += line.length
    if (line.trim() === '' && buffer.trim().length >= 200) {
      await flush(offset)
    }
  }
  await flush(offset)

  if (chunks.length === 0) {
    throw new TextParseError('没有可提取的文本内容。', 'no_content')
  }
  return {
    title,
    encoding: decoded.encoding,
    normalizedText,
    chunks,
    charCount: normalizedText.length,
  }
}
