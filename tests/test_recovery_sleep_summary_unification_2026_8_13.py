from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
LANGS = ("en","el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko")


def test_readiness_and_recovery_are_visually_unified_but_keep_distinct_entities():
    card = JS[JS.index("class FitnessRecoveryCard"):JS.index("class FitnessTrainingLoadCard")]
    assert 'class="recovery-readiness-panel"' in card
    assert "e.readiness" in card
    assert "e.estimated_recovery_time" in card
    assert 'class="recovery-score-stack"' in card
    assert 'kind:"readiness"' in card
    assert 'kind:"progress"' in card
    assert 'class="next-workout entity-link"' in card


def test_sleep_summary_metrics_live_only_in_last_sleep_card():
    sleep = JS[JS.index("class FitnessSleepStageCard"):JS.index("const _fitnessNumber")]
    recovery = JS[JS.index("class FitnessRecoveryCard"):JS.index("class FitnessTrainingLoadCard")]
    for key in ("last_sleep_score", "last_sleep_hrv", "sleep_deficit_7d"):
        assert key in sleep
    assert "sleep-summary" in sleep
    assert "e.last_sleep_duration" not in recovery
    assert "e.last_sleep_score" not in recovery
    assert "e.last_sleep_hrv" not in recovery
    assert "sleep_deficit_7d" not in recovery
    assert '_fitnessSleepSourceMetric(this._profile, this._hass, "last_sleep_hrv"' in recovery


def test_readiness_component_bars_have_state_colours():
    card = JS[JS.index("class FitnessRecoveryCard"):JS.index("class FitnessTrainingLoadCard")]
    assert "componentTone" in card
    for colour in ("#2e7d32", "#00897b", "#f9a825", "#ef6c00", "#c62828"):
        assert colour in card
    assert "var(--component-tone)" in card


def test_recovery_limiter_is_localized_in_all_languages():
    for code in LANGS:
        start = DASH.index(f'"{code}": {{')
        chunk = DASH[start:start+13000]
        for key in (
            "recovery_limiting_factor", "limiter_muscular_recovery",
            "limiter_autonomic_recovery", "limiter_sleep_recovery",
            "limiter_overall_readiness", "limiter_workout_dose",
            "recovery_readiness",
        ):
            assert f'"{key}":' in chunk


def test_frontend_backend_revision_match():
    f = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    b = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert f and b and f.group(1) == b.group(1) == "2026.8.11.14"
