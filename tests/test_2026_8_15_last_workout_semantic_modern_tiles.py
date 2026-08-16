from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
BACKEND = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_known_workout_metrics_use_semantic_labels_not_source_entity_names():
    assert 'last_workout_duration:"metric_duration"' in FRONTEND
    assert 'last_workout_avg_hr:"metric_avg_hr"' in FRONTEND
    assert 'last_workout_max_hr:"metric_max_hr"' in FRONTEND
    assert 'last_workout_calories:"metric_calories"' in FRONTEND
    assert 'last_workout_total_reps:"metric_total_reps"' in FRONTEND
    assert 'last_workout_session_rpe_load:"metric_session_load"' in FRONTEND
    assert 'const semantic = _fitnessWorkoutSemanticLabel(profile, key);' in FRONTEND


def test_workout_tiles_keep_source_entity_as_click_target():
    assert 'data-more-info="${_fitnessEscape(entityId || "")}"' in FRONTEND
    assert '_fitnessWorkoutMetricTile(this._profile, key, displayLabel, display, metric.moreInfoEntityId)' in FRONTEND


def test_workout_tiles_have_modern_icon_visual_hierarchy():
    assert 'const _FITNESS_WORKOUT_METRIC_ICONS' in FRONTEND
    assert 'class="hi-head"' in FRONTEND
    assert 'class="hi-icon"' in FRONTEND
    assert 'class="hi-label"' in FRONTEND
    assert 'class="hi-value"' in FRONTEND
    assert 'linear-gradient(145deg,color-mix(in srgb,var(--primary-color) 9%' in FRONTEND


def test_workout_metric_labels_are_dashboard_translations():
    for key in (
        "metric_duration", "metric_distance", "metric_avg_hr", "metric_max_hr",
        "metric_calories", "metric_total_reps", "metric_session_load", "metric_rpe",
    ):
        assert f'"{key}"' in BACKEND
    assert '"metric_duration":"Διάρκεια"' in BACKEND
    assert '"metric_avg_hr":"Μέσος καρδιακός ρυθμός"' in BACKEND
    assert '"metric_session_load":"Φορτίο συνεδρίας"' in BACKEND
