"""Find and stop the BioLearn AI process listening on a local port.

Usage:
    python scripts/stop_services.py [--port 8000] [--check]

``--check`` only reports whether the port is in use (exit code 1 if free).
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def listener_pids(port: int) -> list[int]:
    """Return PIDs listening on ``port`` using Get-NetTCPConnection."""

    script = (
        f"(Get-NetTCPConnection -LocalPort {port} -State Listen "
        "-ErrorAction SilentlyContinue).OwningProcess"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return sorted(set(pids))


def main() -> int:
    parser = argparse.ArgumentParser(description="Stop BioLearn AI service")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    in_use = port_in_use("127.0.0.1", args.port)
    if args.check:
        if in_use:
            pids = listener_pids(args.port)
            print(f"running {args.port} pids={','.join(map(str, pids))}")
            return 0
        print(f"free {args.port}")
        return 1

    if not in_use:
        print(f"[INFO] 端口 {args.port} 上没有运行中的服务。")
        return 0

    pids = listener_pids(args.port)
    if not pids:
        print(f"[WARN] 端口 {args.port} 被占用，但无法确定进程 PID。")
        print("       请手动在任务管理器中结束占用该端口的 Python 进程。")
        return 1

    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            print(f"[OK]   已停止进程 {pid}")
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"[ERROR] 无法停止进程 {pid}：{exc}")
            return 1

    if port_in_use("127.0.0.1", args.port):
        print(f"[WARN] 端口 {args.port} 仍被占用，请稍后重试或手动结束进程。")
        return 1
    print(f"[OK]   端口 {args.port} 已释放。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
