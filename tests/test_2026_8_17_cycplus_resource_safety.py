"""Regression contracts for bounded CYCPLUS import and shutdown behavior."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
CYCPLUS = (FIT / "live" / "cycplus_m1.py").read_text(encoding="utf-8")
BLUETOOTH = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")
MANAGER = (FIT / "manager.py").read_text(encoding="utf-8")
WORKOUTS = (FIT / "providers" / "workouts.py").read_text(encoding="utf-8")


def test_initial_archive_backlog_is_split_into_small_resumable_batches():
    sync = CYCPLUS.split("    async def _async_sync", 1)[1].split(
        "    async def async_shutdown", 1
    )[0]
    assert "MAX_FILES_PER_SYNC = 3" in CYCPLUS
    assert "MAX_BYTES_PER_SYNC = 24 * 1024 * 1024" in CYCPLUS
    assert "queue[:download_slots]" in sync
    assert "batch_bytes >= MAX_BYTES_PER_SYNC" in sync
    assert "_schedule_after_current(" in sync
    assert "BATCH_CONTINUE_DELAY" in sync


def test_batch_import_rewrites_each_profile_history_at_most_once():
    importer = CYCPLUS.split(
        "    async def _import_records_to_profiles", 1
    )[1].split("    def _apply_fit_device_attributes", 1)[0]
    assert importer.count("await manager.async_import_device_workouts") == 1
    sync = CYCPLUS.split("    async def _async_sync", 1)[1].split(
        "    async def async_shutdown", 1
    )[0]
    assert sync.count("await self._import_records_to_profiles(") == 1
    assert '"workouts": [' in sync
    assert "workout.as_persistent_dict()" in sync


def test_fit_decode_and_transfer_have_hard_memory_limits():
    assert "MAX_TRANSFER_BYTES = 16 * 1024 * 1024" in CYCPLUS
    assert "MAX_FIT_RECORDS = 100_000" in CYCPLUS
    assert "MAX_FIT_METADATA_FRAMES = 2_048" in CYCPLUS
    decoder = CYCPLUS.split("def decode_fit_messages", 1)[1].split(
        "def _value", 1
    )[0]
    assert "frame_name not in _FIT_RETAINED_FRAMES" in decoder
    assert 'frame_name == "record" and name not in _FIT_RECORD_FIELDS' in decoder
    assert "FIT file exceeds the safe record limit" in decoder


def test_unassignment_and_shutdown_cannot_leave_an_unbounded_ble_job():
    assignment = CYCPLUS.split("    def assignment_changed", 1)[1].split(
        "    def forget_sensor", 1
    )[0]
    assert "sensor_assigned_profile_ids" in assignment
    assert "task.cancel()" in assignment
    assert 'sync_state="idle"' in assignment
    assert "asyncio.timeout(SHUTDOWN_TIMEOUT)" in CYCPLUS
    assert "asyncio.timeout(BLE_CLEANUP_TIMEOUT)" in CYCPLUS
    assert "asyncio.timeout(BLE_DISCONNECT_TIMEOUT)" in BLUETOOTH


def test_legacy_gigabyte_history_is_compacted_once_before_device_imports():
    setup = MANAGER.split("    async def async_setup", 1)[1].split(
        "    async def _async_post_start_setup", 1
    )[0]
    assert 'stored.pop("history", None)' in setup
    assert "await self.hass.async_add_executor_job(" in setup
    assert "_compact_history_for_storage" in setup
    assert "await self._save()" in setup
    assert '"history_compaction_version": HISTORY_COMPACTION_VERSION' in MANAGER
    assert "PERSISTENCE_MAX_NODES = 4096" in WORKOUTS
    assert "PERSISTENCE_MAX_LIST_ITEMS = 256" in WORKOUTS

