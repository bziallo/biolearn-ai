"""Remove the synthetic practice session created during phase-3 device testing.

Only the explicitly supplied session id is touched, and only after printing
what will be deleted. Real study history is never matched by name or date.

Usage:
    backend\\.venv\\Scripts\\python.exe scripts\\cleanup_phase3_sync.py --session-id <id> --dry-run
    backend\\.venv\\Scripts\\python.exe scripts\\cleanup_phase3_sync.py --session-id <id> --apply
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
from app.models import PracticeAnswer, PracticeSession  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="explicit no-op preview")
    args = parser.parse_args()

    with SessionLocal() as db:
        session = db.get(PracticeSession, args.session_id)
        if session is None:
            print(f"[INFO] 会话不存在：{args.session_id}")
            return 1
        answers = db.scalars(
            select(PracticeAnswer).where(PracticeAnswer.session_id == session.id)
        ).all()
        print(
            f"[plan] session={session.id} status={session.status} "
            f"total={session.total_questions} answers={len(answers)} "
            f"started_at={session.started_at}"
        )
        for answer in answers:
            print(f"  answer {answer.id} correct={answer.is_correct} at={answer.answered_at}")

        if not args.apply:
            print("[dry-run] 未删除任何数据；确认无误后加 --apply。")
            return 0

        for answer in answers:
            db.delete(answer)
        db.delete(session)
        db.commit()
        print(f"[done] 已删除会话 {session.id} 与 {len(answers)} 条作答记录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
