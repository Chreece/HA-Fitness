from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()


def test_tv_ai_cards_are_registered_and_selectable_only_for_ai_profiles():
    assert 'id:"ai_today", element:"fitness-ai-today-card"' in FRONTEND
    assert 'id:"ai_last_workout", element:"fitness-ai-last-workout-card"' in FRONTEND
    assert 'filter((item) => !item.ai || this._profile?.ai_enabled)' in FRONTEND
    assert '"ai_today"' in TV
    assert '"ai_last_workout"' in TV


def test_dashboard_payload_exposes_last_workout_ai_result():
    assert '"ai_workout_verdict": manager.ai_workout_verdict' in DASHBOARD
    assert '"ai_workout_evaluation": manager.ai_workout' in DASHBOARD


def test_ai_cards_have_distinct_modern_rest_and_workout_presentations():
    assert 'class FitnessAiTodayCard' in FRONTEND
    assert 'class FitnessAiLastWorkoutCard' in FRONTEND
    assert 'mdi:power-sleep' in FRONTEND
    assert "ha-card.rest" in FRONTEND
    assert 'class="verdict"' in FRONTEND
