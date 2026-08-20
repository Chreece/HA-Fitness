"""Regression contracts for stale discovery flows after accepted route merges."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")


def test_accepted_physical_merge_aborts_stale_discovery_flow():
    merge = RUNTIME.split("    def _merge_physical_sensors", 1)[1].split(
        "    def _abort_discovery_flows_after_accepted_merge", 1
    )[0]
    assert "elif self.sensor_is_accepted(primary.sensor_id):" in merge
    assert "self._abort_discovery_flows_after_accepted_merge(" in merge


def test_accepted_merge_cleanup_cancels_pending_and_open_flows_without_reopening():
    helper = RUNTIME.split(
        "    def _abort_discovery_flows_after_accepted_merge", 1
    )[1].split("    def _collapse_provisional_discovery_flows_after_merge", 1)[0]
    assert "self._discovery_tasks.pop(sensor_id, None)" in helper
    assert "task.cancel()" in helper
    assert "self._discovery_started.discard(sensor_id)" in helper
    assert "include_uninitialized=True" in helper
    assert "manager.async_abort(flow_id)" in helper
    assert "self.resolve_sensor_id(provisional) != canonical_id" in helper
    assert "_schedule_sensor_discovery" not in helper
    assert "call_soon" not in helper


def test_stale_add_flow_still_resolves_to_installed_sensor_as_final_guard():
    block = FLOW.split("    async def async_step_assign_live_sensor", 1)[1].split(
        "    async def async_step_user", 1
    )[0]
    assert "sensor_id = runtime.resolve_sensor_id(sensor_id)" in block
    assert "if runtime.sensor_is_accepted(sensor_id):" in block
    assert 'return self.async_abort(reason="live_sensor_assigned")' in block
