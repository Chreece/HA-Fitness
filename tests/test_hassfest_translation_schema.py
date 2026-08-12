import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components/fitness"

# Home Assistant translation files permit a defined set of top-level sections.
# Keep this conservative: these are the only sections HA-Fitness currently needs.
ALLOWED_TOP_LEVEL = {
    "title",
    "config",
    "device",
    "options",
    "selector",
    "entity",
    "exceptions",
    "issues",
    "services",
    "device_automation",
    "state",
}


def test_no_custom_top_level_keys_in_strings_json():
    data = json.loads(
        (BASE / "strings.json").read_text(encoding="utf-8")
    )
    assert set(data).issubset(ALLOWED_TOP_LEVEL), (
        set(data) - ALLOWED_TOP_LEVEL
    )


def test_no_custom_top_level_keys_in_translations():
    for path in (BASE / "translations").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert set(data).issubset(ALLOWED_TOP_LEVEL), (
            path.name,
            set(data) - ALLOWED_TOP_LEVEL,
        )


def test_evaluation_provenance_is_not_in_ha_translation_json():
    assert "evaluation_provenance" not in json.loads(
        (BASE / "strings.json").read_text(encoding="utf-8")
    )
    for path in (BASE / "translations").glob("*.json"):
        assert "evaluation_provenance" not in json.loads(
            path.read_text(encoding="utf-8")
        )
