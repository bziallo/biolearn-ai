import { describe, expect, it } from 'vitest'

import { parseTextDocument, TextParseError } from './textParser'

const encoder = new TextEncoder()

describe('parseTextDocument', () => {
  it('handles UTF-8 BOM, CRLF and Markdown headings deterministically', async () => {
    const bytes = new Uint8Array([
      0xef,
      0xbb,
      0xbf,
      ...encoder.encode('# 蛋白质\r\n\r\n## 一级结构\r\n氨基酸序列。\r\n'),
    ])
    const first = await parseTextDocument(bytes, 'notes.md', 'doc-1')
    expect(first.encoding).toBe('utf-8')
    expect(first.title).toBe('蛋白质')
    expect(first.normalizedText).not.toContain('\r')
    expect(first.chunks.length).toBeGreaterThan(0)
    expect(first.chunks.some((chunk) => chunk.headingPath?.includes('蛋白质'))).toBe(
      true,
    )
    expect(first.chunks[0].id).toMatch(/^chunk-doc-1-/)

    const second = await parseTextDocument(bytes, 'notes.md', 'doc-1')
    expect(second.chunks.map((chunk) => chunk.id)).toEqual(
      first.chunks.map((chunk) => chunk.id),
    )
  })

  it('decodes GB18030 text when UTF-8 is invalid', async () => {
    // "中文" in GB18030
    const gb = new Uint8Array([0xd6, 0xd0, 0xce, 0xc4])
    const parsed = await parseTextDocument(gb, 'legacy.txt', 'doc-gb')
    expect(parsed.encoding).toBe('gb18030')
    expect(parsed.normalizedText).toBe('中文')
  })

  it('rejects empty/whitespace-only files', async () => {
    await expect(
      parseTextDocument(new Uint8Array(), 'empty.txt', 'doc-empty'),
    ).rejects.toMatchObject({ code: 'empty' })
    await expect(
      parseTextDocument(encoder.encode(' \r\n\t'), 'space.txt', 'doc-space'),
    ).rejects.toMatchObject({ code: 'empty' })
  })

  it('splits long text into bounded chunks with stable identifiers', async () => {
    const text = Array.from({ length: 250 }, (_, index) => `第 ${index} 行内容`).join(
      '\n',
    )
    const parsed = await parseTextDocument(
      encoder.encode(text),
      'long.txt',
      'doc-long',
    )
    expect(parsed.chunks.length).toBeGreaterThan(1)
    expect(Math.max(...parsed.chunks.map((chunk) => chunk.content.length))).toBeLessThanOrEqual(
      2000,
    )
    expect(new Set(parsed.chunks.map((chunk) => chunk.id)).size).toBe(
      parsed.chunks.length,
    )
  })

  it('throws a typed error for invalid input', async () => {
    await expect(
      parseTextDocument(new Uint8Array([0xff, 0xff]), 'bad.txt', 'doc-bad'),
    ).rejects.toBeInstanceOf(TextParseError)
  })
})
