from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
BACKEND = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    return FRONTEND.split(start, 1)[1].split(end, 1)[0]


def test_workout_routing_rejects_sleep_sibling_entities():
    assert 'def _workout_route_candidate_allowed(field_name: str, label: str)' in BACKEND
    assert '"sleep", "awake", "time in bed"' in BACKEND
    assert '"resting heart rate" in normalized' in BACKEND
    assert "ordered = sorted((item for item in candidates if _workout_route_candidate_allowed(field_name, item[2]))" in BACKEND


def test_last_workout_card_is_sport_aware_and_bounded():
    block = _block("class FitnessWorkoutHighlightsCard", "class FitnessStrengthDetailsCard")
    assert "_fitnessWorkoutPriority" in block
    assert "last_workout_exercise_count" in block
    assert "last_workout_total_reps" in block
    assert "last_workout_volume" in block
    assert ".slice(0, 9)" in block
    assert "sleep|awake|time in bed" in block


def test_last_workout_hr_baseline_requires_evidence_and_uses_symmetric_heat():
    block = _block("class FitnessWorkoutHighlightsCard", "class FitnessStrengthDetailsCard")
    assert "comparableCount >= 3" in block
    assert "personal_baseline_average_hr_bpm" in block
    assert "current_average_hr_bpm" in block
    assert "_fitnessSymmetricHeatTone(hrDelta, 2, 5, 8)" in block
    assert "n=${comparableCount.toFixed(0)}" in block
    assert "#c62828 0%" in block and "#c62828 100%" in block


def test_recovery_hrv_baseline_requires_14_nights_and_compares_latest_hrv():
    block = _block("class FitnessRecoveryCard", "class FitnessAdaptationCard")
    assert 'sleep_hrv_latest_vs_28d_percent' in block
    assert 'sleep_hrv_baseline_nights' in block
    assert "hrvBaselineNights >= 14" in block
    assert "_fitnessSymmetricHeatTone(hrvVs, 3, 7, 12)" in block
    assert "-20%" in block and "+20%" in block


def test_sleep_summary_is_beside_pie_and_inline_values_open_data_map():
    block = _block("class FitnessSleepStageCard", "const _fitnessNumber")
    assert 'class="sleep-overview"' in block
    assert 'class="sleep-summary"' in block
    assert "grid-template-columns:minmax(124px,auto) minmax(0,1fr)" in block
    assert "durationMetric?.moreInfoEntityId" in block
    assert "scoreMetric.moreInfoEntityId" in block
    assert "hrvMetric.moreInfoEntityId" in block
    assert 'profile?.data_entities?.recovery' in FRONTEND
    assert 'profile?.data_entities?.workout' in FRONTEND
    assert 'profile?.data_entities?.evaluation' in FRONTEND


def test_vo2_card_has_heat_colours_and_three_clear_history_references():
    block = _block("class FitnessProgressCard", "class FitnessRecoveryCard")
    assert "_fitnessVo2Tone(pctPred)" in block
    assert 'class="actual-line"' in block
    assert 'class="trend-line"' in block
    assert 'class="predicted-line"' in block
    assert "predictedAbsolute" in block
    assert 'data-more-info="${_fitnessEscape(e.vo2max_percent_predicted || "")}"' in block
    assert 'data-more-info="${_fitnessEscape(e.cardiorespiratory_fitness_trend || "")}"' in block
    assert 'currentSource?.moreInfoEntityId' in block


def test_dashboard_cache_version_bumped_for_visual_change():
    assert 'FITNESS_DASHBOARD_VERSION = "2026.8.11.13"' in FRONTEND
    assert '?v=2026.8.11.13' in BACKEND
