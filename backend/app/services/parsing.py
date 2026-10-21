from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pptx import Presentation

from app.core.errors import DomainError

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
}
SUPPORTED_FORMAT_LABEL = "PDF、DOCX、PPTX、TXT、Markdown（MD）"


@dataclass(slots=True)
class ParsedBlock:
    kind: str
    text: str
    level: int | None = None
    page: int | None = None
    slide: int | None = None


@dataclass(slots=True)
class ParsedDocument:
    title: str
    blocks: list[ParsedBlock]
    page_count: int | None = None
    slide_count: int | None = None
    warnings: list[str] = field(default_factory=list)
    needs_ocr: bool = False


def normalize_extension(filename: str | None) -> str:
    if not filename:
        raise DomainError(422, "missing_filename", "上传文件缺少文件名")
    extension = Path(filename).suffix.lower()
    if extension == ".markdown":
        extension = ".md"
    if extension == ".ppt":
        raise DomainError(
            415,
            "legacy_ppt_unsupported",
            "暂不支持旧版 .ppt，请另存为 .pptx 后再上传",
        )
    if extension not in SUPPORTED_EXTENSIONS:
        raise DomainError(
            415,
            "unsupported_file_type",
            f"不支持该文件格式，当前支持：{SUPPORTED_FORMAT_LABEL}",
        )
    return extension


def detect_and_validate_file(path: Path, extension: str) -> str:
    """Validate the extension and actual file signature; return MIME type."""

    if not path.exists() or not path.is_file():
        raise DomainError(422, "file_not_found", "上传文件不存在")

    header = path.read_bytes()[:8]

    if extension == ".pdf":
        if not header.startswith(b"%PDF-"):
            raise DomainError(
                422,
                "file_content_mismatch",
                "文件内容不是有效的 PDF",
            )
    elif extension in {".docx", ".pptx"}:
        if not zipfile.is_zipfile(path):
            raise DomainError(
                422,
                "file_content_mismatch",
                "文件内容不是有效的 Office Open XML 文档",
            )
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
        required = (
            "word/document.xml"
            if extension == ".docx"
            else "ppt/presentation.xml"
        )
        if required not in names:
            raise DomainError(
                422,
                "file_content_mismatch",
                f"文件内容与 {extension} 扩展名不匹配",
            )
    else:
        data = path.read_bytes()
        if b"\x00" in data:
            raise DomainError(
                422,
                "file_content_mismatch",
                "文本文件包含二进制内容",
            )
        _decode_text_bytes(data)

    return MIME_TYPES[extension]


def parse_document(
    path: Path,
    extension: str,
    original_filename: str,
) -> ParsedDocument:
    fallback_title = Path(original_filename).stem.strip() or "未命名资料"
    if extension == ".pdf":
        return _parse_pdf(path, fallback_title)
    if extension == ".docx":
        return _parse_docx(path, fallback_title)
    if extension == ".pptx":
        return _parse_pptx(path, fallback_title)
    text = _decode_text_bytes(path.read_bytes())
    if extension == ".md":
        return _parse_markdown(text, fallback_title)
    return _parse_plain_text(text, fallback_title)


def _decode_text_bytes(data: bytes) -> str:
    if not data.strip():
        raise DomainError(422, "empty_file", "文件内容为空，无法解析")
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if text.strip():
            return text
    raise DomainError(
        422,
        "invalid_text_encoding",
        "无法识别文本编码，请使用 UTF-8 或常见中文文本编码",
    )


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    return [part.strip() for part in parts if part.strip()]


