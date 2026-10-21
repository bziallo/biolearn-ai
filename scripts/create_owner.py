"""Create the first Owner account locally (never exposed over HTTP).

Usage:
    backend\\.venv\\Scripts\\python.exe scripts\\create_owner.py --username owner

The password is requested with getpass and is never printed or written to Git.
Run migrations first (start.bat / alembic upgrade head).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if not (BACKEND / "app").is_dir():
    BACKEND = ROOT
sys.path.insert(0, str(BACKEND))

from app.core.errors import DomainError  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import auth as auth_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="owner")
    parser.add_argument("--display-name", default="Owner")
    args = parser.parse_args()

    password = getpass.getpass("Owner password (min 10 chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("[ERROR] 两次密码不一致")
        return 2

    with SessionLocal() as db:
        try:
            owner = auth_service.create_owner(
                db,
                username=args.username,
                password=password,
                display_name=args.display_name,
            )
        except DomainError as exc:
            print(f"[ERROR] {exc.message}")
            return 1
        print(f"[OK] Owner created: {owner.username} ({owner.id})")
        print("     现在所有业务接口都需要登录；共享 ACCESS_TOKEN 不再生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
