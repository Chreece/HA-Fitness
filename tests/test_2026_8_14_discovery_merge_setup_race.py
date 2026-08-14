"""Discovery/setup must survive ANT/BLE canonical identity merges."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / 'custom_components/fitness/live/runtime.py').read_text(encoding='utf-8')
FLOW = (ROOT / 'custom_components/fitness/config_flow.py').read_text(encoding='utf-8')
ANT = (ROOT / 'custom_components/fitness/live/antplus.py').read_text(encoding='utf-8')


def test_config_flow_resolves_provisional_sensor_id_to_canonical_id():
    discovery = FLOW.split('async def async_step_integration_discovery', 1)[1].split(
        'async def async_step_assign_live_sensor', 1
    )[0]
    assignment = FLOW.split('async def async_step_assign_live_sensor', 1)[1].split(
        'async def async_step_user', 1
    )[0]
    assert 'sensor_id = runtime.resolve_sensor_id(sensor_id)' in discovery
    assert 'sensor_id = runtime.resolve_sensor_id(sensor_id) if sensor_id else None' in assignment


def test_existing_profile_assignments_are_canonicalized_during_add():
    assignment = FLOW.split('async def async_step_assign_live_sensor', 1)[1].split(
        'async def async_step_user', 1
    )[0]
    assert 'canonical_id = runtime.resolve_sensor_id(configured_id)' in assignment
    assert 'if canonical_id not in ids:' in assignment


def test_discovery_dedupes_flows_across_sensor_alias_merge():
    block = RUNTIME.split('def _discovery_flow_matches_sensor', 1)[1].split(
        'def sensor_is_accepted', 1
    )[0]
    assert 'self.resolve_sensor_id(provisional) == canonical' in block
    assert 'if self._discovery_flow_active(sensor_id):' in block


def test_merge_preserves_inflight_discovery_instead_of_cancelling_it():
    merge = RUNTIME.split('def _merge_physical_sensors', 1)[1].split(
        'def _schedule_merged_registry_cleanup', 1
    )[0]
    assert 'self._discovery_tasks.setdefault(primary.sensor_id, secondary_task)' in merge
    assert 'secondary_task.cancel()' not in merge
    assert 'self._discovery_started.add(primary.sensor_id)' in merge


def test_add_response_precedes_registry_work_and_never_reloads_profile():
    assignment = FLOW.split('async def async_step_assign_live_sensor', 1)[1].split(
        'async def async_step_user', 1
    )[0]
    assert 'await asyncio.sleep(0.5)' in assignment
    assert 'runtime.suppress_entry_reload_once(entry_id)' in assignment
    assert 'runtime.schedule_profile_assignment_refresh(changed_entries)' in assignment
    assert 'async_reload(' not in assignment


def test_ant_structural_radio_path_does_not_unconditionally_touch_device_registry():
    publish = ANT.split('def _publish_device', 1)[1].split('def _has_available_receiver', 1)[0]
    assert 'ensure_sensor_device' not in publish
