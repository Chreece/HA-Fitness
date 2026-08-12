from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")

SUPPORTED = (
    "en", "el", "de", "fr", "es", "it", "pt", "nl",
    "pl", "ru", "uk", "tr", "zh", "ja", "ko",
)


def test_readiness_attributes_do_not_call_missing_entity_method():
    assert "self._readiness_data_used(readiness)" not in SENSOR
    assert '"confidence_percent": readiness.get("confidence_percent")' in SENSOR
    assert '"components": readiness.get("components")' in SENSOR


def test_recovery_card_restores_sleep_score_as_percentage():
    section = JS[
        JS.index("class FitnessRecoveryCard"):
        JS.index("class FitnessTrainingLoadCard")
    ]
    assert "e.last_sleep_score" in section
    assert "_sleepScoreMetric" in section
    assert '`${Math.max(0, Math.min(100, value)).toFixed(0)}%`' in section


def test_all_device_translation_keys_exist_in_all_languages():
    strings = json.loads(
        (ROOT / "custom_components/fitness/strings.json").read_text(encoding="utf-8")
    )

    for key in ("evaluation", "live", "workout", "recovery"):
        assert strings["device"][key]["name"]

    for lang in SUPPORTED:
        data = json.loads(
            (ROOT / f"custom_components/fitness/translations/{lang}.json")
            .read_text(encoding="utf-8")
        )

        for key in ("evaluation", "live", "workout", "recovery"):
            assert data["device"][key]["name"]
