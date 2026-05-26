#!/usr/bin/env python3
"""CI script: POST draft client update rows to /internal/client-updates/from-release.

Expected environment variables:
  API_URL                    e.g. https://api.ojikbms.kr
  CLIENT_UPDATE_INGEST_TOKEN shared secret (GitHub Actions secret)
  GITHUB_REPOSITORY          e.g. Speeditidious/OJIK-BMS
  TAG_NAME                   e.g. v1.0.0-beta.2

Expected files in the release-assets directory (relative to repo root):
  one or more *.metadata.json files produced by the Tauri build jobs.
  Each metadata file must include asset_name, target_os, arch, installer_kind,
  asset_size_bytes, asset_sha256, and tauri_signature. When app_size_bytes is
  present, it is used as the display size for update announcements.
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


def build_payloads(assets_dir: Path, tag: str, repo: str) -> list[dict]:
    """Build one ingest payload per release target metadata file."""
    version = tag.lstrip("v")
    release_page_url = f"https://github.com/{repo}/releases/tag/{tag}"
    payloads: list[dict] = []

    for meta_path in sorted(assets_dir.glob("*.metadata.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        asset_name = str(meta["asset_name"])
        asset_path = assets_dir / asset_name
        sig_path = assets_dir / f"{asset_name}.sig"

        if not asset_path.exists():
            sys.exit(f"ERROR: installer not found: {asset_path}")

        tauri_signature = str(meta.get("tauri_signature") or "").strip()
        if not tauri_signature:
            if not sig_path.exists():
                sys.exit(f"ERROR: signature not found: {sig_path}")
            tauri_signature = sig_path.read_text(encoding="utf-8").strip()

        asset_size_bytes = int(
            meta.get("app_size_bytes")
            or meta.get("asset_size_bytes")
            or asset_path.stat().st_size
        )
        asset_sha256 = str(meta.get("asset_sha256") or _sha256_file(asset_path)).lower()
        update_url = f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"

        payloads.append(
            {
                "version": version,
                "channel": "stable",
                "target_os": meta["target_os"],
                "arch": meta["arch"],
                "installer_kind": meta["installer_kind"],
                "title": f"OJIK BMS Client v{version}",
                "body_markdown": (
                    "GitHub Release에서 생성된 클라이언트 업데이트 초안입니다.\n"
                    "공개 전에 릴리즈 노트를 확인하고 타이틀/내용을 수정하세요.\n\n"
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
        )

    if not payloads:
        sys.exit(f"ERROR: no metadata files found in {assets_dir}")

    return payloads


def post_payload(api_url: str, token: str, payload: dict) -> None:
    """POST one draft update payload to the API."""
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

    target = f"{payload['target_os']}/{payload['arch']}/{payload['installer_kind']}"
    print(f"Registering draft update row for v{payload['version']} ({target}) ...")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            action = "created" if resp_body.get("created") else "updated"
            print(
                f"OK: draft row {action} "
                f"(id={resp_body['id']}, published={resp_body['is_published']})"
            )
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        sys.exit(f"ERROR: API returned {exc.code}: {err_body}")
    except Exception as exc:
        sys.exit(f"ERROR: {exc}")


def main() -> None:
    api_url = _require_env("API_URL").rstrip("/")
    token = _require_env("CLIENT_UPDATE_INGEST_TOKEN")
    repo = _require_env("GITHUB_REPOSITORY")
    tag = _require_env("TAG_NAME")
    assets_dir = Path("release-assets")

    for payload in build_payloads(assets_dir, tag, repo):
        post_payload(api_url, token, payload)


if __name__ == "__main__":
    main()
