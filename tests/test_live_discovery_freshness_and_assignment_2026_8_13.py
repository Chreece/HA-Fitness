from pathlib import Path

R = Path("custom_components/fitness/live/runtime.py").read_text()
C = Path("custom_components/fitness/config_flow.py").read_text()
H = Path("custom_components/fitness/live/ha_entities.py").read_text()
B = Path("custom_components/fitness/binary_sensor.py").read_text()
I = Path("custom_components/fitness/__init__.py").read_text()


def test_discovery_requires_one_fresh_observation_then_stays_sticky():
    assert "DISCOVERY_RECENT_SECONDS = 30.0" in R
    assert "def sensor_recently_observed(" in R
    poll = R[R.index("async def _poll()") : R.index("@callback\n        def _start_poll", R.index("async def _poll()"))]
    assert "self._prune_stale_sensor_discovery_flows()" not in poll
    assert 'sensor.metadata.get("discovery_confirmed")' in poll
    prune = R[R.index("def _prune_stale_sensor_discovery_flows") : R.index("def sensor_recently_observed")]
    assert "async_abort" not in prune
    assert "discovery cards are intentionally sticky" in prune
    discover = R[R.index("def _schedule_sensor_discovery") : R.index("def sensor_is_accepted")]
    assert 'confirmed = bool(sensor.metadata.get("discovery_confirmed"))' in discover
    assert 'sensor.metadata["discovery_confirmed"] = True' in discover
    assert "if not fresh and not confirmed" in discover


def test_acceptance_does_not_reload_or_create_devices_inline():
    marked = R[R.index("def mark_sensor_accepted") : R.index("def remove_unaccepted_sensor_device")]
    assert "self.ensure_sensor_device(sensor_id)" not in marked
    assert "self.request_hub_reload()" not in marked
    assert "self._notify_structure()" not in marked


def test_assignment_finalization_is_deferred_and_refreshes_routing_without_reload():
    block = C[C.index("async def async_step_assign_live_sensor"):C.index("async def async_step_user")]
    section = block[block.index("pending_updates: list"):block.rindex('return self.async_abort(reason="live_sensor_assigned")')]
    assert "async def _finalize_assignment()" in section
    assert "eager_start=False" in section
    assert "await asyncio.sleep(0.5)" in section
    assert "runtime.suppress_entry_reload_once(entry_id)" in section
    assert "self.hass.config_entries.async_update_entry(entry, options=options)" in section
    assert "runtime.finalize_sensor_acceptance(canonical_id)" in section
    assert "runtime.schedule_profile_assignment_refresh(changed_entries)" in section
    assert "async_reload(" not in section

def test_fitness_device_entities_materialize_dynamically_without_protocol_reload():
    assert "runtime.add_structure_listener(_collect)" in H
    assert "runtime.devices_entry" in H
    assert "runtime.ensure_sensors_subentry()" not in H
    assert "runtime.add_structure_listener(_add_live_sensor_availability)" in B
