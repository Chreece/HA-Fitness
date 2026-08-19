from pathlib import Path

ROOT = Path(__file__).parents[1]
FIT = (ROOT / "custom_components/fitness/device_adapters/garmin/fit.py").read_text()
GFDI = (ROOT / "custom_components/fitness/device_adapters/garmin/gfdi.py").read_text()
COORD = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text()
CATALOG = (ROOT / "custom_components/fitness/health_catalog.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
STRINGS = (ROOT / "custom_components/fitness/strings.json").read_text()


def test_garmin_parser_covers_documented_all_day_health_messages():
    for message in (
        "monitoring", "monitoring_hr_data", "stress_level", "respiration_rate",
        "spo2_data", "sleep_level", "sleep_assessment", "hrv_status_summary",
        "hrv_value", "hsa_step_data", "hsa_spo2_data", "hsa_stress_data",
        "hsa_respiration_data", "hsa_heart_rate_data", "hsa_body_battery_data",
        "skin_temp_overnight", "hsa_wrist_temperature_data", "max_met_data",
        "weight_scale", "blood_pressure",
    ):
        assert f'"{message}"' in FIT


def test_garmin_health_mapping_preserves_major_wellness_metrics():
    for metric in (
        "steps", "distance_m", "calories", "active_calories", "heart_rate",
        "resting_heart_rate", "stress", "respiratory_rate", "spo2",
        "body_battery", "body_battery_charged", "body_battery_drained",
        "hrv_ms", "beat_interval_ms", "vo2_max", "skin_temperature",
        "weight", "bmi", "body_fat", "body_water", "muscle_mass",
        "bone_mass", "systolic_blood_pressure", "diastolic_blood_pressure",
    ):
        assert f'"{metric}"' in FIT
        assert f'HealthMetricSpec("{metric}"' in CATALOG


def test_garmin_body_battery_and_wrist_temperature_use_fit_profile_field_names():
    assert '_first(values, "level", "body_battery"' in FIT
    assert '_first(values, "value", "wrist_temperature", "temperature")' in FIT
    assert 'values.get("nightly_value")' in FIT
    assert 'values.get("average_7_day_deviation")' in FIT


def test_garmin_sleep_assessment_without_timestamp_merges_into_staged_night():
    assert 'FIT sleep_assessment has no timestamp field' in FIT
    assert 'candidate = sessions[-1]' in FIT
    assert '"recovery_score": ("sleep_recovery_score",)' in FIT
    assert '"disturbance_count": ("awakenings_count",)' in FIT


def test_garmin_circular_health_files_are_refreshed_and_import_is_chunked():
    assert "_catalog_item_fingerprint" in COORD
    assert "newest_health" in COORD
    assert "refresh_items" in COORD
    assert 'if force or str(cached.get("catalog_fingerprint") or "") != fingerprint' in COORD
    assert "for offset in range(0, max(len(health_points), 1), point_chunk)" in COORD


def test_garmin_manual_sync_label_no_longer_claims_workouts_only():
    assert '"name": "Sync Garmin now"' in STRINGS


def test_daily_summary_semantics_cover_new_garmin_metrics():
    assert '"active_calories"' in MANAGER
    assert '"body_battery_charged"' in MANAGER
    assert '"body_battery"' in MANAGER
    assert '"vo2_max"' in MANAGER
