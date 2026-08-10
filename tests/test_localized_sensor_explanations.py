from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLAIN = (
    ROOT / "custom_components/fitness/explanations.py"
).read_text(encoding="utf-8")
SENSOR = (
    ROOT / "custom_components/fitness/sensor.py"
).read_text(encoding="utf-8")


def test_explanations_support_all_profile_languages():
    for code in (
        "en", "el", "de", "fr", "es", "it", "pt", "nl",
        "pl", "ru", "uk", "tr", "zh", "ja", "ko",
    ):
        assert f'"{code}": {{' in EXPLAIN


def test_scientific_methods_are_fixed_not_ai_generated():
    assert "Banister TRIMP" in EXPLAIN
    assert "ACSM %HRR" in EXPLAIN
    assert '"HRR"' in EXPLAIN
    assert "_call_ai" not in EXPLAIN


def test_all_sensor_kinds_receive_explanatory_attributes():
    assert 'sensor_explanation(' in SENSOR
    assert '"live",' in SENSOR
    assert '"workout",' in SENSOR
    assert '"evaluation",' in SENSOR
