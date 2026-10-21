"""Phase-2 acceptance sample: generate an importable class file.

Generates a small PPTX (two slides, one with a numbered outline) and a
knowledge-point JSON in the documented ``schema_version 1.0`` format, so the
whole pipeline can be exercised without touching real data.

Nothing is uploaded by this script; it only writes files, and it refuses to
upload through the API on purpose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
OUT.mkdir(parents=True, exist_ok=True)


def build_pptx(path: Path) -> None:
    prs = Presentation()
    blank = prs.slide_layouts[6]

    slide = prs.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.6), Inches(0.6), Inches(8.5), Inches(1.2))
    box.text_frame.text = "第二章 第X节 阶段二验收（合成样例）"
    box.text_frame.paragraphs[0].runs[0].font.size = Pt(32)

    slide2 = prs.slides.add_slide(blank)
    body = slide2.shapes.add_textbox(Inches(0.6), Inches(0.6), Inches(8.5), Inches(4.5))
    frame = body.text_frame
    frame.text = "一、细胞膜的结构\n二、物质跨膜运输\n三、信号的跨膜转导"
    for paragraph in frame.paragraphs[1:]:
        paragraph.font.size = Pt(24)
    frame.paragraphs[0].font.size = Pt(28)

    slide3 = prs.slides.add_slide(blank)
    body3 = slide3.shapes.add_textbox(Inches(0.6), Inches(0.6), Inches(8.5), Inches(0.9))
    frame3 = body3.text_frame
    frame3.text = "细胞膜与物质运输（正文页）"
    frame3.paragraphs[0].font.size = Pt(28)
    body3b = slide3.shapes.add_textbox(Inches(0.6), Inches(1.8), Inches(8.5), Inches(3.6))
    frame3b = body3b.text_frame
    frame3b.text = (
        "细胞膜由磷脂双分子层和膜蛋白构成。"
        "膜运输分为被动运输与主动运输；主动运输依赖 ATP 提供的能量进行逆浓度梯度转运。"
        "信号跨膜转导依赖膜受体与配体结合后的构象变化。"
    )
    prs.save(path)


def build_json(path: Path) -> None:
    payload = {
        "schema_version": "1.0",
        "document": {
            "name": "阶段二验收外部JSON（合成样例）",
            "type": "txt",
            "summary": "仅用于验证外部知识点导入流程",
        },
        "subject": {"id": None, "name": "生物化学"},
        "chapter_tree": [
            {
                "id": "c1",
                "name": "阶段二验收章节",
                "children": [{"id": "c1-1", "name": "验收子章节"}],
            }
        ],
        "knowledge_points": [
            {
                "point_id": "phase2-verify-001",
                "title": "阶段二验收知识点",
                "content": "该知识点仅用于验证外部 AI JSON 导入的校验、预览与保存流程。",
                "chapter_path": ["阶段二验收章节", "验收子章节"],
                "category": "basic_concept",
                "importance": "low",
                "key_terms": ["验收", "合成样例"],
                "source": {"document_name": "阶段二验收外部JSON（合成样例）", "slide": 1},
                "prerequisites": [],
                "confidence": 0.5,
            }
        ],
        "metadata": {
            "model": "acceptance-script",
            "generated_at": "2026-10-21T00:00:00Z",
            "shard_index": 1,
            "shard_total": 1,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    pptx_path = OUT / "phase2-acceptance-sample.pptx"
    json_path = OUT / "phase2-acceptance-sample.json"
    build_pptx(pptx_path)
    build_json(json_path)
    print(pptx_path)
    print(json_path)
