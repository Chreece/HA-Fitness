from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()


def _section(start: str, end: str) -> str:
    return JS[JS.index(start):JS.index(end, JS.index(start))]


def test_rpe_card_queries_the_newest_performed_workout_and_rates_that_exact_uid():
    card = _section("class FitnessWorkoutRpeCard", "class FitnessWorkoutCard")
    assert 'type:"fitness/workouts/list"' in card
    assert 'limit:1' in card
    assert 'this._rpeWorkout = Array.isArray(result?.workouts) ? (result.workouts[0] || null)' in card
    assert 'type:"fitness/workouts/rpe"' in card
    assert 'workout_id:latest.uid' in card


def test_workout_viewer_has_per_workout_rpe_and_real_osm_map_tiles():
    card = _section("class FitnessWorkoutCard", "const FITNESS_FEATURE_TEXT")
    assert 'data-workout-rpe=' in card
    assert 'type:"fitness/workouts/rpe"' in card
    assert 'workout_id:w.uid' in card
    assert 'https://tile.openstreetmap.org/' in card
    assert 'class="workout-map-tile"' in card
    assert 'class="map-attribution"' in card
    assert 'class="workout-meta"' in card
    assert 'Avg speed' in card
    assert 'Moving time' in card


def test_backend_rates_selected_workout_without_turning_it_into_manual_edit():
    assert 'vol.Required("type"): "fitness/workouts/rpe"' in DASHBOARD
    assert 'async def websocket_workouts_rpe' in DASHBOARD
    assert 'manager.async_set_workout_rpe(' in DASHBOARD
    assert 'async def async_set_workout_rpe(' in MANAGER
    assert 'self._apply_user_rpe_override(candidate, value).as_persistent_dict()' in MANAGER
    rpe_method = MANAGER[MANAGER.index('async def async_set_workout_rpe('):MANAGER.index('async def async_set_session_rpe(')]
    assert 'fitness_manual_edit' not in rpe_method
    assert 'async_delete_calendar_workout' not in rpe_method


def test_overview_prioritizes_wellness_and_drops_session_state():
    card = _section("class FitnessTodayCard", "class FitnessWellnessCard")
    assert '"training_readiness"' in card
    assert '"last_sleep_recovery_score"' in card
    assert '"last_sleep_score"' in card
    assert '"hrv_last_night"' in card
    assert '"resting_hr"' in card
    assert '"vo2max"' in card
    assert 'e.session_status' not in card


def test_non_cast_dashboard_does_not_repaint_gradient_on_nested_shell():
    assert ':host(:not([fitness-cast-receiver])) ha-card.tv-shell{min-height:max(var(--fitness-dashboard-viewport-floor,0px),calc(100dvh - var(--fitness-dashboard-host-top,0px)))!important;background:transparent!important}' in JS
