"""2026.8.11 native DeviceInfo, adapter lifecycle and UI safety regressions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
BINARY = (ROOT / "custom_components/fitness/binary_sensor.py").read_text()
FRONTEND = (
    ROOT / "custom_components/fitness/frontend/fitness-dashboard.js"
).read_text()


def test_sensor_device_info_uses_valid_primary_shape_for_ha_2026_8():
    block = RUNTIME.split("def sensor_device_info", 1)[1].split(
        "def sensor_identity", 1
    )[0]
    assert '"identifiers"' in block
    assert '"name"' in block
    assert "default_name" not in block


def test_manual_registry_creation_does_not_mix_default_name_with_primary_fields():
    block = RUNTIME.split("def ensure_sensor_device", 1)[1].split(
        "def request_hub_reload", 1
    )[0]
    assert '"name": info.get("name") or "Fitness sensor"' in block
    assert '"default_name"' not in block


def test_adapter_device_info_avoids_primary_plus_translation_key_mix():
    block = RUNTIME.split("def adapter_device_info", 1)[1].split(
        "def sensor_device_info", 1
    )[0]
    assert "translation_key=" not in block
    assert "identifiers=" in block
    assert "manufacturer=" in block


def test_bluetooth_adapter_no_longer_has_capture_active_entity():
    setup = BINARY.split("async def async_setup_entry", 1)[1].split(
        "class _RuntimeEntity", 1
    )[0]
    assert "adapter_entities.append(AdapterCapture" not in setup


def test_capture_active_is_materialized_per_physical_sensor_transport():
    assert "class SensorTransportCaptureActive" in BINARY
    assert 'added.append(SensorTransportCaptureActive(runtime, sensor_id, transport))' in BINARY
    cls = BINARY.split("class SensorTransportCaptureActive", 1)[1].split(
        "class AdapterProblem", 1
    )[0]
    assert "sensor_transport_capture_enabled" in cls
    assert "adapter_enabled" in cls


def test_disabling_adapter_unloads_module_and_invalidates_volatile_state():
    setter = RUNTIME.split("async def async_set_transport_enabled", 1)[1].split(
        "async def async_register_profile", 1
    )[0]
    assert "await self.async_refresh_modules()" in setter
    assert "self._mark_transport_runtime_inactive(transport)" in setter
    refresh = RUNTIME.split("async def async_refresh_modules", 1)[1].split(
        "async def async_begin_setup_discovery", 1
    )[0]
    assert "await self.providers.pop(name).async_shutdown()" in refresh


def test_training_load_requires_real_evidence_not_zero_placeholder():
    load = FRONTEND.split("class FitnessTrainingLoadCard", 1)[1].split(
        "class FitnessWorkoutRpeCard", 1
    )[0]
    assert "hasWorkoutLoadEvidence" in load
    assert "recent != null && recent > 0" in load
    assert "workouts7 != null && workouts7 > 0" in load
    assert "mins7 != null && mins7 > 0" in load


def test_hr_baseline_has_explicit_baseline_current_difference_and_heat_axis():
    comparison = FRONTEND.split("class FitnessComparisonCard", 1)[1].split(
        "class FitnessSleepStageCard", 1
    )[0]
    assert 'labels.baseline || "Baseline"' in comparison
    assert 'labels.current || "Current"' in comparison
    assert 'labels.difference || "Difference"' in comparison
    assert "heat-axis" in comparison
    assert "linear-gradient(90deg,#e53935" in comparison
    assert "baseline = current - value" in comparison
