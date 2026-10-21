"""Pre-start maintenance: verify Python, skip or apply migrations safely.

Run by start.bat before the backend starts. It:
1. Verifies the virtualenv and backend dependencies.
2. Creates .env from .env.example on first run (never overwrites).
3. Shows pending Alembic revisions.
4. Creates an automatic backup before upgrading an existing database.
5. Applies migrations and records the revision that was migrated.

Migrations in this project only add tables/columns and never drop user data.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATA = BACKEND / "data"


def fail(message: str) -> int:
    print(f"[ERROR] {message}")
    return 1


def main() -> int:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))

    try:
        from alembic import command
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine
    except ImportError as exc:
        return fail(
            f"缺少后端依赖（{exc.name}）。请先运行 install.bat 安装依赖。"
        )

    env_file = ROOT / ".env"
    example = ROOT / ".env.example"
    if not env_file.exists() and example.exists():
        shutil.copy2(example, env_file)
        print("[OK]   已从 .env.example 创建 .env；如需 AI 功能请填写 AI 配置。")

    from app.core.config import get_settings
    from app.db.session import normalize_database_url, resolve_sqlite_path

    settings = get_settings()
    data_dir = settings.resolved(settings.ai_config_path).parent
    data_dir.mkdir(parents=True, exist_ok=True)
    (settings.resolved(settings.log_dir)).mkdir(parents=True, exist_ok=True)

    upload_dir = settings.resolved(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    database_url = normalize_database_url(settings.database_url)
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    db_path = resolve_sqlite_path(database_url)
    existed = bool(db_path and db_path.exists())

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()

    if not existed:
        print("[INFO] 首次启动：正在初始化数据库…")
        command.upgrade(config, "head")
        print("[OK]   数据库已初始化。")
        return 0

    if current is None:
        return fail(
            "数据库文件存在但没有迁移记录，可能是损坏或非本系统文件。"
            "请先备份 backend/data，再决定是否重建。"
        )

    rev_head = _head_revision(config)
    if current == rev_head:
        print(f"[INFO] 数据库结构已是最新（{current}）。")
        _integrity(db_path)
        return 0

    print(f"[INFO] 检测到数据库升级：{current} -> {rev_head}")
    print("       升级前会自动备份，迁移只新增结构，不会删除已有数据。")
    backup = _auto_backup(db_path)
    if backup is None:
        return fail("自动备份失败，已中止升级以免数据丢失。")

    command.upgrade(config, "head")
    _integrity(db_path)
    print(f"[OK]   数据库已升级到 {rev_head}；升级前备份：{backup}")
    return 0


def _head_revision(config: Config) -> str:
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(config)
    return script.get_current_head() or ""


def _integrity(db_path: Path | None) -> None:
    if db_path is None or not db_path.exists():
        return
    try:
        with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result and result[0] == "ok":
                print("[OK]   数据库完整性检查通过。")
            else:
                print(f"[WARN] 数据库完整性检查异常：{result}")
    except sqlite3.Error as exc:
        print(f"[WARN] 无法执行完整性检查：{exc}")


def _auto_backup(db_path: Path | None) -> Path | None:
    if db_path is None or not db_path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_dir = DATA / "pre_migration_backups" / stamp
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "biolearn.db"
    try:
        source = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            destination = sqlite3.connect(target)
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
    except sqlite3.Error as exc:
        print(f"[WARN] 备份失败：{exc}")
        return None
    uploads = DATA / "uploads"
    if uploads.is_dir():
        shutil.copytree(uploads, target_dir / "uploads", dirs_exist_ok=True)
    return target_dir


if __name__ == "__main__":
    sys.exit(main())
