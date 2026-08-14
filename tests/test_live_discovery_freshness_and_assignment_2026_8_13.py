from pathlib import Path

R = Path("custom_components/fitness/live/runtime.py").read_text()
C = Path("custom_components/fitness/config_flow.py").read_text()
H = Path("custom_components/fitness/live/ha_entities.py").read_text()
B = Path("custom_components/fitness/binary_sensor.py").read_text()
I = Path("custom_components/fitness/__init__.py").read_text()


def test_discovery_requires_recent_radio_observation_and_prunes_stale_flows():
    assert "DISCOVERY_RECENT_SECONDS = 30.0" in R
    assert "def sensor_recently_observed(" in R
    poll = R[R.index("async def _poll()") : R.index("@callback\n        def _start_poll", R.index("async def _poll()"))]
    assert "self._prune_stale_sensor_discovery_flows()" in poll
    assert "self.sensor_recently_observed(sensor.sensor_id)" in poll
    prune = R[R.index("def _prune_stale_sensor_discovery_flows") : R.index("def sensor_recently_observed")]
    assert "self.hass.config_entries.flow.async_abort(flow_id)" in prune
    discover = R[R.index("def _schedule_sensor_discovery") : R.index("def sensor_is_accepted")]
    assert "not self.sensor_recently_observed(sensor_id)" in discover


def test_acceptance_does_not_reload_or_create_devices_inline():
    marked = R[R.index("def mark_sensor_accepted") : R.index("def remove_unaccepted_sensor_device")]
    assert "self.ensure_sensor_device(sensor_id)" not in marked
    assert "self.request_hub_reload()" not in marked
    assert "self._notify_structure()" in marked


def test_assignment_finalization_is_deferred_and_suppresses_profile_reload():
    section = C[C.index("pending_updates: list") : C.index('return self.async_abort(reason="live_sensor_assigned")')]
    assert "async def _finalize_assignment()" in section
    assert "eager_start=False" in section
    assert "runtime.suppress_entry_reload_once(entry.entry_id)" in section
    assert "runtime.ensure_sensor_device(sensor_id)" in section
    assert "runtime.request_hub_reload()" not in section
    assert "runtime._notify_structure()" in section
    assert "consume_entry_reload_suppression" in I


def test_hub_sensor_entities_materialize_dynamically_without_hub_reload():
    assert "runtime.add_structure_listener(_collect)" in H
    assert "runtime.ensure_sensors_subentry()" in H
    assert "runtime.add_structure_listener(_add_live_sensor_availability)" in B
