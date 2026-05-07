#!/usr/bin/env python3
"""CI script: POST a draft client update row to /internal/client-updates/from-release.

Expected environment variables:
  API_URL                    e.g. https://api.ojikbms.kr
  CLIENT_UPDATE_INGEST_TOKEN shared secret (GitHub Actions secret)
  GITHUB_REPOSITORY          e.g. Speeditidious/OJIK-BMS
  TAG_NAME                   e.g. v1.0.0-beta.2

Expected files in the release-assets directory (relative to repo root):
  ojikbms-client-<TAG_NAME>-windows-x64-setup.exe
  ojikbms-client-<TAG_NAME>-windows-x64-setup.exe.sig
  ojikbms-client-<TAG_NAME>-windows-x64-setup.metadata.json
"""

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path


def _require_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        sys.exit(f"ERROR: required env var {name!r} is not set")
    return val


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    api_url = _require_env("API_URL").rstrip("/")
    token = _require_env("CLIENT_UPDATE_INGEST_TOKEN")
    repo = _require_env("GITHUB_REPOSITORY")
    tag = _require_env("TAG_NAME")

    # Strip leading 'v' for version field, keep tag as-is for URLs.
    version = tag.lstrip("v")
    asset_base = f"ojikbms-client-{tag}-windows-x64-setup"
    assets_dir = Path("release-assets")

    exe_path = assets_dir / f"{asset_base}.exe"
    sig_path = assets_dir / f"{asset_base}.exe.sig"
    meta_path = assets_dir / f"{asset_base}.metadata.json"

    if not exe_path.exists():
        sys.exit(f"ERROR: installer not found: {exe_path}")
    if not sig_path.exists():
        sys.exit(f"ERROR: signature not found: {sig_path}")

    tauri_signature = sig_path.read_text(encoding="utf-8").strip()

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        asset_size_bytes = int(meta["asset_size_bytes"])
        asset_sha256 = meta["asset_sha256"].lower()
    else:
        print("WARNING: metadata.json not found, computing sha256 from exe (slower)", file=sys.stderr)
        asset_size_bytes = exe_path.stat().st_size
        asset_sha256 = _sha256_file(exe_path)

    release_page_url = f"https://github.com/{repo}/releases/tag/{tag}"
    update_url = f"https://github.com/{repo}/releases/download/{tag}/{asset_base}.exe"

    payload = {
        "version": version,
        "channel": "stable",
        "target_os": "windows",
        "arch": "x86_64",
        "installer_kind": "nsis",
        "title": f"OJIK BMS Client v{version}",
        "body_markdown": (
            f"GitHub Release에서 생성된 클라이언트 업데이트 초안입니다.\n"
            f"공개 전에 릴리즈 노트를 확인하고 타이틀/내용을 수정하세요.\n\n"
            f"릴리즈 페이지: {release_page_url}"
        ),
        "release_page_url": release_page_url,
        "update_url": update_url,
        "tauri_signature": tauri_signature,
        "asset_size_bytes": asset_size_bytes,
        "asset_sha256": asset_sha256,
        "mandatory": False,
        "min_supported_version": None,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url}/internal/client-updates/from-release",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-OJIK-Internal-Token": token,
        },
        method="POST",
    )

    print(f"Registering draft update row for v{version} ...")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            action = "created" if resp_body.get("created") else "updated"
            print(f"OK: draft row {action} (id={resp_body['id']}, published={resp_body['is_published']})")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        sys.exit(f"ERROR: API returned {exc.code}: {err_body}")
    except Exception as exc:
        sys.exit(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
