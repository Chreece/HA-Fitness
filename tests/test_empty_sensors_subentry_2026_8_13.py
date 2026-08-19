from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
I = (ROOT / "custom_components/fitness/__init__.py").read_text()


def test_fitness_devices_are_separate_service_not_protocol_subentry():
    register = R[R.index("async def async_register_hub"):R.index("def _cleanup_legacy_profile_infrastructure")]
    assert "await self.async_ensure_devices_hub()" in register
    assert 'DEVICES_HUB_ENTRY_TYPE = "devices_hub"' in R
    assert "self.ensure_sensors_subentry()" not in register


def test_sensor_count_never_removes_or_creates_subentry_during_delete_cleanup():
    block = R[R.index("def _schedule_deleted_sensor_cleanup"):R.index("def forget_sensor")]
    assert "async_remove_subentry" not in block
    assert "async_add_subentry" not in block
    assert "ensure_sensors_subentry" not in block


def test_profile_live_device_is_created_once_and_never_runtime_deleted():
    assert "runtime.ensure_profile_live_registry(entry)" in I
    assert "cleanup_profile_live_registry" not in I
    block = R[R.index("def ensure_profile_live_registry"):R.index("def _start_presence_monitor")]
    assert "async_get_or_create" in block
    assert "async_remove_device" not in block
    assert "entity_registry" not in block
