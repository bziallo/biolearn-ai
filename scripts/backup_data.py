"""Create a timestamped, tested backup of BioLearn AI data.

Usage (from the repository root):
    python scripts/backup_data.py [--output-dir D:\\BioLearnBackup]

What is backed up:
- backend/data/biolearn.db   (SQLite, copied with the SQLite backup API)
- backend/data/uploads/      (original courseware and external JSON files)
- backend/data/ai_config.json (runtime AI settings, contains the API key)
- .env.example / alembic revision

What is NOT backed up: .env (copy it manually if you customized it).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if not (BACKEND / "app").is_dir():
    BACKEND = ROOT
DATA = BACKEND / "data"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_sqlite(source: Path, target: Path) -> None:
    source_conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        target_conn = sqlite3.connect(target)
        try:
            source_conn.backup(target_conn)
            result = target_conn.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError(f"备份数据库完整性检查失败：{result}")
        finally:
            target_conn.close()
    finally:
        source_conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up BioLearn AI data")
    parser.add_argument(
        "--output-dir",
        default=str(Path("D:/BioLearnBackup"))
        if Path("D:/").exists()
        else str(ROOT / "backups"),
        help="备份根目录",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="数据目录（默认 backend/data；测试时可指向临时目录）",
    )
    args = parser.parse_args()
    data = Path(args.data_dir).expanduser().resolve() if args.data_dir else DATA

    database = data / "biolearn.db"
    if not database.is_file():
        print(f"[ERROR] 未找到数据库：{database}")
        print("        请先在项目根目录运行 start.bat 完成初始化。")
        return 1

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    target = Path(args.output_dir) / timestamp
    target.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] 备份到：{target}")
    copy_sqlite(database, target / "biolearn.db")
    print(f"[OK]   数据库 -> biolearn.db（SHA-256 {sha256(target / 'biolearn.db')[:16]}…）")

    uploads = data / "uploads"
    if uploads.is_dir():
        shutil.copytree(uploads, target / "uploads", dirs_exist_ok=True)
        count = sum(1 for _ in (target / "uploads").iterdir())
        print(f"[OK]   上传文件 -> uploads/（{count} 个文件）")
    else:
        print("[WARN] 没有上传目录，跳过。")

    ai_config = data / "ai_config.json"
    if ai_config.is_file():
        shutil.copy2(ai_config, target / "ai_config.json")
        print("[OK]   AI 运行时配置 -> ai_config.json（含密钥，请妥善保管）")
    else:
        print("[INFO] 没有 AI 运行时配置，跳过。")

    env_example = ROOT / ".env.example"
    if env_example.is_file():
        shutil.copy2(env_example, target / ".env.example")
    if (ROOT / ".env").is_file():
        print("[INFO] 检测到 .env；为避免密钥外泄，未自动复制，请手动备份。")

    print("\n备份完成。恢复方法：关闭 BioLearn AI，运行 restore.bat 并选择该目录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
