"""Assign legacy rows to the first Owner (dry-run by default).

Run only after:
1. A backup exists.
2. Migration 0010 is applied.
3. The owner was created with scripts/create_owner.py.
4. This dry-run has been reviewed.

Usage:
    python scripts/backfill_owner.py --dry-run
    python scripts/backfill_owner.py --apply
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

from sqlalchemy import select, update  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    ImportJob,
    KnowledgeExtractionJob,
    PracticeSession,
    QuestionGenerationJob,
    Subject,
    User,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.role == "owner"))
        if owner is None:
            print("[ERROR] 没有 Owner；请先运行 scripts/create_owner.py")
            return 1
        subjects = db.scalars(
            select(Subject).where(Subject.owner_id.is_(None))
        ).all()
        sessions = db.scalars(
            select(PracticeSession).where(PracticeSession.user_id.is_(None))
        ).all()
        imports = db.scalars(
            select(ImportJob).where(ImportJob.created_by.is_(None))
        ).all()
        extractions = db.scalars(
            select(KnowledgeExtractionJob).where(
                KnowledgeExtractionJob.created_by.is_(None)
            )
        ).all()
        generations = db.scalars(
            select(QuestionGenerationJob).where(
                QuestionGenerationJob.created_by.is_(None)
            )
        ).all()
        print(
            f"[plan] owner={owner.username} ({owner.id}) subjects={len(subjects)} "
            f"practice_sessions={len(sessions)} import_jobs={len(imports)} "
            f"extraction_jobs={len(extractions)} generation_jobs={len(generations)}"
        )
        if not args.apply:
            print("[dry-run] 未修改任何数据；确认后加 --apply。")
            return 0

        db.execute(
            update(Subject)
            .where(Subject.owner_id.is_(None))
            .values(owner_id=owner.id)
        )
        db.execute(
            update(PracticeSession)
            .where(PracticeSession.user_id.is_(None))
            .values(user_id=owner.id)
        )
        db.execute(
            update(ImportJob)
            .where(ImportJob.created_by.is_(None))
            .values(created_by=owner.id)
        )
        db.execute(
            update(KnowledgeExtractionJob)
            .where(KnowledgeExtractionJob.created_by.is_(None))
            .values(created_by=owner.id)
        )
        db.execute(
            update(QuestionGenerationJob)
            .where(QuestionGenerationJob.created_by.is_(None))
            .values(created_by=owner.id)
        )
        db.commit()
        print("[done] 已把遗留数据归属到 Owner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
