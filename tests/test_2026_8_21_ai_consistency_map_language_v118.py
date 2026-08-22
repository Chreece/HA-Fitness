from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()


def test_today_ai_editor_is_immediately_below_title_before_chips():
    block = JS.split("class FitnessAiTodayCard", 1)[1].split("class FitnessAiLastWorkoutCard", 1)[0]
    assert '</button>${promptBox}${actions}${chips?' in block
    assert '.ai-user-text{display:grid;gap:5px;margin:12px 0 7px}' in block


def test_daily_and_seven_day_plans_share_one_canonical_today_decision():
    assert '"canonical_today_plan": self.ai_daily_plan if self.ai_daily_plan_date == self._today_iso() else None' in MANAGER
    assert 'day date_offset 0 MUST match its rest/workout decision' in MANAGER
    assert "def _sync_training_plan_today_from_daily" in MANAGER
    assert MANAGER.count("self._sync_training_plan_today_from_daily()") >= 2


def test_workout_map_accepts_nested_and_geojson_routes():
    block = JS.split("class FitnessWorkoutCard", 1)[1].split("class FitnessSleepRecoveryCard", 1)[0]
    assert 'new Set(["gps_track","gps_points","route","track","coordinates","geometry","polyline","encoded_polyline","summary_polyline"])' in block
    assert 'String(value.type||"").toLowerCase()==="linestring"' in block
    assert 'geojson?[b,a]:[a,b]' in block
    assert "selected-route" in block and "tile.openstreetmap.org" in block


def test_v118_cache_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
    dashboard = (ROOT / "custom_components/fitness/dashboard.py").read_text()
    accounts = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
    assert '?v=unreleased-138' in dashboard
    assert 'frontend_version = "unreleased-138"' in accounts


def test_ai_prompts_use_single_logic_prompt_with_profile_output_language():
    assert "MANDATORY OUTPUT LANGUAGE for user-facing strings" in MANAGER
    assert "MANDATORY OUTPUT LANGUAGE: {strings['language']}" in MANAGER
