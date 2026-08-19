from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
MANIFEST = (ROOT / "custom_components/fitness/manifest.json").read_text()

def test_sleep_stage_total_uses_source_routed_canonical_duration():
    assert '_fitnessSleepSourceMetric(this._profile, this._hass, "last_sleep_duration")' in JS
    assert "const displayTotal" in JS
    assert "${displayTotal}" in JS
    assert "e.last_sleep_duration" not in JS

def test_workout_metrics_always_remain_visible_and_route_is_optional():
    assert 'class FitnessWorkoutCard' in JS
    assert 'gps_track' in JS
    assert 'class="hero-facts"' in JS

def test_route_summary_has_full_normalized_workout_metrics():
    for key in ("last_workout_max_hr", "last_workout_vo2max", "last_workout_banister_trimp"):
        assert key in JS

def test_manifest_declares_home_assistant_components():
    import json

    manifest = json.loads(MANIFEST)
    assert "http" in manifest.get("dependencies", [])
    assert "recorder" in manifest.get("after_dependencies", [])
