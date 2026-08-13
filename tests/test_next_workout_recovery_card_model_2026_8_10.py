from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")

LANGS = ("en","el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko")


def test_recovery_model_is_one_bounded_estimate_not_max_of_clocks():
    start = MANAGER.index("def recovery_time_evaluation")
    end = MANAGER.index("def readiness_evaluation", start)
    section = MANAGER[start:end]
    assert "fitness_next_workout_recovery_estimate_v2" in section
    assert "max(value for _name, value in candidates)" not in section
    assert "ready_for_next_workout_at" in section
    assert "estimated_recovery_low_hours" in section
    assert "estimated_recovery_high_hours" in section
    assert '"full_physiological_recovery_claimed": False' in section
    assert "recorder_long_term_evaluation()" in section


def test_recovery_card_is_prominent_beside_readiness():
    assert 'class="dual-hero"' in JS
    assert 'class="recovery-hero entity-link"' in JS
    assert 'ready_for_next_workout_at' in JS
    assert 'recovery_progress_percent' in JS
    assert 'estimated_recovery_low_hours' in JS
    assert 'estimated_recovery_high_hours' in JS
    assert 'recovery_signals' in JS
    # It must not be repeated as a tiny metric tile.
    assert 'this._metric(entityName(this._hass, e.estimated_recovery_time)' not in JS


def test_dashboard_has_recovery_labels_in_all_languages():
    for code in LANGS:
        start = DASH.index(f'"{code}": {{')
        chunk = DASH[start:start+9000]
        for key in (
            "next_workout","remaining","ready_at","recovery_window",
            "recovery_progress_label","recovery_signals_label","physio_note",
            "ready_now","confidence_short","hours_short",
        ):
            assert f'"{key}":' in chunk


def test_recovery_entity_attributes_match_all_languages():
    en = json.loads((ROOT / "custom_components/fitness/strings.json").read_text())
    expected = set(en["entity"]["sensor"]["estimated_recovery_time"]["state_attributes"])
    for code in LANGS:
        path = ROOT / "custom_components/fitness/strings.json" if code == "en" else ROOT / f"custom_components/fitness/translations/{code}.json"
        data = json.loads(path.read_text())
        attrs = data["entity"]["sensor"]["estimated_recovery_time"]["state_attributes"]
        assert set(attrs) == expected
        assert data["entity"]["sensor"]["estimated_recovery_time"]["name"]


def test_frontend_revision_matches_backend():
    front = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    back = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert front and back
    assert front.group(1) == back.group(1) == "2026.8.10.7"
