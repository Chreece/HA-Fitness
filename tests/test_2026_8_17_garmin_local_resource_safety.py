"""Static contracts preventing Garmin local sync from becoming an HA stall source."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
GARMIN = FIT / "device_adapters" / "garmin"
COORD = (GARMIN / "coordinator.py").read_text(encoding="utf-8")
GFDI = (GARMIN / "gfdi.py").read_text(encoding="utf-8")
PROTO = (GARMIN / "protocol.py").read_text(encoding="utf-8")
FIT_PARSER = (GARMIN / "fit.py").read_text(encoding="utf-8")
BT = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")
ARCHIVES = (FIT / "device_archives.py").read_text(encoding="utf-8")
BUTTON = (FIT / "button.py").read_text(encoding="utf-8")
FLOW = (FIT / "config_flow.py").read_text(encoding="utf-8")


def _method(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(name)


def test_garmin_sync_has_hard_session_stage_cleanup_and_shutdown_bounds():
    assert "SESSION_TIMEOUT = 100.0" in COORD
    assert "CONNECT_TIMEOUT = 35.0" in COORD
    assert "CLEANUP_TIMEOUT = 6.0" in COORD
    assert "SHUTDOWN_TIMEOUT = 12.0" in COORD
    sync = _method(COORD, "_async_sync")
    assert "async with asyncio.timeout(SESSION_TIMEOUT)" in sync
    assert "async with asyncio.timeout(CONNECT_TIMEOUT)" in sync
    assert "async with asyncio.timeout(CLEANUP_TIMEOUT)" in sync
    shutdown = _method(COORD, "async_shutdown")
    assert "asyncio.timeout(SHUTDOWN_TIMEOUT)" in shutdown
    assert "task.cancel()" in shutdown


def test_every_protocol_loop_is_backstopped_and_input_is_bounded():
    assert "GFDI_QUEUE_LIMIT = 128" in GFDI
    assert "MANAGEMENT_QUEUE_LIMIT = 32" in GFDI
    assert "MAX_COMPRESSED_FILE_BYTES = 16 * 1024 * 1024" in GFDI
    assert "MAX_FILES_PER_LISTING = 1_000" in GFDI
    assert "MAX_GFDI_FRAME_BYTES = 256 * 1024" in PROTO
    assert "MAX_COBS_BUFFER_BYTES = 512 * 1024" in PROTO
    assert "MAX_PROTOBUF_BYTES = 4 * 1024 * 1024" in PROTO
    assert "MAX_PROTOBUF_FIELDS = 20_000" in PROTO
    assert "MAX_FILE_LIST_ITEMS = 2_000" in PROTO
    assert "MAX_FIT_BYTES = 32 * 1024 * 1024" in FIT_PARSER
    assert "MAX_FIT_RECORDS = 150_000" in FIT_PARSER
    for token in (
        "HANDSHAKE_TIMEOUT",
        "PROTOBUF_EXCHANGE_TIMEOUT",
        "FILE_TRANSFER_TIMEOUT",
        "MAX_FILE_LIST_PAGES",
        "MAX_CURSOR_PAGES",
    ):
        assert token in GFDI


def test_download_batch_is_small_and_heavy_fit_work_is_off_event_loop():
    assert "MAX_FILES_PER_SYNC = 2" in COORD
    assert "MAX_BYTES_PER_SYNC = 16 * 1024 * 1024" in COORD
    assert "MAX_CACHED_FILE_RECORDS = 2_000" in COORD
    sync = _method(COORD, "_async_sync")
    assert 'batch_bytes + expected_size > MAX_BYTES_PER_SYNC' in sync
    assert "await self.hass.async_add_executor_job(" in sync
    assert "_decode_downloaded_file" in sync
    assert "# Checkpoint each complete FIT before touching profile history." in sync
    checkpoint = sync.index("# Checkpoint each complete FIT before touching profile history.")
    importer = sync.index("await self._import_records(")
    assert sync.index("await self._save()", checkpoint) < importer


def test_advertisements_are_rate_limited_and_cannot_defeat_retry_backoff():
    advertise = _method(COORD, "advertise")
    schedule = _method(COORD, "schedule")
    assert "ADVERTISEMENT_ACTION_MIN_INTERVAL = 30.0" in COORD
    assert "_last_advertisement_action" in advertise
    assert "ADVERTISEMENT_ACTION_MIN_INTERVAL" in advertise
    assert 'state.get("next_attempt")' in schedule
    assert "next_attempt > datetime.now(timezone.utc)" in schedule
    failure = _method(COORD, "_async_sync")
    assert 'next_attempt=retry_at.isoformat()' in failure
    assert "UNSUPPORTED_RETRY_DELAY = 6 * 60 * 60.0" in COORD


def test_garmin_does_not_compete_with_live_ble_and_uses_same_device_lock():
    sync = _method(COORD, "_async_sync")
    assert "self.provider.sensor_users(sensor_id)" in sync
    assert "self.provider.sensor_connected(sensor_id)" in sync
    assert "lock = self.provider._connect_lock(sensor_id)" in sync
    assert "async with lock:" in sync
    assert "_async_disconnect_client" in sync


def test_transport_selection_is_capability_based_without_test_watch_special_cases():
    transport = _method(GFDI, "transport_from_client")
    assert "GarminV2Transport.from_client" in transport
    assert "GarminV1Transport.from_client" in transport
    combined = (COORD + GFDI + PROTO).lower()
    assert "forerunner 965" not in combined
    assert "fr965" not in combined
    assert "e0:48:24:67:85:64" not in combined
    assert "if model" not in transport.lower()
    # Informational advertised names are allowed; they never select a backend.
    assert '"model": str(name or "Garmin wearable")' in COORD


def test_unverified_mlr_fails_fast_instead_of_entering_a_transfer_loop():
    register = _method(GFDI, "async_register_service")
    assert "if reliable != 0:" in register
    assert "GarminUnsupportedTransport" in register
    assert "MLR reliable mode is not implemented" in register
    assert "UNSUPPORTED_RETRY_DELAY" in COORD


def test_local_archive_is_read_only_by_construction():
    combined = (PROTO + GFDI + COORD).lower()
    # No builder or caller exists for Garmin's mutating file flags/sync marker.
    for forbidden in (
        "mark_synced",
        "marksynced",
        "file_set_flags",
        "set_file_flag",
        "gfdi_set_file_flag",
        "delete_file",
        "archive_file",
    ):
        assert forbidden not in combined
    assert "synced-file exclusion flags are intentionally omitted" in PROTO.lower()


def test_manual_sync_button_only_schedules_background_work():
    press = _method(BUTTON, "async_press")
    # There are several async_press methods; source lookup can return another one,
    # so assert the Garmin class block explicitly as well.
    block = BUTTON.split("class GarminSyncWorkoutsButton", 1)[1].split("class BaseLiveFitnessButton", 1)[0]
    assert "coordinator.schedule" in block
    assert "await coordinator" not in block


def test_integration_contains_user_visible_garmin_setup_guide_and_docs():
    assert "async_step_garmin_local_guide" in FLOW
    assert 'menu.extend(["workout_devices", "sleep_devices", "ai", "feedback", "tv_dashboard"])' in FLOW
    assert 'menu.insert(menu.index("workout_devices") + 1, "garmin_local_guide")' in FLOW
    assert (ROOT / "docs" / "GARMIN_LOCAL.md").is_file()
    guide = (ROOT / "docs" / "GARMIN_LOCAL.md").read_text(encoding="utf-8")
    assert "phone does **not** connect to HA-Fitness" in guide
    assert "does **not** keep Garmin GATT open while idle" in guide
    assert "mark Garmin files as synchronized" in guide


def test_live_bluetooth_stays_vendor_neutral_via_archive_registry():
    assert "DeviceArchiveRegistry" in BT
    assert "device_archives.match_bluetooth" in BT
    assert "garmin" not in BT.lower()
    assert "GarminLocalCoordinator" in ARCHIVES


def test_cached_archive_state_is_bounded_without_pruning_current_device_catalogue():
    prune = _method(COORD, "_prune_file_records")
    assert "MAX_CACHED_FILE_RECORDS" in prune
    assert "key not in protected_keys" in prune
    sync = _method(COORD, "_async_sync")
    assert "self._prune_file_records(files, set(keys))" in sync


def test_manual_retry_can_replace_sleeping_backoff_but_not_cancel_active_ble():
    schedule = _method(COORD, "schedule")
    assert "self._active_sync" in schedule
    assert "current.cancel()" in schedule
    assert "if sensor_id not in self._active_sync" in schedule
    assert "self._queued[sensor_id]" in schedule
    assert "UNSUPPORTED_RETRY_DELAY" in COORD
    # Pairing requires user action, so background retry is intentionally sparse.
    assert 'if error_code == "pairing_required"' in COORD
