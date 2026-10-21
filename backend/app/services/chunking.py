from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.parsing import ParsedBlock, ParsedDocument


@dataclass(slots=True)
class ChunkDraft:
    heading_path: str | None
    heading_level: int | None
    content: str
    page_start: int | None
    page_end: int | None
    slide_number: int | None
    char_start: int
    char_end: int
    block_start: int | None
    block_end: int | None
    location_label: str


def _format_block(block: ParsedBlock) -> str:
    if block.kind == "heading":
        level = block.level or 1
        return f"{'#' * min(level, 6)} {block.text}".strip()
    if block.kind == "list_item":
        return block.text if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", block.text) else f"- {block.text}"
    return block.text


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    buffer = ""
    for sentence in re.split(r"(?<=[。！？.!?])\s*", text):
        if not sentence:
            continue
        if len(buffer) + len(sentence) <= max_chars:
            buffer += sentence
            continue
        if buffer:
            pieces.append(buffer.strip())
            buffer = ""
        while len(sentence) > max_chars:
            pieces.append(sentence[:max_chars].strip())
            sentence = sentence[max_chars:]
        buffer = sentence
    if buffer.strip():
        pieces.append(buffer.strip())
    return [piece for piece in pieces if piece]


def _location_label(
    page_start: int | None,
    page_end: int | None,
    slide_number: int | None,
    heading_path: str | None,
) -> str:
    if page_start is not None:
        if page_end is not None and page_end != page_start:
            return f"第 {page_start}–{page_end} 页"
        return f"第 {page_start} 页"
    if slide_number is not None:
        return f"第 {slide_number} 张幻灯片"
    return heading_path or "正文"


def build_chunks(
    parsed: ParsedDocument,
    *,
    max_chars: int,
    min_chars: int,
) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    heading_stack: list[tuple[int, str]] = []
    current_parts: list[str] = []
    current_heading_path: str | None = None
    current_heading_level: int | None = None
    current_page_start: int | None = None
    current_page_end: int | None = None
    current_slide: int | None = None
    current_char_start = 0
    current_char_end = 0
    current_block_start: int | None = None
    current_block_end: int | None = None
    cursor = 0

    def flush() -> None:
        nonlocal current_parts
        content = "\n\n".join(part for part in current_parts if part.strip()).strip()
        if content:
            drafts.append(
                ChunkDraft(
                    heading_path=current_heading_path,
                    heading_level=current_heading_level,
                    content=content,
                    page_start=current_page_start,
                    page_end=current_page_end,
                    slide_number=current_slide,
                    char_start=current_char_start,
                    char_end=current_char_end,
                    block_start=current_block_start,
                    block_end=current_block_end,
                    location_label=_location_label(
                        current_page_start,
                        current_page_end,
                        current_slide,
                        current_heading_path,
                    ),
                )
            )
        current_parts = []

    def start_block(
        block: ParsedBlock,
        block_start: int,
        block_end: int,
        block_index: int,
    ) -> None:
        nonlocal current_page_start, current_page_end, current_slide
        nonlocal current_char_start, current_char_end
        nonlocal current_block_start, current_block_end
        current_page_start = block.page
        current_page_end = block.page
        current_slide = block.slide
        current_char_start = block_start
        current_char_end = block_end
        current_block_start = block_index
        current_block_end = block_index

    for block_index, block in enumerate(parsed.blocks):
        block_text = _format_block(block)
        if not block_text.strip():
            continue
        block_start = cursor
        block_end = cursor + len(block_text)
        cursor = block_end + 2

        if block.kind == "heading":
            flush()
            level = block.level or 1
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, block.text))
            current_heading_path = " > ".join(title for _, title in heading_stack)
            current_heading_level = level
            start_block(block, block_start, block_end, block_index)
            current_parts.append(block_text)
            continue

        page_changed = (
            block.page is not None
            and current_page_start is not None
            and block.page != current_page_end
        )
        slide_changed = (
            block.slide is not None
            and current_slide is not None
            and block.slide != current_slide
        )
        if current_parts and (page_changed or slide_changed):
            flush()

        if not current_parts:
            start_block(block, block_start, block_end, block_index)
        else:
            current_page_end = block.page or current_page_end
            current_slide = block.slide or current_slide
            current_char_end = block_end
            current_block_end = block_index

        candidate = "\n\n".join([*current_parts, block_text])
        if len(candidate) <= max_chars:
            current_parts.append(block_text)
            continue

        if current_parts:
            flush()

        # A single oversized block is split into pieces. Record each piece's
        # real offset inside the formatted block instead of reusing the whole
        # block range for every piece.
        search_from = 0
        for piece in _split_long_text(block_text, max_chars):
            offset = block_text.find(piece, search_from)
            if offset < 0:
                offset = search_from
            piece_start = block_start + offset
            piece_end = piece_start + len(piece)
            search_from = offset + len(piece)

            if current_parts and len(
                "\n\n".join([*current_parts, piece])
            ) > max_chars:
                flush()

            if not current_parts:
                current_page_start = block.page
                current_page_end = block.page
                current_slide = block.slide
                current_char_start = piece_start
                current_char_end = piece_end
                current_block_start = block_index
                current_block_end = block_index
            else:
                current_char_end = piece_end
            current_parts.append(piece)

    flush()

    if min_chars > 0:
        merged: list[ChunkDraft] = []
        for draft in drafts:
            if (
                merged
                and len(merged[-1].content) < min_chars
                and merged[-1].heading_path == draft.heading_path
                and merged[-1].page_start == draft.page_start
                and merged[-1].slide_number == draft.slide_number
                and len(merged[-1].content) + len(draft.content) + 2
                <= max_chars
            ):
                previous = merged[-1]
                previous.content = f"{previous.content}\n\n{draft.content}"
                previous.page_end = draft.page_end or previous.page_end
                previous.slide_number = draft.slide_number or previous.slide_number
                previous.char_end = draft.char_end
                previous.block_end = draft.block_end
                previous.location_label = _location_label(
                    previous.page_start,
                    previous.page_end,
                    previous.slide_number,
                    previous.heading_path,
                )
            else:
                merged.append(draft)
        drafts = merged

    for draft in drafts:
        if not draft.location_label:
            draft.location_label = draft.heading_path or "正文"
        if draft.char_end <= draft.char_start:
            draft.char_end = draft.char_start + len(draft.content)

    return drafts
