"""CYCPLUS M1 discovery, FIT normalization and restart-safety contracts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import json
from pathlib import Path
import sys
import types

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

# Load the production module under an isolated package name. This keeps the
# custom integration's heavyweight __init__ module out of these pure unit tests.
components = sys.modules.setdefault(
    "homeassistant.components", types.ModuleType("homeassistant.components")
)
components.__path__ = []
sys.modules.setdefault(
    "homeassistant.components.bluetooth",
    types.ModuleType("homeassistant.components.bluetooth"),
)
storage = sys.modules.setdefault(
    "homeassistant.helpers.storage", types.ModuleType("homeassistant.helpers.storage")
)


class _Store:
    @classmethod
    def __class_getitem__(cls, _item):
        return cls


storage.Store = _Store

root_pkg = sys.modules.setdefault("cycplus_test", types.ModuleType("cycplus_test"))
root_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault(
    "cycplus_test.providers", types.ModuleType("cycplus_test.providers")
)
providers_pkg.__path__ = [str(FITNESS / "providers")]
adapters_pkg = sys.modules.setdefault(
    "cycplus_test.device_adapters", types.ModuleType("cycplus_test.device_adapters")
)
adapters_pkg.__path__ = [str(FITNESS / "device_adapters")]

load_module("cycplus_test.const", "const.py")
workouts = load_module("cycplus_test.providers.workouts", "providers/workouts.py")
cycplus = load_module(
    "cycplus_test.device_adapters.cycplus_m1", "device_adapters/cycplus_m1.py"
)

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"


def test_discovery_requires_both_m1_name_and_vendor_service():
    identity = cycplus.cycplus_m1_identity(
        "M1_98C6", [cycplus.CYCPLUS_M1_SERVICE_UUID.upper()]
    )
    assert identity == {
        "manufacturer": "CYCPLUS",
        "model": "CYCPLUS M1 GPS Bike Computer",
        "model_id": "M1",
        "cycplus_protocol": "m1_ble_fit_archive_v1",
        "cycplus_model_id": "M1",
        "cycplus_device_number": "98C6",
        "fitness_physical_identity": "cycplus:m1:98c6",
        "fitness_vendor_identity": "cycplus",
        "archive_adapter": "cycplus_m1",
        "smart_device_default_type": "bike_computer",
        "archive_compatible": True,
        "device_number": "98C6",
    }
    assert cycplus.cycplus_m1_name_identity("M1_98C6") == {
        "cycplus_model_id": "M1",
        "cycplus_device_number": "98C6",
        "fitness_physical_identity": "cycplus:m1:98c6",
    }
    assert cycplus.cycplus_m1_identity("M1_98C6", []) is None
    assert cycplus.cycplus_m1_identity(
        "unrelated UART", [cycplus.CYCPLUS_M1_SERVICE_UUID]
    ) is None


def test_protocol_requests_match_verified_m1_commands():
    assert cycplus.cycplus_request("filelist.txt") == bytes.fromhex(
        "0566696c656c6973742e74787457"
    )
    assert cycplus.cycplus_request("20260817123456.fit") == (
        b"\x05" + b"20260817123456.fit" + b"\x50"
    )


def test_protocol_transfer_handshake_returns_exact_bytes_without_queue_duplication():
    class FakeClient:
        def __init__(self):
            self.callbacks = {}
            self.writes = []
            self.copy_count = 0

        async def start_notify(self, uuid, callback):
            self.callbacks[uuid] = callback

        async def stop_notify(self, _uuid):
            return None

        async def write_gatt_char(self, uuid, payload, response=False):
            assert response is False
            payload = bytes(payload)
            self.writes.append((uuid, payload))
            command = self.callbacks[cycplus.CYCPLUS_M1_COMMAND_UUID]
            data = self.callbacks[cycplus.CYCPLUS_M1_TX_UUID]
            if uuid == cycplus.CYCPLUS_M1_COMMAND_UUID:
                if payload == b"\xff\x00\xff":
                    command(None, bytearray(b"\x06"))
                elif payload.startswith(b"\x05"):
                    filename = payload[1:-1]
                    command(None, bytearray(b"\x06" + filename + b"\x00"))
                return
            if payload == b"\x43":
                self.copy_count += 1
                if self.copy_count == 1:
                    command(None, bytearray(b"\x43"))
                else:
                    # Three-byte per-block prefix and two-byte trailer are not
                    # part of the returned file. A trailing NUL in the file is.
                    data(None, bytearray(b"HDRpayload\x00ZZ"))
                    data(None, bytearray(b"\x04"))
            elif payload in {b"\x06", b"\x15"}:
                command(None, bytearray(b"\x06"))

    async def exercise():
        client = FakeClient()
        protocol = cycplus.CycplusM1Protocol(client)
        await protocol.async_start()
        result = await protocol.async_read_file("20260817123456.fit")
        await protocol.async_stop()
        assert result == b"payload\x00"
        assert protocol._any_queue.empty()
        assert client.copy_count == 2

    asyncio.run(exercise())


def test_catalog_fallback_prefers_nonempty_firmware_catalog():
    protocol = object.__new__(cycplus.CycplusM1Protocol)

    async def read_file(filename):
        if filename == "filelist.txt":
            return b"\x00"
        return b'{"files":["20260817123456.fit"]}\x00'

    protocol.async_read_file = read_file
    name, _payload, files = asyncio.run(protocol.async_file_catalog())
    assert name == "workouts.json"
    assert files == ["20260817123456.fit"]


def test_catalog_parser_supports_text_and_json_without_case_damage():
    payload = json.dumps({
        "workouts": [
            {"file": "20260817123456.FIT"},
            "20260816010203.fit",
            "duplicate 20260817123456.FIT",
        ]
    }).encode() + b"\x00\x00"
    assert cycplus.extract_fit_filenames(payload) == [
        "20260816010203.fit",
        "20260817123456.FIT",
    ]
    assert cycplus.extract_fit_filenames(
        b"20260818000000.fit\r\n20260819000000.fit\r\n"
    ) == ["20260818000000.fit", "20260819000000.fit"]


def test_disk_space_and_fit_framing_are_bounded_and_padding_safe():
    assert cycplus.parse_disk_space(b"\n120 / 256 kb\x00") == (120, 256)
    assert cycplus.parse_disk_space(b"\n8192\x00") == (8192, None)
    assert cycplus.parse_disk_space(b"999 / 100 kb") == (None, None)

    # Empty but correctly framed container: 14-byte header plus file CRC.
    container = bytes([14, 0x10, 0, 0]) + (0).to_bytes(4, "little") + b".FIT" + b"\0\0\0\0"
    padded = container + b"\0\0\0"
    assert cycplus._valid_fit_container(padded)
    assert cycplus._fit_container(padded) == container
    assert not cycplus._valid_fit_container(container[:-1])


def test_fit_sessions_normalize_into_canonical_calendar_workouts():
    start = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=30)
    semicircle_lat = int(52.5 / 180.0 * (2**31))
    semicircle_lon = int(13.4 / 180.0 * (2**31))
    messages = [
        ("file_id", {
            "manufacturer": "cycplus",
            "product_name": "M1",
            "serial_number": 123456,
            "time_created": start,
        }),
        ("device_info", {
            "device_index": "creator",
            "manufacturer": "cycplus",
            "product_name": "M1",
            "serial_number": 123456,
            "hardware_version": 2,
            "software_version": 3.4,
            "battery_voltage": 3.91,
            "battery_status": "good",
        }),
        ("record", {
            "timestamp": start,
            "position_lat": semicircle_lat,
            "position_long": semicircle_lon,
            "heart_rate": 140,
            "power": 210,
            "cadence": 82,
            "enhanced_speed": 7.0,
        }),
        ("record", {
            "timestamp": end,
            "heart_rate": 160,
            "power": 290,
            "cadence": 94,
            "enhanced_speed": 11.0,
        }),
        ("lap", {"timestamp": end}),
        ("session", {
            "start_time": start,
            "timestamp": end,
            "sport": "cycling",
            "total_timer_time": 1800,
            "total_elapsed_time": 1810,
            "total_distance": 15000,
            "total_ascent": 120,
            "total_descent": 118,
            "total_calories": 510,
            "normalized_power": 245,
            "total_work": 420000,
            "num_laps": 1,
        }),
    ]

    result = cycplus.workouts_from_fit_messages(
        messages,
        filename="20260817120000.fit",
        sensor_id="physical_1",
        advertised_number="98C6",
        sha256="abc",
    )
    assert len(result.workouts) == 1
    workout = result.workouts[0]
    assert workout.start == start.isoformat()
    assert workout.end == end.isoformat()
    assert workout.duration_s == 1800
    assert workout.elapsed_time_s == 1810
    assert workout.distance_m == 15000
    assert workout.avg_hr == 150
    assert workout.max_hr == 160
    assert workout.avg_power == 250
    assert workout.max_power == 290
    assert workout.weighted_power == 245
    assert workout.avg_cadence == 88
    assert workout.max_cadence == 94
    assert workout.average_speed_m_s == 9
    assert workout.max_speed_m_s == 11
    assert workout.kilojoules == 420
    assert abs(workout.start_latitude - 52.5) < 0.000001
    assert abs(workout.start_longitude - 13.4) < 0.000001
    assert workout.sample_count is None
    assert workout.provider_domains == ["cycplus_m1"]
    assert workout.extra["source_filename"] == "20260817120000.fit"
    assert workout.extra["source_file_sha256"] == "abc"
    assert result.device_attributes == {
        "device_number": "98C6",
        "fit_manufacturer": "cycplus",
        "fit_product": "M1",
        "fit_serial_number": 123456,
        "fit_hardware_version": 2,
        "fit_software_version": 3.4,
        "fit_battery_voltage": 3.91,
        "fit_battery_status": "good",
    }


def test_all_bundled_languages_cover_every_new_entity_and_enum_state():
    expected_sensors = set(cycplus._DETAIL_META)
    expected_states = {"idle", "waiting", "connecting", "syncing", "ready", "retrying", "error"}
    expected_battery_states = {"new", "good", "ok", "low", "critical", "charging", "unknown"}
    expected_errors = {
        "none", "connection_failed", "catalog_failed", "transfer_interrupted",
        "invalid_fit", "import_failed", "unknown",
    }
    paths = [FIT / "strings.json", *sorted((FIT / "translations").glob("*.json"))]
    assert len(paths) == 16
    for path in paths:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        sensors = catalog["entity"]["sensor"]
        binary_sensors = catalog["entity"]["binary_sensor"]
        assert expected_sensors <= set(sensors), path.name
        assert {
            "physical_battery",
            "physical_active_transport",
            "physical_workout_owner",
            "physical_signal_strength",
            "physical_last_seen",
        } <= set(sensors), path.name
        assert {
            "physical_available",
            "physical_gatt_connected",
        } <= set(binary_sensors), path.name
        assert set(sensors["cycplus_sync_state"]["state"]) == expected_states
        assert set(sensors["cycplus_fit_battery_status"]["state"]) == expected_battery_states
        assert set(sensors["cycplus_last_error"]["state"]) == expected_errors
        assert "cycplus_sync_workouts" in catalog["entity"]["button"]
    assert (FIT / "strings.json").read_bytes() == (FIT / "translations/en.json").read_bytes()


def test_archive_lifecycle_has_auto_retry_checkpoint_and_profile_boundaries():
    source = (FIT / "device_adapters" / "cycplus_m1.py").read_text(encoding="utf-8")
    bluetooth = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")
    manager = (FIT / "manager.py").read_text(encoding="utf-8")
    manifest = json.loads((FIT / "manifest.json").read_text(encoding="utf-8"))

    assert "fitdecode==0.11.0" in manifest["requirements"]
    assert "check_crc=fitdecode.CrcCheck.RAISE" in source
    assert 'pending_file=filename' in source
    assert '"completed_at"' in source
    assert "_schedule_after_current" in source
    assert "force=force" in source
    schedule = source.split("    def schedule(", 1)[1].split(
        "    def _queue_after_task", 1
    )[0]
    assert "current.cancel()" not in schedule
    assert "_queue_after_task(sensor_id, current, delay)" in schedule
    assert "_migrate_sensor_state" in source
    assert "FILE_RETRY_FRONT_LIMIT" in source
    assert 'state.setdefault("file_failures", {})' in source
    assert 'last_error_code=ERROR_CODE_BY_STAGE.get(stage, "unknown")' in source
    assert '"cycplus_last_error": state.get("last_error_code") or "none"' in source
    assert "MAX_FILES_PER_SYNC = 3" in source
    assert "MAX_BYTES_PER_SYNC" in source
    assert "queue[:download_slots]" in source
    assert "_import_records_to_profiles" in source
    assert "workout.as_persistent_dict()" in source
    assert "asyncio.timeout(SHUTDOWN_TIMEOUT)" in source
    assert "history_compaction_version" in manager
    assert "as_persistent_dict() for item in merged" in manager
    assert "async_import_device_workouts" in manager
    assert "CAPABILITY_WORKOUT_HISTORY not in sensor.capabilities" in source
    registry = (FIT / "device_archives.py").read_text(encoding="utf-8")
    adapter = (FIT / "device_adapters" / "cycplus_adapter.py").read_text(encoding="utf-8")
    assert "cycplus" not in bluetooth.lower()
    assert "cycplus" not in registry.lower()
    assert "cycplus_m1_identity" in adapter
    assert "CYCPLUS_M1_SERVICE_UUID" in adapter
    assert "device_archives.enrich_connected_metadata" in bluetooth


def test_archive_capability_never_becomes_a_live_metric():
    const = load_module("cycplus_test.const_again", "const.py")
    assert const.CAPABILITY_WORKOUT_HISTORY not in const.LIVE_METRICS


def test_user_documentation_explains_hardware_locality_and_resume_boundary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sensors = (ROOT / "docs" / "LIVE_SENSORS.md").read_text(encoding="utf-8")
    calendar = (ROOT / "docs" / "WORKOUT_CALENDAR.md").read_text(encoding="utf-8")
    assert "CYCPLUS M1 workout import" in readme
    assert "connectable Home Assistant Bluetooth adapter or proxy" in readme
    assert "## CYCPLUS M1 workout archive" in sensors
    assert "file boundary" in sensors
    assert "CRC" in sensors
    assert "validated device FIT archive" in calendar
