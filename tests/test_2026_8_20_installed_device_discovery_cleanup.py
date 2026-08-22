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

def test_discovery_task_revalidates_identity_before_and_after_flow_creation():
    schedule = RUNTIME.split(
        "    def _schedule_sensor_discovery", 1
    )[1].split("    def sensor_is_accepted", 1)[0]
    assert "canonical_id = self.resolve_sensor_id(sensor_id)" in schedule
    assert schedule.count("canonical_id = self.resolve_sensor_id(sensor_id)") >= 2
    assert "result = await self.hass.config_entries.flow.async_init(" in schedule
    assert 'flow_id = str((result or {}).get("flow_id") or "")' in schedule
    assert "self.hass.config_entries.flow.async_abort(flow_id)" in schedule
    assert "canonical_id != sensor_id" in schedule
    assert "self.sensor_is_accepted(canonical_id)" in schedule


def test_merged_physical_registry_cleanup_uses_devices_entry_not_protocol_hub():
    block = RUNTIME.split(
        "    def _cleanup_merged_registry_sensor", 1
    )[1].split("    @staticmethod", 1)[0]
    assert "if self.devices_entry is None:" in block
    assert "devices_entry_id = self.devices_entry.entry_id" in block
    assert "entity.config_entry_id == devices_entry_id" in block
    assert "self.hub_entry.entry_id" not in block



def test_profile_registration_aborts_discovery_already_owned_by_that_profile():
    block = RUNTIME.split("    async def async_register_profile", 1)[1].split(
        "    def _restore_legacy_profile_selections", 1
    )[0]
    assert "accepted = self.sensor_is_accepted(sensor.sensor_id)" in block
    assert "if accepted:" in block
    assert "self._abort_discovery_flows_after_accepted_merge(" in block
    assert "sensor.sensor_id, {sensor.sensor_id}" in block
    assert block.index("if accepted:") < block.index("elif sensor.capabilities:")
