from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text()


def test_discovery_is_assignment_driven_not_is_new_gated():
    assert "if is_new and self.profile_entries:" not in RUNTIME
    assert "if self.profile_entries and not self.sensor_is_accepted(sensor.sensor_id):" in RUNTIME
    assert "for sensor in tuple(self.sensors.values()):" in RUNTIME
    assert "sensor.available" in RUNTIME
    assert "self._schedule_sensor_discovery(sensor.sensor_id)" in RUNTIME


def test_discovery_guard_tracks_real_ha_flow_progress():
    assert "self._discovery_tasks: dict[str, asyncio.Task]" in RUNTIME
    assert "self.hass.config_entries.flow.async_progress()" in RUNTIME
    assert 'unique_id = f"live_sensor:{sensor_id}"' in RUNTIME
    assert '"fitness discover live sensor {sensor_id}"' in RUNTIME


def test_ant_metric_path_does_not_reenter_structural_registration_each_packet():
    assert "_device_sensor_ids" in ANT
    assert "_device_accepted" in ANT
    assert "if sensor_id is not None and not self._device_accepted.get(device_id, False):" in ANT
    assert "self._publish_metric_values(device, sensor_id)" in ANT
    assert "self.hass.loop.call_later(0.25, self._finish_publish_window, device_id)" in ANT


def test_unaccepted_merge_skips_registry_reload_and_tombstone_wins():
    assert "requires_reassignment = (" in RUNTIME
    assert 'primary.metadata.pop("accepted", None)' in RUNTIME
    assert "if had_accepted_device and not requires_reassignment:" in RUNTIME
    assert "self._schedule_merged_registry_cleanup(secondary.sensor_id)" in RUNTIME


def test_assignment_does_not_double_reload_profiles():
    block = FLOW[FLOW.index("async def async_step_assign_live_sensor"):FLOW.index("async def async_step_user")]
    assert "async_update_entry(entry, options=options)" in block
    assert "async_reload(entry_id)" not in block
