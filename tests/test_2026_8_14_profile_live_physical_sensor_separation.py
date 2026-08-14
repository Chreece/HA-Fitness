from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text()
CONFIG_FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text()
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text()
SELECT = (ROOT / "custom_components/fitness/select.py").read_text()
HA_ENTITIES = (ROOT / "custom_components/fitness/live/ha_entities.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()

RAW_PROFILE_MIRRORS = {
    "current_heart_rate",
    "current_power",
    "current_cadence",
    "current_speed",
    "current_distance",
    "current_altitude",
}


def _descriptions_block() -> str:
    start = SENSOR.index("DESCRIPTIONS = (")
    end = SENSOR.index("async def async_setup_entry", start)
    return SENSOR[start:end]


def test_profile_live_device_has_no_raw_physical_sensor_mirrors():
    descriptions = _descriptions_block()
    for key in RAW_PROFILE_MIRRORS:
        assert f'Desc(key="{key}"' not in descriptions

    # Old profile mirrors are explicitly migrated away on next profile setup.
    for key in RAW_PROFILE_MIRRORS:
        assert f'"{key}"' in SENSOR[SENSOR.index("deprecated_live_mirror_keys"):]


def test_physical_measurements_remain_on_physical_sensor_device_only():
    assert "class PhysicalMetricSensor(_PhysicalSensorEntity)" in HA_ENTITIES
    assert "self._attr_device_info = runtime.sensor_device_info(self.sensor_id)" in HA_ENTITIES
    assert 'self._attr_device_info = device_info(entry, desc.kind)' in SENSOR
    assert 'DeviceInfo(\n                identifiers={(DOMAIN, f"live_sensor:{resolved_id}")}' in RUNTIME


def test_profile_live_calculation_surface_is_stable_and_assignment_independent():
    assert "manager.remember_materialized_sensors(live_keys, persist=True)" in SENSOR
    assert 'desc.kind == "live" and not native_live_enabled' not in SENSOR
    assert "profile_has_assigned_live_sensor(entry)" not in SELECT
    assert "entities = [\n        StartWorkoutButton" in BUTTON


def test_accept_and_reassign_sensor_do_not_reload_profiles():
    assign_start = CONFIG_FLOW.index("async def async_step_assign_live_sensor")
    reassign_start = CONFIG_FLOW.index("async def async_step_sensor_assignment")
    assign_block = CONFIG_FLOW[assign_start:reassign_start]
    reassign_block = CONFIG_FLOW[reassign_start:]

    assert "async_reload(" not in assign_block
    assert "async_reload(" not in reassign_block
    assert "suppress_entry_reload_once" in assign_block
    assert "suppress_entry_reload_once" in reassign_block
    assert "schedule_profile_assignment_refresh" in assign_block
    assert "schedule_profile_assignment_refresh" in reassign_block


def test_assignment_refresh_is_data_routing_not_profile_structure_mutation():
    start = RUNTIME.index("def schedule_profile_assignment_refresh")
    end = RUNTIME.index("def sensor_assigned_profile_ids", start)
    block = RUNTIME[start:end]
    assert "_reconcile_profile_transports" in block
    assert "manager._notify_live()" in block
    assert "async_reload" not in block
    assert "async_update_entry" not in block
    assert "ensure_sensor_device" not in block
