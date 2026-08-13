from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_training_adaptation_is_textual_not_measurement():
    start = SENSOR.index("def state_class")
    end = SENSOR.index("def native_unit_of_measurement", start)
    section = SENSOR[start:end]
    assert '"training_adaptation_status"' in section


def test_training_adaptation_is_integrated_with_training_load():
    assert "class FitnessTrainingAdaptationCard" in JS
    evaluation = JS[JS.index("class FitnessEvaluationCard"):JS.index("class FitnessDashboardStrategy")]
    assert 'this._mount("fitness-training-adaptation-card")' not in evaluation
    load = JS[JS.index("class FitnessTrainingLoadCard"):JS.index("class FitnessCompositeCard")]
    assert "training_adaptation_status" in load
    assert "adaptTones" in load


def test_training_adaptation_card_has_state_colours():
    for state in (
        "productive", "maintaining", "insufficient_stimulus", "absent",
        "high_load", "excessive", "strained", "unproductive", "insufficient_data",
    ):
        assert f"{state}:" in JS
    for colour in ("#2e7d32", "#00897b", "#f9a825", "#ef6c00", "#d84315", "#c62828"):
        assert colour in JS


def test_frontend_resource_revision_matches():
    front = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    back = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert front and back
    assert front.group(1) == back.group(1)


def test_adaptation_card_labels_exist_for_all_languages():
    for code in ("en","el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko"):
        start = DASH.index(f'"{code}": {{')
        # every language block should contain these labels before its closing dictionary area
        chunk = DASH[start:start+5000]
        assert '"training_adaptation_card":' in chunk
        assert '"training_adaptation_subtitle":' in chunk
        assert '"adaptation_load_ratio":' in chunk
        assert '"adaptation_fitness_trend":' in chunk
        assert '"adaptation_recovery_signal":' in chunk
