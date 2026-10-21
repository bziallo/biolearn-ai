"""Remove synthetic acceptance data created while verifying phase-2 pipelines.

Deletes only rows whose names contain the explicitly listed markers, and only
after printing exactly what will be removed. Real courseware, reviewed
knowledge points, user questions and practice records are never matched.

Usage:
    backend\\.venv\\Scripts\\python.exe scripts/cleanup_acceptance_data.py --dry-run
    backend\\.venv\\Scripts\\python.exe scripts/cleanup_acceptance_data.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if not (BACKEND / "app").is_dir():
    BACKEND = ROOT
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Chapter,
    Document,
    DocumentChunk,
    ImportJob,
    KnowledgePoint,
)

DOCUMENT_MARKERS = (
    "阶段二验收",
    "Phase2",
    "½×¶Î",
    "验收临时外部JSON",
)
CHAPTER_MARKERS = (
    "阶段二验收",
    "一、细胞膜的结构",
    "½×¶Î",
    "验收临时外部JSON",
    "验收临时章节",
)
KNOWLEDGE_MARKERS = ("阶段二验收知识点", "验证知识点")


def _matches(value: str | None, markers: tuple[str, ...]) -> bool:
    return bool(value) and any(marker in value for marker in markers)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually delete")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()
    apply = args.apply

    with SessionLocal() as db:
        documents = [
            doc
            for doc in db.scalars(select(Document)).all()
            if _matches(doc.name, DOCUMENT_MARKERS)
            or _matches(doc.original_filename, DOCUMENT_MARKERS)
        ]
        chapters = [
            chapter
            for chapter in db.scalars(select(Chapter)).all()
            if _matches(chapter.name, CHAPTER_MARKERS)
        ]  
        points = [
            point
            for point in db.scalars(select(KnowledgePoint)).all()
            if _matches(point.name, KNOWLEDGE_MARKERS)
        ]

        print(f"[plan] documents={len(documents)} chapters={len(chapters)} points={len(points)}")
        for doc in documents:
            chunks = db.scalar(
                select(DocumentChunk).where(DocumentChunk.document_id == doc.id).limit(1)
            )
            print(f"  doc  {doc.id} {doc.name!r} chunks={'yes' if chunks else 'no'}")
        for chapter in chapters:
            print(f"  chap {chapter.id} {chapter.name!r}")
        for point in points:
            print(f"  point {point.id} {point.name!r} status={point.review_status}")

        if not apply:
            print("[dry-run] 未删除任何数据；确认无误后加 --apply。")
            return 0

        removed_documents = len(documents)
        for doc in documents:
            jobs = db.scalars(select(ImportJob).where(ImportJob.document_id == doc.id)).all()
            for job in jobs:
                db.delete(job)
            db.delete(doc)
        for point in points:
            db.delete(point)
        for chapter in chapters:
            db.delete(chapter)
        db.commit()
        print(f"[done] 删除资料 {removed_documents}、知识点 {len(points)}、章节 {len(chapters)}")
        print("       上传目录中对应的原始文件未自动删除，可按需手动清理。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
