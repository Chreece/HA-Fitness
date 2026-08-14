"""Device-page performance and adaptive UI regressions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components/fitness"
RUNTIME = (FIT / "live/runtime.py").read_text(encoding="utf-8")
BLUETOOTH = (FIT / "live/bluetooth.py").read_text(encoding="utf-8")
BUTTON = (FIT / "button.py").read_text(encoding="utf-8")
BINARY = (FIT / "binary_sensor.py").read_text(encoding="utf-8")
FRONTEND = (FIT / "frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_gatt_support_check_never_resolves_ble_device_or_proxy():
    support = RUNTIME.split("def bluetooth_gatt_supported", 1)[1].split(
        "def bluetooth_gatt_capable", 1
    )[0]
    assert "async_ble_device_from_address" not in support
    assert 'endpoint.metadata.get("connectable", False)' in support
    assert "SensorGattConnectButton" not in BUTTON
    assert "SensorGattDisconnectButton" not in BUTTON

def test_ble_device_resolution_happens_only_in_real_connection_path():
    assert "async_ble_device_from_address" in BLUETOOTH
    connection = BLUETOOTH.split("async def async_connect_profile", 1)[1].split(
        "async def _async_enrich_identity", 1
    )[0]
    assert "async_ble_device_from_address" in connection


def test_per_sensor_capture_entities_and_buttons_are_gone():
    assert "SensorTransportStartCaptureButton" not in BUTTON
    assert "SensorTransportStopCaptureButton" not in BUTTON
    assert "SensorTransportCaptureActive" not in BINARY
    assert "async_set_sensor_transport_capture" not in RUNTIME
    assert "_sensor_transport_capture" not in RUNTIME


def test_old_capture_registry_entities_are_pruned_once_on_hub_setup():
    cleanup = RUNTIME.split("def _cleanup_obsolete_hub_capture_entities", 1)[1].split(
        "async def _async_start_hub_modules", 1
    )[0]
    assert "_bluetooth_start_capture" in cleanup
    assert "_bluetooth_stop_capture" in cleanup
    assert "_bluetooth_capture_active" in cleanup
    assert "registry.async_remove" in cleanup


def test_hr_comparison_uses_semantic_key_not_entity_id_name():
    comparison = FRONTEND.split("class FitnessComparisonCard", 1)[1].split(
        "class FitnessSleepStageCard", 1
    )[0]
    assert 'metric.key === "last_workout_hr_vs_baseline"' in comparison
    assert "baseline-number" in comparison
    assert 'labels.baseline || "Baseline"' in comparison


def test_baseline_comparisons_need_at_least_three_comparable_workouts():
    comparison = FRONTEND.split("class FitnessComparisonCard", 1)[1].split(
        "class FitnessSleepStageCard", 1
    )[0]
    assert "last_workout_comparable_count" in comparison
    assert "comparableCount >= 3" in comparison


def test_training_load_card_requires_reliable_load_baseline():
    load = FRONTEND.split("class FitnessTrainingLoadCard", 1)[1].split(
        "class FitnessWorkoutRpeCard", 1
    )[0]
    assert "baselineReliable" in load
    assert "workouts7 != null && workouts7 >= 2" in load
    assert "if (!hasLoadData)" in load


def test_recovery_has_numeric_hrv_vs_baseline_bar_only_when_baseline_exists():
    recovery = FRONTEND.split("class FitnessRecoveryCard", 1)[1].split(
        "class FitnessTrainingAdaptationCard", 1
    )[0]
    assert 'sleep_hrv_latest_ms' in recovery
    assert 'sleep_hrv_28d_mean_ms' in recovery
    assert "hrvBaselineReady" in recovery
    assert "hrv-baseline-marker" in recovery
    assert "hrv-current-marker" in recovery
    assert "hrvBaselineBar" in recovery


def test_frontend_revision_is_bumped_for_visible_changes():
    assert 'const FITNESS_DASHBOARD_VERSION = "2026.8.11.2";' in FRONTEND
