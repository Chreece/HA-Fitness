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




def test_existing_physical_device_registry_name_is_refreshed_after_identity_enrichment():
    block = RUNTIME.split("def ensure_sensor_device", 1)[1].split(
        "def request_hub_reload", 1
    )[0]
    assert 'registry_updates = {' in block
    assert '"name": info.get("name") or "Fitness sensor"' in block
    assert 'registry.async_update_device(device.id, **registry_updates)' in block
    # Integration-owned identity may be refreshed, but no user-name update is passed.
    assert '"name_by_user":' not in block
    assert 'name_by_user=' not in block

def test_physical_adapter_device_info_avoids_fake_protocol_devices():
    assert "def ant_receiver_device_info" in RUNTIME
    assert "def bluetooth_scanner_device_info" in RUNTIME
    assert "def adapter_device_info" not in RUNTIME


def test_bluetooth_adapter_no_longer_has_capture_active_entity():
    setup = BINARY.split("async def async_setup_entry", 1)[1].split(
        "class _RuntimeEntity", 1
    )[0]
    assert "adapter_entities.append(AdapterCapture" not in setup


def test_per_sensor_capture_state_is_removed():
    assert "class SensorTransportCaptureActive" not in BINARY
    assert "SensorTransportCaptureActive(runtime" not in BINARY
    assert "_bluetooth_capture_active" in RUNTIME  # registry cleanup only


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


def test_training_load_requires_reliable_personal_baseline():
    load = FRONTEND.split("class FitnessTrainingLoadCard", 1)[1].split(
        "class FitnessWorkoutRpeCard", 1
    )[0]
    assert "baselineReliable" in load
    assert "recent != null && recent > 0" in load
    assert "baseline != null && baseline > 0" in load
    assert "workouts7 != null && workouts7 >= 2" in load
    assert "if (!hasLoadData)" in load


def test_hr_baseline_has_explicit_baseline_current_difference_and_heat_axis():
    comparison = FRONTEND.split("class FitnessComparisonCard", 1)[1].split(
        "class FitnessSleepStageCard", 1
    )[0]
    assert "labels.baseline" in comparison
    assert "labels.current" in comparison
    assert "labels.difference" in comparison
    assert "heat-axis" in comparison
    # HR comparisons now prefer the user's real HR-reserve zones when available,
    # with the translated legacy heat axis retained only as the fallback.
    assert "_heartRateGradient" in comparison
    assert "heart_rate_zones" in comparison
    assert "user-zone-axis" in comparison
    assert "linear-gradient(90deg,#42a5f5" in comparison
    assert "baseline = current - value" in comparison


def test_generic_placeholder_user_name_can_be_migrated_but_real_user_names_are_preserved():
    text = (ROOT / "custom_components/fitness/live/runtime.py").read_text(encoding="utf-8")
    assert 'getattr(device, "name_by_user", None)' in text
    assert '== "Fitness sensor"' in text
    assert 'registry_updates["name_by_user"] = None' in text
