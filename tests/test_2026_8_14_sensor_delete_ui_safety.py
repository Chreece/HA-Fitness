"""Deleting a native sensor must stay off expensive HA control paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_delete_request_never_waits_for_store_write():
    block = RUNTIME.split("async def async_forget_sensor",1)[1].split("def _listen_for_registry_deletions",1)[0]
    assert "await self._async_save_adapter_config()" not in block
    assert "self._schedule_save()" in block


def test_memory_forget_does_not_notify_structure_synchronously():
    block = RUNTIME.split("def _forget_sensor_memory",1)[1].split("def _schedule_deleted_sensor_cleanup",1)[0]
    assert "self._notify_structure()" not in block


def test_cleanup_waits_until_delete_transaction_has_closed_without_reload_or_structure_burst():
    block = RUNTIME.split("def _schedule_deleted_sensor_cleanup",1)[1].split("def forget_sensor",1)[0]
    assert "await asyncio.sleep(0.75)" in block
    assert "suppress_entry_reload_once" in block
    assert "async_reload" not in block
    assert "async_remove_subentry" not in block
    assert "_notify_structure_throttled()" not in block


def test_deleted_endpoint_is_temporarily_quarantined_from_rediscovery():
    forget = RUNTIME.split("def _forget_sensor_memory",1)[1].split("def _schedule_deleted_sensor_cleanup",1)[0]
    assert "time.monotonic() + 5.0" in forget
    schedule = RUNTIME.split("def _schedule_sensor_discovery",1)[1].split("def sensor_is_accepted",1)[0]
    assert "_rediscovery_quarantine_until" in schedule
