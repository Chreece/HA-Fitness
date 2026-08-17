"""HACS repository/release layout contracts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUSTOM_COMPONENTS = ROOT / "custom_components"
HACS_JSON = ROOT / "hacs.json"
FITNESS_MANIFEST = CUSTOM_COMPONENTS / "fitness" / "manifest.json"


def test_hacs_repository_has_exactly_one_nested_integration() -> None:
    """HACS must be able to infer the integration directory/domain."""
    hacs = json.loads(HACS_JSON.read_text(encoding="utf-8"))
    assert hacs["name"] == "Fitness"
    assert hacs.get("content_in_root", False) is False

    integration_dirs = sorted(
        path.name
        for path in CUSTOM_COMPONENTS.iterdir()
        if path.is_dir() and (path / "manifest.json").is_file()
    )
    assert integration_dirs == ["fitness"]


def test_hacs_manifest_domain_matches_repository_directory() -> None:
    """Prevent HACS from ever resolving custom_components/None/manifest.json."""
    manifest = json.loads(FITNESS_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["domain"] == "fitness"
    assert manifest["name"] == "Fitness"
    assert isinstance(manifest["version"], str)
    assert manifest["version"].strip()