def _table_to_markdown(rows: list[list[str]]) -> str:
    cleaned = [
        [cell.replace("\n", " / ").replace("|", "\\|").strip() for cell in row]
        for row in rows
        if row
    ]
    if not cleaned:
        return ""
    width = max(len(row) for row in cleaned)
    cleaned = [row + [""] * (width - len(row)) for row in cleaned]
    header = cleaned[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines.extend(
        "| " + " | ".join(row) + " |" for row in cleaned[1:]
    )
    return "\n".join(lines)


def _docx_heading_level(style_name: str) -> int | None:
    style = style_name.strip().lower()
    match = re.search(r"(?:heading|标题)\s*([1-9])", style)
    if match:
        return int(match.group(1))
    if style in {"title", "标题"}:
        return 1
    return None


def _parse_pdf(path: Path, fallback_title: str) -> ParsedDocument:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise DomainError(
            422,
            "encrypted_pdf",
            "PDF 受密码保护，当前无法解析",
        )

    blocks: list[ParsedBlock] = []
    warnings: list[str] = []
    total_text = 0
    pages = list(reader.pages)

    for page_number, page in enumerate(pages, start=1):
        text = (page.extract_text() or "").strip()
        total_text += len(re.sub(r"\s+", "", text))
        if not text:
            warnings.append(f"第 {page_number} 页没有提取到文字")
            continue
        for paragraph in _split_paragraphs(text):
            blocks.append(
                ParsedBlock(
                    kind="paragraph",
                    text=paragraph,
                    page=page_number,
                )
            )

    if total_text < 20:
        return ParsedDocument(
            title=fallback_title,
            blocks=[],
            page_count=len(pages),
            warnings=warnings,
            needs_ocr=True,
        )

    return ParsedDocument(
        title=fallback_title,
        blocks=blocks,
        page_count=len(pages),
        warnings=warnings,
    )


def _parse_docx(path: Path, fallback_title: str) -> ParsedDocument:
    document = DocxDocument(str(path))
    blocks: list[ParsedBlock] = []
    title = fallback_title

    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                continue
            level = _docx_heading_level(paragraph.style.name if paragraph.style else "")
            if level is not None:
                blocks.append(ParsedBlock("heading", text, level=level))
                if title == fallback_title:
                    title = text
                continue
            style_name = (paragraph.style.name if paragraph.style else "").lower()
            is_list = "list" in style_name or "列表" in style_name
            blocks.append(
                ParsedBlock("list_item" if is_list else "paragraph", text)
            )
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            markdown = _table_to_markdown(
                [[cell.text for cell in row.cells] for row in table.rows]
            )
            if markdown:
                blocks.append(ParsedBlock("table", markdown))

    if not blocks:
        raise DomainError(422, "no_extractable_text", "DOCX 中没有可提取的正文")
    return ParsedDocument(title=title, blocks=blocks)


def _parse_pptx(path: Path, fallback_title: str) -> ParsedDocument:
    presentation = Presentation(str(path))
    blocks: list[ParsedBlock] = []
    warnings: list[str] = []
    title = fallback_title

    for slide_number, slide in enumerate(presentation.slides, start=1):
        slide_start = len(blocks)
        title_shape = slide.shapes.title
        has_text_title = bool(
            title_shape is not None
            and title_shape.has_text_frame
            and title_shape.text_frame.text.strip()
        )
        if has_text_title:
            title_text = title_shape.text_frame.text.strip()
            blocks.append(
                ParsedBlock(
                    "heading",
                    title_text,
                    level=1,
                    slide=slide_number,
                )
            )
            if title == fallback_title:
                title = title_text

        for shape in slide.shapes:
            if shape is title_shape:
                continue
            if getattr(shape, "has_text_frame", False):
                paragraphs = [
                    paragraph.text.strip()
                    for paragraph in shape.text_frame.paragraphs
                    if paragraph.text.strip()
                ]
                for index, (paragraph, text) in enumerate(
                    zip(shape.text_frame.paragraphs, paragraphs)
                ):
                    # Slides without a title placeholder (very common for
                    # hand-made decks) would otherwise never produce a
                    # heading, so structure detection always fell back to the
                    # filename. Treat the first line of the first non-empty
                    # text frame as the slide heading.
                    if not has_text_title and index == 0:
                        blocks.append(
                            ParsedBlock(
                                "heading",
                                text,
                                level=1,
                                slide=slide_number,
                            )
                        )
                        if title == fallback_title:
                            title = text
                        continue
                    kind = "list_item" if paragraph.level > 0 else "paragraph"
                    blocks.append(
                        ParsedBlock(
                            kind,
                            text,
                            slide=slide_number,
                        )
                    )
            if getattr(shape, "has_table", False):
                markdown = _table_to_markdown(
                    [
                        [cell.text for cell in row.cells]
                        for row in shape.table.rows
                    ]
                )
                if markdown:
                    blocks.append(
                        ParsedBlock(
                            "table",
                            markdown,
                            slide=slide_number,
                        )
                    )

        if len(blocks) == slide_start:
            warnings.append(f"第 {slide_number} 张幻灯片没有可提取的文字")

    if not blocks:
        raise DomainError(422, "no_extractable_text", "PPTX 中没有可提取的正文")
    return ParsedDocument(
        title=title,
        blocks=blocks,
        slide_count=len(presentation.slides),
        warnings=warnings,
    )


def _text_heading_level(line: str) -> int | None:
    stripped = line.strip()
    if not stripped:
        return None
    if re.match(r"^第[一二三四五六七八九十百0-9]+[章节部分]", stripped):
        return 1
    if re.match(r"^[0-9]+(\.[0-9]+){0,2}[、.．\s]+\S", stripped) and len(
        stripped
    ) < 80:
        return 2
    if stripped.endswith("：") and len(stripped) < 40:
        return 3
    return None


def _is_list_line(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-*+]|\d+[.)])\s+\S", line))


