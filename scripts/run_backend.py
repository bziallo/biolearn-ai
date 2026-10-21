"""Launch the BioLearn AI backend (production or development).

Usage (from the repository root):
    python scripts/run_backend.py [--host 127.0.0.1] [--port 8000]
                                  [--reload] [--log-level info]

The script checks the environment before starting and prints actionable
messages for the common failure cases: missing virtualenv/dependencies,
occupied port, and missing AI configuration (the app still starts without
AI; only AI features are disabled).
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
# Source checkout: scripts/../backend. Portable build: python/ + app/ at ROOT.
if not (BACKEND / "app").is_dir():
    BACKEND = ROOT


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def _line_buffer():  # type: ignore[no-untyped-def]
    """Return a line-buffered text stream for redirectable console output."""

    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return None
    import io

    return io.TextIOWrapper(
        buffer,
        encoding="utf-8",
        errors="replace",
        line_buffering=True,
        write_through=True,
    )


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs, never overriding real environment variables."""

    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def lan_addresses() -> list[str]:
    """Best-effort list of this machine's LAN IPv4 addresses."""

    addresses: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(0.5)
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1, never routable
            addresses.append(probe.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in addresses and not address.startswith("127."):
                addresses.append(address)
    except OSError:
        pass
    return addresses


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the BioLearn AI backend")
    parser.add_argument("--host", default=None, help="默认 127.0.0.1；--lan 时为 0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default=None)
    parser.add_argument(
        "--lan",
        action="store_true",
        help="显式允许局域网设备（手机）访问；需要配置 ACCESS_TOKEN 才建议开启",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(BACKEND))
    load_env_file(BACKEND / "config.env")
    os.chdir(BACKEND)

    stream = _line_buffer()
    if stream is not None:
        sys.stdout = stream
        sys.stderr = stream

    try:
        import uvicorn
    except ImportError:
        print("[ERROR] 未安装后端依赖（uvicorn）。")
        print("        请先运行 install.bat，或执行：")
        print("        cd backend && python -m pip install -e .")
        return 2

    try:
        import app.main  # noqa: F401
    except Exception as exc:  # pragma: no cover - defensive startup message
        print(f"[ERROR] 后端导入失败：{exc}")
        print("        请确认已安装依赖，并检查 backend/app 是否完整。")
        return 3

    from app.core.config import get_settings

    settings = get_settings()
    lan_mode = args.lan or settings.allow_lan
    host = args.host or ("0.0.0.0" if lan_mode else "127.0.0.1")
    log_level = (args.log_level or settings.log_level or "info").lower()
    log_dir = settings.resolved(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    if port_in_use(host, args.port):
        print(f"[ERROR] 端口 {args.port} 已被占用，后端无法启动。")
        print("        可能是上一次启动的 BioLearn AI 仍在运行。")
        print("        请运行 stop.bat 停止，或在 .env 中修改端口后重新启动。")
        return 4

    if not settings.ai_configured:
        print("[WARN] 尚未配置 AI（AI_API_BASE / AI_API_KEY / AI_MODEL 为空）。")
        print("       系统仍可导入、审核和练习，但 AI 识别与出题不可用。")
        print("       可在页面“AI 设置”中填写，或配置 .env。")

    if lan_mode:
        print("[WARN] 局域网模式已开启：同网段设备可以访问本服务。")
        if settings.auth_required:
            print("[OK]   已启用访问口令（ACCESS_TOKEN），其他设备需填写相同口令。")
        else:
            print("[WARN] 未设置 ACCESS_TOKEN：同网段任何设备都能读写数据。")
            print("       建议在 .env 中设置一个随机口令后再开启 --lan。")
        for address in lan_addresses():
            print(f"[INFO] 手机请填写：http://{address}:{args.port}/api/v1")
    else:
        print("[INFO] 仅本机可访问（默认安全配置）。需要手机访问请加 --lan，")
        print("       同时建议设置 ACCESS_TOKEN 与 CORS_EXTRA_ORIGINS。")

    print(f"[INFO] 数据库：{settings.database_url}")
    print(f"[INFO] 上传目录：{settings.resolved(settings.upload_dir)}")
    print(f"[INFO] 日志目录：{log_dir}")
    print(f"[INFO] 访问地址：http://{host if host != '0.0.0.0' else '127.0.0.1'}:{args.port}/")
    print("[INFO] 关闭窗口或按 Ctrl+C 可停止服务。")
    if settings.serve_frontend and not (
        settings.resolved(settings.frontend_dist_dir) / "index.html"
    ).is_file():
        print("[WARN] 未找到前端构建产物（frontend/dist/index.html）。")
        print("       只提供 API；请运行 build_frontend.bat 生成前端。")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=args.port,
        reload=args.reload,
        log_level=log_level,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
