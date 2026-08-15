"""Merged live sensors preserve materialized HA entities and restart topology."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text(encoding="utf-8")


def test_merge_primary_prefers_existing_materialized_ha_device_before_ant():
    block = RUNTIME.split("def _select_merge_primary", 1)[1].split(
        "def _migrate_workout_state_for_sensor_merge", 1
    )[0]
    assert "a_materialized = a.sensor_id in self._sensor_device_ids" in block
    assert "b_materialized = b.sensor_id in self._sensor_device_ids" in block
    assert "if a_materialized != b_materialized:" in block
    assert block.index("if a_materialized != b_materialized:") < block.index(
        'if ("antplus" in a.endpoints) != ("antplus" in b.endpoints):'
    )


def test_registry_cleanup_only_removes_entities_attached_to_discarded_device():
    block = RUNTIME.split("def _cleanup_merged_registry_sensor", 1)[1].split(
        "@staticmethod", 1
    )[0]
    assert "entity.device_id == device.id" in block
    assert "old_sensor_id in str(entity.unique_id" not in block


def test_accepted_but_not_materialized_second_add_does_not_trigger_device_cleanup():
    merge = RUNTIME.split("def _merge_physical_sensors", 1)[1].split(
        "def _schedule_merged_registry_cleanup", 1
    )[0]
    assert (
        "secondary_had_accepted_device = secondary.sensor_id in self._sensor_device_ids"
        in merge
    )
    assert "secondary_had_accepted_device = self.sensor_is_accepted" not in merge


def test_merge_drops_only_secondary_device_bookkeeping():
    merge = RUNTIME.split("def _merge_physical_sensors", 1)[1].split(
        "def _schedule_merged_registry_cleanup", 1
    )[0]
    assert "self._sensor_device_ids.pop(secondary.sensor_id, None)" in merge
    assert "self._sensor_device_ids.pop(primary.sensor_id" not in merge


def test_pending_topology_is_flushed_during_shutdown_instead_of_discarded():
    block = RUNTIME.split("async def async_shutdown", 1)[1].split(
        "def get_live_runtime", 1
    )[0]
    assert "pending_topology_save = bool(self._save_pending)" in block
    assert "await self._async_save_adapter_config()" in block
    assert block.index("await self._async_save_adapter_config()") < block.index(
        "await provider.async_shutdown()"
    )
