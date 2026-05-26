"""Tests for the client update release registration helper."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "client" / "scripts" / "register-client-update.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("register_client_update", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discovers_windows_and_linux_release_metadata(tmp_path: Path) -> None:
    """A tag release should register one draft row per target artifact."""
    module = _load_script_module()
    assets_dir = tmp_path / "release-assets"
    assets_dir.mkdir()
    tag = "v1.2.3"

    cases = [
        (
            "ojikbms-client-v1.2.3-windows-x64-setup.metadata.json",
            "windows",
            "x86_64",
            "nsis",
            "ojikbms-client-v1.2.3-windows-x64-setup.exe",
        ),
        (
            "ojikbms-client-v1.2.3-linux-x64-appimage.metadata.json",
            "linux",
            "x86_64",
            "appimage",
            "ojikbms-client-v1.2.3-linux-x64-appimage.AppImage",
        ),
    ]
    for filename, target_os, arch, installer_kind, asset_name in cases:
        (assets_dir / asset_name).write_bytes(b"artifact")
        (assets_dir / f"{asset_name}.sig").write_text("signature", encoding="utf-8")
        (assets_dir / filename).write_text(
            json.dumps(
                {
                    "version": "1.2.3",
                    "target_os": target_os,
                    "arch": arch,
                    "installer_kind": installer_kind,
                    "asset_name": asset_name,
                    "asset_size_bytes": 8,
                    "app_size_bytes": 12,
                    "asset_sha256": "a" * 64,
                    "tauri_signature": "signature",
                }
            ),
            encoding="utf-8",
        )

    payloads = module.build_payloads(assets_dir, tag, "Speeditidious/OJIK-BMS")

    assert [p["target_os"] for p in payloads] == ["linux", "windows"]
    assert {p["installer_kind"] for p in payloads} == {"appimage", "nsis"}
    assert all(p["version"] == "1.2.3" for p in payloads)
    assert all("/releases/download/v1.2.3/" in p["update_url"] for p in payloads)
    assert all(p["asset_size_bytes"] == 12 for p in payloads)
