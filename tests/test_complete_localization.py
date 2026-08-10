import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "custom_components/fitness/translations"
EXPECTED = {
    "en", "el", "de", "fr", "es", "it", "pt", "nl",
    "pl", "ru", "uk", "tr", "zh", "ja", "ko",
}


def _shape(value, prefix=""):
    result = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            result.add(path)
            result.update(_shape(child, path))
    return result


def test_exact_supported_language_set_is_shipped():
    assert {path.stem for path in TRANSLATIONS.glob("*.json")} == EXPECTED


def test_translation_structures_are_identical():
    english = json.loads(
        (TRANSLATIONS / "en.json").read_text(encoding="utf-8")
    )
    expected_shape = _shape(english)

    for path in TRANSLATIONS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert _shape(data) == expected_shape, path.name


def test_every_setup_field_has_meaningful_localized_help():
    for path in TRANSLATIONS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for root_name in ("config", "options"):
            for step_name, step in data[root_name]["step"].items():
                fields = step.get("data", {})
                if not fields:
                    continue
                descriptions = step.get("data_description", {})
                for key in fields:
                    assert key in descriptions, (
                        path.name, root_name, step_name, key
                    )
                    help_text = descriptions[key].strip()
                    minimum = 12 if path.stem in {"zh", "ja", "ko"} else 30
                    assert len(help_text) >= minimum, (
                        path.name, root_name, step_name, key, help_text
                    )


def test_strings_json_is_english_canonical_translation():
    strings = json.loads(
        (ROOT / "custom_components/fitness/strings.json").read_text(
            encoding="utf-8"
        )
    )
    english = json.loads(
        (TRANSLATIONS / "en.json").read_text(encoding="utf-8")
    )
    assert strings == english
