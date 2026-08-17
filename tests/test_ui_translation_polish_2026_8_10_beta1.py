import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")


def test_rpe_scale_uses_effort_gradient_not_primary_color():
    assert "--rpe-hue:" in FRONTEND
    assert "hsl(var(--rpe-hue)" in FRONTEND
    assert ".rpe-choice.selected{border-color:hsl(var(--rpe-hue)" in FRONTEND


def test_readiness_confidence_is_localized():
    assert "confidence from available evidence</span>" not in FRONTEND
    assert "l.certain_compact" in FRONTEND
    assert "readinessCertainty" in FRONTEND


def test_personal_context_empty_history_is_localized():
    for code in ("en", "el", "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "uk", "tr", "zh", "ja", "ko"):
        assert f'"{code}":' in MANAGER
    assert "Δεν υπάρχουν ακόμη αρκετές" in MANAGER


def test_translation_attribute_structure_matches_english():
    directory = ROOT / "custom_components/fitness/translations"
    english = json.loads((directory / "en.json").read_text(encoding="utf-8"))["entity"]["sensor"]
    expected = {key: set(value.get("state_attributes", {})) for key, value in english.items()}
    for path in directory.glob("*.json"):
        sensors = json.loads(path.read_text(encoding="utf-8"))["entity"]["sensor"]
        assert set(english).issubset(sensors), path.name
        for key, attributes in expected.items():
            assert attributes.issubset(sensors[key].get("state_attributes", {})), (path.name, key)
