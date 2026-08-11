from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
REFS = (ROOT / "custom_components/fitness/research/references.py").read_text(encoding="utf-8")


def test_compact_evaluation_domains_exist():
    for key in (
        "sleep_consistency",
        "sleep_deficit_7d",
        "autonomic_recovery_trend",
        "cardiorespiratory_fitness_trend",
        "training_load",
        "heart_rate_recovery",
        "training_recovery_relationship",
    ):
        assert f'key="{key}"' in SENSOR


def test_beta29_fine_grained_entities_are_migrated_away():
    for key in (
        "training_load_7d",
        "sleep_duration_7d_mean",
        "sleep_hrv_7d_mean",
        "resting_hr_7d_mean",
        "vo2max_28d_mean",
    ):
        assert f'"{key}"' in SENSOR  # migration list remains explicit
        assert f'key="{key}"' not in SENSOR


def test_sleep_deficit_requires_observed_nights_and_adult_reference():
    assert "len(seven) >= 5" in MANAGER
    assert "7 * 3600" in MANAGER
    assert '"nights_observed": sleep.get("nights_7d")' in SENSOR


def test_training_recovery_is_descriptive_not_causal():
    assert "_pearson_correlation" in MANAGER
    assert '"causal_interpretation": False' in SENSOR
    assert "exercise_sleep_meta_2024" in REFS


def test_vo2_long_term_slope_uses_recorder_history():
    assert '"slope_percent_per_30d"' in MANAGER
    assert "cardiorespiratory_fitness_meta_2024" in REFS
