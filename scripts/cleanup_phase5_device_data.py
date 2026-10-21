"""Delete the synthetic data created for phase-5 Android acceptance.

Only rows tied to the explicit subject id are touched. Always run with
--dry-run first; --apply performs the deletion.

Usage:
    python scripts/cleanup_phase5_device_data.py --subject-id <id> --dry-run
    python scripts/cleanup_phase5_device_data.py --subject-id <id> --apply
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
    ImportJob,
    KnowledgePoint,
    PracticeAnswer,
    PracticeSession,
    Question,
    QuestionGenerationJob,
    Subject,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        subject = db.get(Subject, args.subject_id)
        if subject is None:
            print(f"[INFO] 学科不存在：{args.subject_id}")
            return 1
        documents = db.scalars(
            select(Document).where(Document.subject_id == subject.id)
        ).all()
        chapters = db.scalars(
            select(Chapter).where(Chapter.subject_id == subject.id)
        ).all()
        points = db.scalars(
            select(KnowledgePoint).where(KnowledgePoint.subject_id == subject.id)
        ).all()
        questions = db.scalars(
            select(Question).where(Question.subject_id == subject.id)
        ).all()
        sessions = db.scalars(
            select(PracticeSession).where(PracticeSession.subject_id == subject.id)
        ).all()
        jobs = db.scalars(
            select(QuestionGenerationJob).where(
                QuestionGenerationJob.subject_id == subject.id
            )
        ).all()
        imports = db.scalars(
            select(ImportJob).where(
                ImportJob.document_id.in_([document.id for document in documents])
            )
        ).all() if documents else []
        answers = db.scalars(
            select(PracticeAnswer).where(
                PracticeAnswer.session_id.in_([session.id for session in sessions])
            )
        ).all() if sessions else []

        print(
            f"[plan] subject={subject.name!r} documents={len(documents)} "
            f"chapters={len(chapters)} points={len(points)} questions={len(questions)} "
            f"sessions={len(sessions)} answers={len(answers)} jobs={len(jobs)} "
            f"imports={len(imports)}"
        )
        for document in documents:
            print(f"  document {document.id} {document.name!r} {document.storage_name!r}")
        for question in questions:
            print(f"  question {question.id} {question.type} {question.status} {question.stem[:40]!r}")
        for session in sessions:
            print(f"  session {session.id} {session.status} score={session.score}")

        if not args.apply:
            print("[dry-run] 未删除任何数据；确认无误后加 --apply。")
            return 0

        for answer in answers:
            db.delete(answer)
        for session in sessions:
            db.delete(session)
        for question in questions:
            db.delete(question)
        for job in jobs:
            db.delete(job)
        for point in points:
            db.delete(point)
        for chapter in chapters:
            db.delete(chapter)
        for document in documents:
            db.delete(document)
        for job in imports:
            db.delete(job)
        db.delete(subject)
        db.commit()
        print(
            f"[done] 已删除合成数据：学科 1、资料 {len(documents)}、章节 {len(chapters)}、"
            f"知识点 {len(points)}、题目 {len(questions)}、练习 {len(sessions)}、"
            f"作答 {len(answers)}、出题任务 {len(jobs)}、导入任务 {len(imports)}"
        )
        print("       上传目录中的原始文件未自动删除，可按需手动清理。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