def _parse_plain_text(text: str, fallback_title: str) -> ParsedDocument:
    blocks: list[ParsedBlock] = []
    title = fallback_title
    for paragraph in _split_paragraphs(text):
        lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
        buffer: list[str] = []
        for line in lines:
            level = _text_heading_level(line)
            if level is not None:
                if buffer:
                    blocks.append(ParsedBlock("paragraph", "\n".join(buffer)))
                    buffer = []
                blocks.append(ParsedBlock("heading", line, level=level))
                if title == fallback_title:
                    title = line
            elif _is_list_line(line):
                if buffer:
                    blocks.append(ParsedBlock("paragraph", "\n".join(buffer)))
                    buffer = []
                blocks.append(ParsedBlock("list_item", line))
            else:
                buffer.append(line)
        if buffer:
            blocks.append(ParsedBlock("paragraph", "\n".join(buffer)))
    if not blocks:
        raise DomainError(422, "no_extractable_text", "文本文件中没有有效正文")
    return ParsedDocument(title=title, blocks=blocks)


def _parse_markdown(text: str, fallback_title: str) -> ParsedDocument:
    blocks: list[ParsedBlock] = []
    title = fallback_title
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    paragraph: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        content = "\n".join(paragraph).strip()
        if content:
            blocks.append(ParsedBlock("paragraph", content))
        paragraph = []

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            if in_code:
                code_lines.append(line)
                blocks.append(ParsedBlock("paragraph", "\n".join(code_lines)))
                code_lines = []
                in_code = False
            else:
                flush_paragraph()
                in_code = True
                code_lines = [line]
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            blocks.append(ParsedBlock("heading", heading_text, level=level))
            if title == fallback_title:
                title = heading_text
            index += 1
            continue

        if line.strip().startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            flush_paragraph()
            blocks.append(ParsedBlock("table", "\n".join(table_lines)))
            continue

        if _is_list_line(line):
            flush_paragraph()
            blocks.append(ParsedBlock("list_item", line.strip()))
            index += 1
            continue

        if not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line.rstrip())
        index += 1

    if in_code and code_lines:
        blocks.append(ParsedBlock("paragraph", "\n".join(code_lines)))
    flush_paragraph()

    if not blocks:
        raise DomainError(422, "no_extractable_text", "Markdown 文件中没有有效正文")
    return ParsedDocument(title=title, blocks=blocks)
