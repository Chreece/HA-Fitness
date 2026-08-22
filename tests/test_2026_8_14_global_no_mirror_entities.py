from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_sleep_source_facts_are_never_materialized_as_fitness_entities():
    start = SENSOR.index("SLEEP_SOURCE_MIRROR_KEYS = frozenset({")
    end = SENSOR.index("\n})", start)
    block = SENSOR[start:end]
    for key in (
        "last_sleep_duration", "last_sleep_score", "last_sleep_efficiency",
        "last_sleep_time_in_bed", "last_sleep_awake", "last_sleep_light",
        "last_sleep_deep", "last_sleep_rem", "last_sleep_hrv",
        "last_sleep_average_hr", "last_sleep_respiratory_rate",
        "last_sleep_spo2", "last_sleep_recovery_score",
        "last_sleep_readiness_score",
    ):
        assert f'"{key}"' in block
    assert "SOURCE_MIRROR_KEYS = SLEEP_SOURCE_MIRROR_KEYS" in SENSOR
    assert "desc.key not in SOURCE_MIRROR_KEYS" in SENSOR
    assert "if key in SOURCE_MIRROR_KEYS:" in SENSOR


def test_recovery_keeps_only_fitness_owned_outputs():
    # Raw sleep measurements are source-routed, while these are genuine Fitness calculations.
    assert 'Desc(key="readiness"' in SENSOR
    assert 'Desc(key="estimated_recovery_time"' in SENSOR
    assert '"sleep_source_metrics": sleep_source_metrics' in DASHBOARD
    assert "def _sleep_source_metrics(" in DASHBOARD
    assert "_fitnessSleepSourceMetric" in FRONTEND
    assert "e.last_sleep_duration" not in FRONTEND
    assert "e.last_sleep_hrv" not in FRONTEND
    assert "e.last_sleep_score" not in FRONTEND


def test_evaluation_states_are_calculations_not_current_source_mirrors():
    # Sleep consistency is variability, autonomic recovery is HRV-vs-baseline,
    # cardio fitness trend is slope/change, and HRR is vs-personal-baseline.
    assert 'sleep_long_term.get("sleep_midpoint_variability_28d_min")' in SENSOR
    assert 'sleep_long_term.get("sleep_hrv_7d_vs_baseline_percent")' in SENSOR
    assert 'recorder_long_term.get("vo2max_slope_percent_per_30d")' in SENSOR
    assert 'workout_long_term.get("hrr_60s_latest_vs_90d_bpm")' in SENSOR
    assert 'latest_sleep.duration_s / 60.0' not in SENSOR[SENSOR.index("compact_map = {"):SENSOR.index("if m in compact_map:")]
    assert 'recorder_long_term.get("vo2max_current")' not in SENSOR[SENSOR.index("compact_map = {"):SENSOR.index("if m in compact_map:")]


def test_dashboard_uses_sources_for_raw_sleep_and_current_evaluation_inputs():
    assert '"evaluation_source_metrics": evaluation_source_metrics' in DASHBOARD
    assert "def _evaluation_source_metrics(" in DASHBOARD
    assert '_fitnessEvaluationSourceMetric(this._profile, this._hass, "vo2max"' in FRONTEND
    assert '_fitnessSleepSourceMetric(this._profile, this._hass, "last_sleep_hrv"' in FRONTEND
    assert 'currentSource?.moreInfoEntityId || e.cardiorespiratory_fitness_trend' in FRONTEND
    assert 'e.autonomic_recovery_trend || hrvSource?.moreInfoEntityId' in FRONTEND


def test_dashboard_version_bumped_for_no_mirror_routing():
    assert '?v=unreleased-138' in DASHBOARD
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
