from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()


def _load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_frontend_revision_is_consistent_for_v112():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD


def test_compare_workouts_uses_personal_hr_zones_and_speed_gradients():
    assert "dashboard_heart_rate_zones" in MANAGER
    assert '"heart_rate_zones": manager.dashboard_heart_rate_zones()' in DASHBOARD
    assert "_heartRateGradient" in FRONTEND
    assert "user-zone-axis" in FRONTEND
    assert "speed-axis" in FRONTEND
    assert "linear-gradient(90deg,#f9a825,#43a047)" in FRONTEND


def test_cross_sport_comparison_has_generic_metrics():
    for key in (
        'add_percent("cadence", "avg_cadence"',
        'add_percent("distance", "distance_m"',
        'add_percent("duration", "duration_s"',
        'add_percent("calories", "calories"',
        'add_percent("repetitions", "total_reps"',
        'add_percent("volume", "volume_kg"',
        'add_percent("strength_sets", "strength_total_sets"',
    ):
        assert key in MANAGER


def test_fitness_tests_are_structured_expandable_and_exportable():
    prescriptions = _load("custom_components/fitness/workout_prescriptions.py", "fitness_prescriptions_v112")
    tests = prescriptions.fitness_test_catalog()
    assert len(tests) >= 10
    for test in tests:
        assert test["schema_version"] == 1
        assert test["id"]
        assert test["sport"]
        assert test["goal"]
        assert test["steps"]
        assert all(step["instruction"] for step in test["steps"])
    assert 'data-steps-id=' in FRONTEND
    assert 'data-export-id=' in FRONTEND
    assert '_fitnessWorkoutPrescriptionMarkup(x,this._profile,this._hass)' in FRONTEND


def test_new_workout_browser_and_test_labels_cover_all_supported_languages():
    translations = _load("custom_components/fitness/dashboard_translations.py", "fitness_dashboard_i18n_v112")
    keys = {
        "workout_history", "select_day_with_workouts", "zoom_in", "zoom_out", "reset_map",
        "fitness_tests", "guided_performance_tests", "fitness_tests_intro", "show_steps", "hide_steps",
        "duration", "moving_time", "distance", "avg_hr", "elevation", "cadence", "avg_speed",
        "max_speed", "avg_power", "weighted_power", "avg_temperature", "sets", "reps", "volume",
        "best_e1rm", "calories", "training_load", "previous_workout", "next_workout", "workout_name",
        "sport", "ai_training_plan", "goal_based_training_plan", "generating_plan", "generate_plan",
        "generate_plan_after_goal", "device_workout", "comparison_cadence", "comparison_distance",
        "comparison_duration", "comparison_calories", "comparison_elevation", "comparison_relative_effort",
        "comparison_repetitions", "comparison_volume", "comparison_strength_sets",
    }
    for language in translations.SUPPORTED_DASHBOARD_LANGUAGES:
        labels = translations.DASHBOARD_LANGUAGE_AUDIT_TEXT[language]
        assert not (keys - labels.keys()), (language, sorted(keys - labels.keys()))
        assert all(str(labels[key]).strip() for key in keys)
