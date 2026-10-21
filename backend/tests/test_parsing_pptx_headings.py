from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from app.services.chunking import build_chunks
from app.services.parsing import ParsedBlock, parse_document

def _blank_slide_file(path: Path, titles: list[str]) -> Path:
    """Build a deck whose slides have no title placeholder, only text boxes.

    Hand-made courseware often looks like this. Before the fix, such slides
    produced no heading block at all, so structure detection always fell back
    to the filename.
    """

    prs = Presentation()
    blank = prs.slide_layouts[6]
    for index, title in enumerate(titles):
        slide = prs.slides.add_slide(blank)
        box = slide.shapes.add_textbox(
            Inches(0.5),
            Inches(0.5),
            Inches(9),
            Inches(4),
        )
        frame = box.text_frame
        frame.text = title
        if index == 0:
            frame.add_paragraph().text = "一、概述"
            frame.add_paragraph().text = "二、机制"
    prs.save(path)
    return path


def test_pptx_without_title_placeholder_uses_first_line_as_heading(
    tmp_path: Path,
) -> None:
    deck = _blank_slide_file(tmp_path / "manual-deck.pptx", ["第一章 细胞膜", "第二章 物质运输"])

    parsed = parse_document(deck, ".pptx", deck.name)

    headings = [block for block in parsed.blocks if block.kind == "heading"]
    assert [block.text for block in headings] == ["第一章 细胞膜", "第二章 物质运输"]
    assert all(block.level == 1 for block in headings)
    assert all(block.slide is not None for block in headings)
    assert parsed.title == "第一章 细胞膜"

    chunks = build_chunks(parsed, max_chars=6000, min_chars=20)
    assert any(chunk.heading_path and "第一章 细胞膜" in chunk.heading_path for chunk in chunks)


def test_pptx_with_title_placeholder_keeps_single_heading(
    tmp_path: Path,
) -> None:
    path = tmp_path / "titled-deck.pptx"
    prs = Presentation()
    layout = prs.slide_layouts[5]
    slide = prs.slides.add_slide(layout)
    slide.shapes.title.text = "第一章 蛋白质"
    body = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(8), Inches(3))
    body.text_frame.text = "一级结构由氨基酸序列决定。"
    prs.save(path)

    parsed = parse_document(path, ".pptx", path.name)
    headings = [block for block in parsed.blocks if block.kind == "heading"]
    assert len(headings) == 1
    assert headings[0].text == "第一章 蛋白质"
    # The body text must stay a paragraph, not be promoted to a heading.
    assert any(
        block.kind == "paragraph" and "一级结构" in block.text
        for block in parsed.blocks
    )


def test_heading_detection_marks_first_line_only_once() -> None:
    blocks = [
        ParsedBlock("heading", "幻灯片标题", level=1, slide=1),
        ParsedBlock("paragraph", "正文内容", slide=1),
    ]
    assert blocks[0].level == 1
    assert blocks[1].kind == "paragraph"
