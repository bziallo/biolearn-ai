"""Build a self-contained portable ZIP of BioLearn AI for external users.

Usage (from the repository root, with the project virtualenv):
    backend\\.venv\\Scripts\\python.exe scripts\\build_portable.py

Checks before building (aborts when failing):
- frontend/dist/index.html exists
- the running interpreter has the runtime dependencies
- the interpreter's base installation is a full CPython (not an embeddable dist)

Output: dist/BioLearnAI-<version>-win64.zip
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
STAGING = BUILD / "portable" / "BioLearnAI"
VERSION = "1.0.0"
REQUIRED_MODULES = (
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "pydantic",
    "pydantic_settings",
    "pypdf",
    "docx",
    "pptx",
    "httpx",
    "multipart",
)
IGNORE_PYC = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
IGNORE_APP = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", "data", "biolearn.db", "uploads",
    "logs", "ai_config.json", "pre_migration_backups", "_restore_previous_*",
)
IGNORE_SITE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "pip", "pip-*", "setuptools*", "wheel*", "pkg_resources",
    "*.dist-info", "tests", "test",
)
# Never ship local settings, secrets or data inside the bundled runtime.
IGNORE_PYTHON = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".env", "*.env", "data", "biolearn.db",
    "uploads", "logs", "ai_config.json",
)


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def check(python: Path) -> None:
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        fail("未找到 frontend/dist/index.html，请先运行 build_frontend.bat。")
    missing = [
        module
        for module in REQUIRED_MODULES
        if subprocess.run(
            [str(python), "-c", f"import {module}"],
            capture_output=True,
            text=True,
        ).returncode != 0
    ]
    if missing:
        fail(f"后端依赖缺失：{', '.join(missing)}；请先运行 install.bat。")
    base = Path(sys.base_prefix)
    if not (base / "Lib" / "site-packages").is_dir():
        fail(f"{base} 不是完整 CPython 运行时，无法内嵌。")
    print(f"[OK] 前置检查通过；将内嵌运行时 {base}")


def copy_runtime(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    base = Path(sys.base_prefix)
    ignore = shutil.ignore_patterns(
        "__pycache__", "*.pyc", "*.pyo", "Lib\\site-packages", "Lib/site-packages",
        "Lib\\test", "Lib\\idlelib", "Lib\\tkinter", "Lib\\ensurepip", "Doc", "Tools",
        "tcl", "Scripts", "share", "include", "libs", ".env", "*.env", "data",
    )
    shutil.copytree(base, target, ignore=ignore)
    if not (target / "python.exe").is_file():
        fail("复制 Python 运行时失败。")
    print(f"[OK] 运行时 -> {target}")


def copy_site_packages(runtime: Path) -> None:
    source = Path(sys.prefix) / "Lib" / "site-packages"
    if not source.is_dir():
        fail(f"未找到 site-packages：{source}")
    target = runtime / "Lib" / "site-packages"
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=IGNORE_SITE)
    print(f"[OK] 依赖 -> {target}")


def copy_application(staging: Path) -> None:
    shutil.copytree(BACKEND / "app", staging / "app", ignore=IGNORE_APP)
    shutil.copytree(BACKEND / "alembic", staging / "alembic", ignore=IGNORE_PYC)
    shutil.copy2(BACKEND / "alembic.ini", staging / "alembic.ini")
    shutil.copytree(ROOT / "frontend" / "dist", staging / "frontend" / "dist", dirs_exist_ok=True)
    shutil.copytree(ROOT / "scripts", staging / "scripts", ignore=IGNORE_PYC)
    shutil.copytree(ROOT / "docs", staging / "docs", ignore=IGNORE_PYC)
    for name in (
        "stop.bat", "backup.bat", "restore.bat",
        ".env.example", "README-QUICKSTART.txt",
    ):
        shutil.copy2(ROOT / name, staging / name)
    # Portable launchers resolve python\python.exe instead of backend\.venv.
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "portable_launchers.py"), str(staging)],
        check=True,
    )
    (staging / "data").mkdir(parents=True, exist_ok=True)
    print("[OK] 应用、前端、脚本 ->", staging)


def write_launcher(staging: Path) -> None:
    """Write a double-click .cmd launcher (no compilation required)."""

    content = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "cd /d \"%~dp0\"\r\n"
        "title BioLearn AI\r\n"
        "rem 统一启动入口：等价于 start.bat\r\n"
        "call \"%~dp0start.bat\"\r\n"
    )
    (staging / "BioLearnAI.cmd").write_text(content, encoding="utf-8")
    print("[OK] 启动入口 BioLearnAI.cmd")


def make_zip(target: Path) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(STAGING.rglob("*")):
            archive.write(path, Path("BioLearnAI") / path.relative_to(STAGING))
    print(f"[OK] 已生成 {target}（{target.stat().st_size / 1024 / 1024:.1f} MB）")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=VERSION)
    args = parser.parse_args()
    python = Path(sys.executable)
    check(python)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    STAGING.mkdir(parents=True)
    copy_runtime(STAGING / "python")
    copy_site_packages(STAGING / "python")
    copy_application(STAGING)
    write_launcher(STAGING)
    make_zip(DIST / f"BioLearnAI-{args.version}-win64.zip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
