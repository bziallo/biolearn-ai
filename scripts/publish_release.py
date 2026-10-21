"""Publish the V1.0.0 GitHub Release with the portable ZIP attached.

Run from the project root (or via publish-release.bat).

Credentials: the script asks ``git credential fill`` for the GitHub
username/password already stored by Git Credential Manager, so the token never
has to be typed again or written into a file. If no credential is stored the
script prints the manual steps instead of failing silently.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "bziallo"
REPO = "biolearn-ai"
TAG = "v1.0.0"
TITLE = "BioLearn AI V1.0.0"
ASSET = ROOT / "dist" / "BioLearnAI-1.0.0-win64.zip"
GIT_CANDIDATES = (
    r"C:\Users\bzlciallo\.dsh\profiles\desktop\node_modules\@dsh-ops\bash-win32-x64\ucrt64\bin\git.exe",
    "git",
)
BODY = """Windows 本地免安装版（便携版）

- 解压后双击 `BioLearnAI.cmd`（等同 `start.bat`）即可启动
- 浏览器访问 http://127.0.0.1:8000/
- 无需安装 Python；首次启动自动创建数据库并完成迁移
- `stop.bat` 停止、`backup.bat` 备份、`restore.bat` 恢复
- 数据全部保存在解压目录的 `data\\` 下

SHA-256: {sha256}

仅本机使用，默认只监听 127.0.0.1，请勿直接暴露到公网。
"""


def git_binary() -> str:
    for candidate in GIT_CANDIDATES:
        try:
            subprocess.run([candidate, "--version"], capture_output=True, check=True)
            return candidate
        except (OSError, subprocess.SubprocessError):
            continue
    raise SystemExit("[ERROR] 未找到 git.exe")


def git_credential(git: str) -> tuple[str, str] | None:
    payload = "protocol=https\nhost=github.com\n\n"
    try:
        result = subprocess.run(
            [git, "credential", "fill"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    password = values.get("password", "")
    if not password:
        return None
    return values.get("username", ""), password


def api(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "BioLearnAI-release-script",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {"message": body}
        return exc.code, parsed


def upload_asset(upload_url: str, token: str, asset: Path) -> tuple[int, dict]:
    """Upload the ZIP as a raw request body.

    ``urllib`` users often wrap the body in ``multipart/form-data``; the GitHub
    Releases upload endpoint expects the raw binary instead, otherwise the
    stored asset gets the boundary prefix and stops being a valid ZIP.
    """

    try:
        payload = asset.read_bytes()
    except OSError as exc:
        return 0, {"message": str(exc)}
    request = urllib.request.Request(
        upload_url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/zip",
            "Content-Length": str(len(payload)),
            "User-Agent": "BioLearnAI-release-script",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {"message": exc.read().decode("utf-8", "replace")}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, {"message": str(exc)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if not ASSET.is_file():
        print(f"[ERROR] 未找到便携版：{ASSET}")
        print("        请先运行：backend\\.venv\\Scripts\\python.exe scripts\\build_portable.py")
        return 1
    asset_hash = sha256(ASSET)
    print(f"[INFO] 附件 {ASSET.name}（{ASSET.stat().st_size / 1024 / 1024:.1f} MB）", flush=True)
    print(f"[INFO] SHA-256 {asset_hash}", flush=True)

    git = git_binary()
    credential = git_credential(git)
    if credential is None:
        print("[ERROR] 本机没有可用的 GitHub 凭据，无法自动创建 Release。", flush=True)
        print("        请在终端执行一次：git push origin v1.0.0", flush=True)
        print("        然后重新运行本脚本；或按 MANUAL_RELEASE_STEPS.txt 手动发布。", flush=True)
        return 2
    token = credential[1]
    print(f"[OK] 已读取本机凭据（用户 {credential[0]}）", flush=True)

    status, repo = api("GET", f"/repos/{OWNER}/{REPO}", token)
    if status != 200:
        print(f"[ERROR] 无法访问仓库：{status} {repo.get('message')}", flush=True)
        return 3
    print("[OK] 仓库可访问", flush=True)

    status, existing = api("GET", f"/repos/{OWNER}/{REPO}/releases/tags/{TAG}", token)
    if status == 200:
        print(f"[INFO] Release {TAG} 已存在：{existing.get('html_url')}", flush=True)
        release = existing
    else:
        status, release = api(
            "POST",
            f"/repos/{OWNER}/{REPO}/releases",
            token,
            {
                "tag_name": TAG,
                "target_commitish": "main",
                "name": TITLE,
                "body": BODY.format(sha256=asset_hash),
                "draft": False,
                "prerelease": False,
            },
        )
        if status not in (200, 201):
            print(f"[ERROR] 创建 Release 失败：{status} {release.get('message')}", flush=True)
            return 4
        print(f"[OK] Release 已创建：{release.get('html_url')}", flush=True)

    upload_url = release["upload_url"].split("{")[0] + f"?name={ASSET.name}"
    print("[INFO] 正在上传附件（约 135 MB，请稍候）…", flush=True)
    status, asset_info = upload_asset(upload_url, token, ASSET)
    if status in (200, 201):
        print(f"[OK] 附件已上传：{asset_info.get('browser_download_url')}", flush=True)
    elif status == 422:
        print("[INFO] 附件已存在，跳过上传。", flush=True)
    elif status == 0:
        print(f"[ERROR] 上传未完成（网络中断或超时）：{asset_info.get('message')}", flush=True)
        print(f"        可重新运行本脚本；Release 页面：{release.get('html_url')}", flush=True)
        return 5
    else:
        print(f"[ERROR] 附件上传失败：{status} {asset_info.get('message')}", flush=True)
        return 5

    print(flush=True)
    print(f"Release 页面：{release.get('html_url')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
