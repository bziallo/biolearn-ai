"""Restore BioLearn AI data from a backup directory.

Usage (from the repository root):
    python scripts/restore_data.py <backup-dir> [--force]

Safety rules:
- Refuses to run while the backend is listening on the configured port.
- Moves the current data aside to ``backend/data/_restore_previous_<ts>``
  instead of deleting it.
- Requires ``--force`` when the target data directory already has content.
- Runs ``alembic upgrade head`` afterwards so an older backup is migrated
  forward; migrations never drop existing rows.
"""

from __future__ import annotations

import argparse
import shutil
import socket
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if not (BACKEND / "app").is_dir():
    BACKEND = ROOT
DATA = BACKEND / "data"


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore BioLearn AI data")
    parser.add_argument("backup_dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    source = Path(args.backup_dir).expanduser().resolve()
    database = source / "biolearn.db"
    if not database.is_file():
        print(f"[ERROR] 备份目录中没有 biolearn.db：{source}")
        return 1

    if port_in_use("127.0.0.1", args.port):
        print(f"[ERROR] 端口 {args.port} 上仍有 BioLearn AI 在运行。")
        print("        请先运行 stop.bat 关闭服务，再执行恢复。")
        return 2

    try:
        with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as conn:
            check = conn.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                print(f"[ERROR] 备份数据库损坏：{check}")
                return 3
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "knowledge_points" not in tables:
                print("[ERROR] 备份看起来不是 BioLearn AI 数据库。")
                return 4
            points = conn.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0]
    except sqlite3.Error as exc:
        print(f"[ERROR] 无法打开备份数据库：{exc}")
        return 5

    target_db = DATA / "biolearn.db"
    if target_db.exists() and not args.force:
        print(f"[ERROR] 当前数据已存在：{target_db}")
        print("        确认覆盖请加 --force（旧数据会被移动到 _restore_previous_*）。")
        return 6

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    DATA.mkdir(parents=True, exist_ok=True)
    previous = DATA / f"_restore_previous_{stamp}"
    previous.mkdir(parents=True, exist_ok=True)
    for name in ("biolearn.db", "uploads", "ai_config.json"):
        current = DATA / name
        if current.exists():
            shutil.move(str(current), str(previous / name))
    print(f"[OK]   旧数据已移动到：{previous}")

    shutil.copy2(database, target_db)
    print(f"[OK]   数据库已恢复（备份中 {points} 条知识点）")

    uploads = source / "uploads"
    if uploads.is_dir():
        shutil.copytree(uploads, DATA / "uploads", dirs_exist_ok=True)
        print("[OK]   上传文件已恢复")
    ai_config = source / "ai_config.json"
    if ai_config.is_file():
        shutil.copy2(ai_config, DATA / "ai_config.json")
        print("[OK]   AI 运行时配置已恢复")

    sys.path.insert(0, str(BACKEND))
    try:
        from alembic import command
        from alembic.config import Config

        config = Config(str(BACKEND / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND / "alembic"))
        command.upgrade(config, "head")
        print("[OK]   数据库结构已升级到最新版本")
    except Exception as exc:
        print(f"[WARN] 自动迁移失败：{exc}")
        print("       请手动运行 start.bat，它会再次尝试迁移。")

    print("\n恢复完成。运行 start.bat 启动系统。")
    print(f"如需回退，旧数据仍在：{previous}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
