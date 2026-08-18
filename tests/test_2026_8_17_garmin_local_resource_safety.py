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
    assert "IMPORT_TIMEOUT = 20.0" in COORD
    assert "TRANSPORT_NEGOTIATION_TIMEOUT = 40.0" in COORD
    assert "TRANSPORT_CANDIDATE_TIMEOUT = 12.0" in COORD
    assert "SHUTDOWN_TIMEOUT = 12.0" in COORD
    sync = _method(COORD, "_async_sync")
    assert "async with asyncio.timeout(SESSION_TIMEOUT)" in sync
    assert "async with asyncio.timeout(CONNECT_TIMEOUT)" in sync
    assert "async with asyncio.timeout(CLEANUP_TIMEOUT)" in sync
    assert "async with asyncio.timeout(IMPORT_TIMEOUT)" in sync
    shutdown = _method(COORD, "async_shutdown")
    assert "asyncio.timeout(SHUTDOWN_TIMEOUT)" in shutdown
    assert "task.cancel()" in shutdown


def test_every_protocol_loop_is_backstopped_and_input_is_bounded():
    assert "GFDI_QUEUE_LIMIT = 128" in GFDI
    assert "MANAGEMENT_QUEUE_LIMIT = 32" in GFDI
    assert "MAX_COMPRESSED_FILE_BYTES = 16 * 1024 * 1024" in GFDI
    assert "MAX_FILES_PER_LISTING = 1_000" in GFDI
    assert "MAX_GFDI_FRAME_BYTES = 0xFFFF" in PROTO
    assert "MAX_COBS_BUFFER_BYTES = 96 * 1024" in PROTO
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
    assert "DEGRADED_RETRY_DELAY = 2 * 60 * 60.0" in COORD
    assert "BUSY_RETRY_DELAY = 5 * 60.0" in COORD
    assert "UNREACHABLE_RETRY_DELAY = 30 * 60.0" in COORD


def test_garmin_does_not_compete_with_live_ble_and_uses_same_device_lock():
    sync = _method(COORD, "_async_sync")
    assert "self.provider.sensor_users(sensor_id)" in sync
    assert "self.provider.sensor_connected(sensor_id)" in sync
    assert "lock = self.provider._connect_lock(sensor_id)" in sync
    assert "async with lock:" in sync
    assert "_async_disconnect_client" in sync


def test_transport_selection_is_capability_based_without_test_watch_special_cases():
    transport = _method(GFDI, "transport_from_client")
    candidates = _method(GFDI, "transport_candidates_from_client")
    negotiation = _method(COORD, "_start_best_session")
    assert "GarminV2Transport.candidates_from_client" in candidates
    assert "GarminV1Transport.candidates_from_client" in candidates
    assert "transport_candidates_from_client" in transport
    assert "transport_candidates_from_client" in negotiation
    assert "TRANSPORT_CANDIDATE_TIMEOUT" in negotiation
    assert "await session.async_stop()" in negotiation
    combined = (COORD + GFDI + PROTO).lower()
    for forbidden in (
        "forerunner 965", "fr965", "e0:48:24:67:85:64",
        "if model", "fenix", "fēnix", "instinct", "vivoactive", "venu",
    ):
        assert forbidden not in combined
    # Local names are display metadata only and are not labeled as a model.
    assert 'result["bluetooth_name"]' in PROTO
    assert 'result["model"]' not in PROTO


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


def test_integration_contains_user_visible_smart_workout_device_guide_and_docs():
    assert "async_step_smart_workout_devices" in FLOW
    assert "async_step_garmin_local_guide" in FLOW  # backward-compatible alias only
    assert 'menu.extend(["workout_devices", "sleep_devices", "ai", "feedback", "tv_dashboard"])' in FLOW
    assert 'menu.insert(menu.index("workout_devices") + 1, "smart_workout_devices")' in FLOW
    assert (ROOT / "docs" / "SMART_WORKOUT_DEVICES.md").is_file()
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
    assert "self._active_sync" in schedule
    assert "wake_if_sleeping" in schedule
    assert "self._queued[sensor_id]" in schedule
    assert "UNSUPPORTED_RETRY_DELAY" in COORD
    # Pairing requires user action, so background retry is intentionally sparse.
    assert 'if error_code == "pairing_required"' in COORD


def test_garmin_discovery_replays_cache_once_and_guide_scan_is_bounded():
    setup = _method(BT, "async_setup")
    assert "BluetoothCallbackReplay.DISABLED" in setup
    assert "self._replay_cached_discovery()" in setup
    replay = _method(BT, "_replay_cached_discovery")
    assert "DISCOVERY_CACHE_REPLAY_LIMIT" in replay
    assert "DISCOVERY_CACHE_SCAN_LIMIT" in replay
    assert "_cached_discovery_relevant" in replay
    refresh = _method(BT, "async_refresh_discovery")
    assert "async_request_active_scan" in refresh
    assert "DISCOVERY_ACTIVE_SCAN_TIMEOUT" in refresh
    assert "DISCOVERY_REFRESH_MIN_INTERVAL" in refresh
    assert "_discovery_refresh_lock" in refresh
    assert "self._replay_cached_discovery()" in refresh
    refresh_guide = _method(FLOW, "_async_refresh_smart_workout_discovery")
    assert "async_refresh_discovery" in refresh_guide
    assert "asyncio.timeout(15.0)" in refresh_guide
    guide = _method(FLOW, "async_step_smart_workout_devices")
    assert "_async_refresh_smart_workout_discovery" in guide


def test_v2_channel_discovery_is_bounded_but_not_hardcoded_to_five_channels():
    candidates = _method(GFDI, "candidates_from_client")
    # AST helper returns the first candidates_from_client method (legacy), so use
    # source-level invariants for the V2 class block.
    v2 = GFDI.split("class GarminV2Transport", 1)[1].split("def transport_candidates_from_client", 1)[0]
    assert "MAX_V2_CHANNEL_CANDIDATES = 4" in GFDI
    assert 'short.startswith("6a4e281")' in v2
    assert 'short[-1] not in "0123456789abcdef"' in v2
    assert "range(5)" not in v2
    assert "pairs[:MAX_V2_CHANNEL_CANDIDATES]" in v2


def test_automatic_sync_is_timer_backed_and_does_not_poll_unreachable_devices_hot():
    advertise = _method(COORD, "advertise")
    schedule = _method(COORD, "schedule")
    sync = _method(COORD, "_async_sync")
    assert "wake_if_sleeping=True" in advertise
    assert "if not (force or wake_if_sleeping)" in schedule
    assert "UNREACHABLE_RETRY_DELAY" in sync
    assert "SYNC_INTERVAL.total_seconds()" in sync
    assert "BATCH_CONTINUE_DELAY" in sync
    # After a GATT session, ask HA to deliver the next identical wake advert;
    # this is a cache-history operation, not a scanner or connection loop.
    assert "async_clear_advertisement_history" in sync


def test_gfdi_frame_ceiling_matches_wire_length_field_and_cobs_headroom_is_small():
    assert "MAX_GFDI_FRAME_BYTES = 0xFFFF" in PROTO
    assert "MAX_COBS_BUFFER_BYTES = 96 * 1024" in PROTO
    assert 'struct.unpack_from("<H"' in PROTO
