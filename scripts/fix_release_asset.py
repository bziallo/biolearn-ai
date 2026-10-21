"""Replace a broken Release asset with a correctly uploaded ZIP.

The first upload used a multipart wrapper, which GitHub stored verbatim (the
file was not a valid ZIP). This helper:
1. downloads the stored asset and checks whether it is a valid ZIP,
2. deletes it when it is not,
3. re-uploads the local ZIP as a raw body and verifies the size.

Usage: python scripts/fix_release_asset.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pub", ROOT / "scripts" / "publish_release.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


def is_zip(path: Path) -> bool:
    """Return True only for a raw ZIP (no multipart wrapper, no truncation).

    ``zipfile`` tolerates a leading envelope by scanning for the first local
    header, so callers must also check the magic bytes explicitly.
    """

    try:
        with path.open("rb") as handle:
            head = handle.read(4)
        if head != b"PK\x03\x04":
            return False
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None and len(archive.namelist()) > 100
    except (zipfile.BadZipFile, OSError):
        return False


def main() -> int:
    asset = publish.ASSET
    credential = publish.git_credential(publish.git_binary())
    if credential is None:
        print("[ERROR] 没有可用的 GitHub 凭据。")
        return 2
    token = credential[1]

    status, release = publish.api(
        "GET",
        f"/repos/{publish.OWNER}/{publish.REPO}/releases/tags/{publish.TAG}",
        token,
    )
    if status != 200:
        print(f"[ERROR] 读取 Release 失败：{status}")
        return 3

    assets = {item["name"]: item for item in release.get("assets", [])}
    existing = assets.get(asset.name)
    if existing:
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe.zip"
            try:
                urllib.request.urlretrieve(existing["browser_download_url"], probe)
            except OSError as exc:
                print(f"[WARN] 下载校验失败，按损坏处理：{exc}")
                probe.write_bytes(b"")
            valid = is_zip(probe)
            size = probe.stat().st_size if probe.exists() else 0
        print(f"[INFO] 已存附件大小 {size} 字节，是否为有效 ZIP：{valid}")
        if valid:
            print("[OK] 附件已是有效 ZIP，无需修复。")
            return 0
        status, response = publish.api(
            "DELETE",
            f"/repos/{publish.OWNER}/{publish.REPO}/releases/assets/{existing['id']}",
            token,
        )
        if status not in (204, 200):
            print(f"[ERROR] 删除损坏附件失败：{status} {response}")
            return 4
        print("[OK] 已删除损坏附件")

    upload_url = release["upload_url"].split("{")[0] + f"?name={asset.name}"
    print("[INFO] 重新上传（原始二进制）…")
    status, info = publish.upload_asset(upload_url, token, asset)
    if status not in (200, 201):
        print(f"[ERROR] 上传失败：{status} {info.get('message')}")
        return 5
    expected = asset.stat().st_size
    actual = info.get("size")
    print(f"[OK] 已上传：{info.get('browser_download_url')}（{actual} 字节，本地 {expected} 字节）")
    if actual != expected:
        print("[WARN] 大小不一致，请人工复核。")
    local_hash = hashlib.sha256(asset.read_bytes()).hexdigest()
    print(f"本地 SHA-256: {local_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
