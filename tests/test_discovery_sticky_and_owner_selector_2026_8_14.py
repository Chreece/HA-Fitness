from pathlib import Path

R = Path("custom_components/fitness/live/runtime.py").read_text()
S = Path("custom_components/fitness/select.py").read_text()
C = Path("custom_components/fitness/config_flow.py").read_text()


def test_discovery_silence_changes_availability_not_config_flow():
    expire = R[R.index("def _expire_stale_sensor_endpoints") : R.index("def _prune_stale_sensor_discovery_flows")]
    assert "endpoint.available = False" in expire
    prune = R[R.index("def _prune_stale_sensor_discovery_flows") : R.index("def sensor_recently_observed")]
    assert "async_abort" not in prune


def test_confirmed_discovery_is_persisted_once():
    discover = R[R.index("def _schedule_sensor_discovery") : R.index("def sensor_is_accepted")]
    assert 'if fresh and not confirmed:' in discover
    assert 'sensor.metadata["discovery_confirmed"] = True' in discover
    assert "self._schedule_save()" in discover


def test_owner_select_created_only_for_configured_shared_sensor():
    setup = S[S.index("async def async_setup_entry") : S.index("class FitnessSensorWorkoutOwnerSelect")]
    assert "len(runtime.sensor_assigned_profile_ids(sensor_id)) <= 1" in setup
    assert "runtime.add_structure_listener(_collect_owner_selects)" in setup
    reassign = C[C.index("async def async_step_sensor_assignment") : C.index("async def async_step_profile")]
    assert "runtime._notify_structure_throttled()" in reassign


def test_owner_select_available_only_during_two_profile_live_overlap():
    helper = R[R.index("def sensor_owner_transfer_available") : R.index("def profile_has_assigned_live_sensor")]
    assert "len(self.sensor_assigned_profile_ids(sensor_id)) > 1" in helper
    assert "len(self.sensor_live_assigned_profile_ids(sensor_id)) >= 2" in helper
    cls = S[S.index("class FitnessSensorWorkoutOwnerSelect") : S.index("class FitnessWorkoutRoomSelect")]
    assert "return self.runtime.sensor_owner_transfer_available(self.sensor_id)" in cls
    assert "live_only=True" in cls


def test_session_start_stop_refreshes_owner_selector_low_frequency():
    prepare = R[R.index("async def async_prepare_session") : R.index("async def async_finish_session")]
    finish = R[R.index("async def async_finish_session") : R.index("async def async_finish_recovery")]
    token='(sensor.sensor_id, "workout_owner", None)'
    assert token in prepare
    assert token in finish
