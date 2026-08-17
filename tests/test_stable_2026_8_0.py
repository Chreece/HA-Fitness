import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_has_valid_release_version():
    manifest = json.loads(
        (ROOT / "custom_components/fitness/manifest.json").read_text()
    )
    assert manifest["version"] == "0.0.0" or re.fullmatch(
        r"\d{4}\.\d{1,2}\.\d+(?:a\d+|-beta\d+)?",
        manifest["version"],
    )


def test_single_changelog():
    assert (ROOT / "CHANGELOG.md").is_file()
    assert not list(ROOT.glob("CHANGELOG_*.md"))
