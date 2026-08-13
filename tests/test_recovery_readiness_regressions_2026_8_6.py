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


def test_last_sleep_card_owns_sleep_score_summary():
    sleep = JS[
        JS.index("class FitnessSleepStageCard"):
        JS.index("const _fitnessNumber")
    ]
    recovery = JS[
        JS.index("class FitnessRecoveryCard"):
        JS.index("class FitnessTrainingLoadCard")
    ]
    assert "e.last_sleep_score" in sleep
    assert "sleep-summary" in sleep
    assert "e.last_sleep_score" not in recovery
    assert "e.last_sleep_duration" not in recovery


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
