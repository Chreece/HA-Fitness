from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
WORKOUTS = (ROOT / "custom_components/fitness/providers/workouts.py").read_text()
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text()

def test_custom_profile_cards_use_natural_sections_height():
    assert 'getGridOptions() { return {columns: 12, min_columns: 6}; }' in JS
    assert 'rows: 7' not in JS

def test_sleep_stage_card_formats_long_minutes():
    assert '_formatMinutes(value, unit = "min")' in JS
    assert 'const displayTotal' in JS
    assert '${displayTotal}' in JS
    assert 'this._formatMinutes(item.value, unit)' in JS

def test_merged_workout_sport_normalizes_nested_garmin_shape():
    assert '"sportTypeKey"' in WORKOUTS
    assert 'def workout_sport_kind' in WORKOUTS
    assert '_sport_token(value) or str(value)' in WORKOUTS
    assert 'attrs["sport"] = sport' in SENSOR

def test_running_pace_uses_merged_workout_and_distance_time_fallback():
    assert 'profile?.latest_workout?.sport !== "running"' in JS
    assert 'last_workout_moving_time' in JS
    assert 'timeMinutes / distanceKm' in JS
    assert '"latest_workout": {' in DASH
    assert 'workout_sport_kind(manager.latest_workout())' in DASH
