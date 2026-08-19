"""Direct-device non-FIT history protocol and architecture regression contracts."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import struct
import sys
import types

from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"


def _pure(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, FIT / rel)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


uh = _pure("direct_history_test_ultrahuman_protocol", "device_adapters/ultrahuman/protocol.py")
zt = _pure("direct_history_test_zetime_protocol", "device_adapters/zetime/protocol.py")
hp = _pure("direct_history_test_hplus_protocol", "device_adapters/hplus/protocol.py")


def test_ultrahuman_identity_is_protocol_or_exact_family_name_not_broad_brand_matching():
    assert uh.ultrahuman_identity("UH_A1B2C3D4E5F6", []) is not None
    assert uh.ultrahuman_identity("UH_NOT_A_MAC", []) is None
    assert uh.ultrahuman_identity("random", [uh.ULTRAHUMAN_COMMAND_SERVICE_UUID]) is not None
    identity = uh.ultrahuman_identity("UH_A1B2C3D4E5F6", [])
    assert identity["archive_adapter"] == "ultrahuman_air"
    assert identity["workout_archive"] is False


def test_ultrahuman_documented_record_decodes_without_destructive_commands():
    # Public protocol example is 30 bytes; append a synthetic uint16 record index.
    record = bytes.fromhex(
        "E945AD67443362018546AD67785B0E4230D20C428546AD67960025003300"
    ) + struct.pack("<H", 0x0532)
    result, records = uh.parse_recordings_response(b"\x04\x00\x01" + record + b"\x00\x00")
    assert result == uh.RESULT_OK
    assert len(records) == 1
    item = records[0]
    assert item.index == 0x0532
    assert item.heart_rate == 68
    assert item.hrv_ms == 51
    assert item.spo2 == 98
    assert item.activity_level == 150
    assert item.steps == 37
    assert item.stress == 51
    assert uh.build_index_command(uh.OP_EARLIEST) == b"\x07"
    assert uh.build_index_command(uh.OP_LATEST) == b"\x08"
    assert uh.build_recordings_command(0x1234) == b"\x04\x34\x12"


def test_ultrahuman_checkpoint_handles_uint16_wrap_and_reset():
    assert uh.next_available_index(100, 105, None) == 100
    assert uh.next_available_index(100, 105, 102) == 103
    assert uh.next_available_index(100, 105, 105) is None
    assert uh.next_available_index(0xFFFE, 1, 0xFFFF) == 0
    # Old checkpoint outside the device's currently retained circular window.
    assert uh.next_available_index(500, 700, 100) == 500


def test_zetime_documented_read_only_requests_and_payloads():
    assert zt.build_history_request(zt.SUBJECT_AVAILABILITY).hex() == "6f52700100008f"
    assert zt.build_history_request(zt.SUBJECT_ACTIVITY, 0).hex() == "6f5470020000008f"

    activity_payload = struct.pack("<HIIIII", 4, 1_700_000_000, 12345, 678, 9012, 88)
    activity = zt.parse_activity(zt.ZeTimeFrame(zt.SUBJECT_ACTIVITY, zt.TYPE_RESPONSE, activity_payload))
    assert (activity.packet, activity.steps, activity.calories, activity.distance_m, activity.activity_minutes) == (
        4, 12345, 678, 9012, 88
    )

    sleep_payload = struct.pack("<HIB", 7, 1_700_000_100, zt.SLEEP_DEEP)
    sleep = zt.parse_sleep(zt.ZeTimeFrame(zt.SUBJECT_SLEEP, zt.TYPE_RESPONSE, sleep_payload))
    assert sleep.packet == 7 and sleep.sleep_type == zt.SLEEP_DEEP

    hr_payload = struct.pack("<HIB", 8, 1_700_000_200, 61)
    hr = zt.parse_heart_rate(zt.ZeTimeFrame(zt.SUBJECT_HEART_RATE, zt.TYPE_RESPONSE, hr_payload))
    assert hr.packet == 8 and hr.heart_rate == 61

    identity = zt.zetime_identity("ZeTime", [])
    assert identity["archive_adapter"] == "mykronoz_zetime"
    assert identity["workout_archive"] is False


def test_zetime_frame_buffer_is_bounded_and_reassembles_att_chunks():
    raw = zt.build_frame(zt.SUBJECT_HEART_RATE, zt.TYPE_RESPONSE, struct.pack("<HIB", 2, 1_700_000_000, 70))
    buffer = zt.ZeTimeFrameBuffer()
    assert buffer.feed(raw[:4]) == []
    assert buffer.feed(raw[4:9]) == []
    frames = buffer.feed(raw[9:])
    assert len(frames) == 1
    assert zt.parse_heart_rate(frames[0]).heart_rate == 70



def test_zetime_sleep_events_reconstruct_explicit_canonical_night():
    components = sys.modules.setdefault(
        "homeassistant.components", types.ModuleType("homeassistant.components")
    )
    components.__path__ = []
    bluetooth = sys.modules.setdefault(
        "homeassistant.components.bluetooth", types.ModuleType("homeassistant.components.bluetooth")
    )
    components.bluetooth = bluetooth
    storage = sys.modules.setdefault(
        "homeassistant.helpers.storage", types.ModuleType("homeassistant.helpers.storage")
    )

    class _Store:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    storage.Store = _Store

    root = sys.modules.setdefault("direct_history_runtime_test", types.ModuleType("direct_history_runtime_test"))
    root.__path__ = [str(FITNESS)]
    providers = sys.modules.setdefault(
        "direct_history_runtime_test.providers", types.ModuleType("direct_history_runtime_test.providers")
    )
    providers.__path__ = [str(FITNESS / "providers")]
    adapters = sys.modules.setdefault(
        "direct_history_runtime_test.device_adapters", types.ModuleType("direct_history_runtime_test.device_adapters")
    )
    adapters.__path__ = [str(FITNESS / "device_adapters")]
    zpkg = sys.modules.setdefault(
        "direct_history_runtime_test.device_adapters.zetime",
        types.ModuleType("direct_history_runtime_test.device_adapters.zetime"),
    )
    zpkg.__path__ = [str(FITNESS / "device_adapters" / "zetime")]

    load_module("direct_history_runtime_test.const", "const.py")
    load_module("direct_history_runtime_test.providers.workouts", "providers/workouts.py")
    load_module("direct_history_runtime_test.providers.sleep", "providers/sleep.py")
    load_module("direct_history_runtime_test.device_adapters.history", "device_adapters/history.py")
    load_module(
        "direct_history_runtime_test.device_adapters.history_coordinator",
        "device_adapters/history_coordinator.py",
    )
    zp = load_module(
        "direct_history_runtime_test.device_adapters.zetime.protocol",
        "device_adapters/zetime/protocol.py",
    )
    zc = load_module(
        "direct_history_runtime_test.device_adapters.zetime.coordinator",
        "device_adapters/zetime/coordinator.py",
    )

    start = 1_700_000_000
    events = [
        zp.ZeTimeSleepEvent(0, start, zp.SLEEP_BEGIN),
        zp.ZeTimeSleepEvent(1, start + 600, zp.SLEEP_LIGHT),
        zp.ZeTimeSleepEvent(2, start + 2400, zp.SLEEP_DEEP),
        zp.ZeTimeSleepEvent(3, start + 6000, zp.SLEEP_AWAKE),
        zp.ZeTimeSleepEvent(4, start + 6600, zp.SLEEP_END),
    ]
    records = zc.ZeTimeCoordinator._sleep_records(events, "sensor:test")
    assert len(records) == 1
    record = records[0]
    assert record.duration_s == 6600
    assert record.light_sleep_s == 1800
    assert record.deep_sleep_s == 3600
    assert record.awake_s == 600
    assert record.rem_sleep_s is None
    assert record.provider_domain == "direct_mykronoz_zetime"

def test_hplus_identity_requires_unique_protocol_service_and_day_summary_decodes():
    assert hp.hplus_identity("Zeband", []) is None
    identity = hp.hplus_identity("anything", [hp.HPLUS_SERVICE_UUID.upper()])
    assert identity is not None
    assert identity["archive_adapter"] == "hplus_history"
    assert identity["workout_archive"] is False
    assert hp.build_day_history_request() == b"\x15"

    # 2026-08-19, 1234 steps, 456 m, documented four-byte calorie formula,
    # 90 active minutes, max HR 155, min HR 52.
    year = 2026
    payload = bytes([
        hp.DATA_DAY_SUMMARY,
        0xD2, 0x04,  # steps = 1234
        0xC8, 0x01,  # distance = 456
        1, 2, 3, 4,  # calories follow the documented HPlus formula
        year & 0xFF, (year >> 8) & 0xFF,
        8, 19,
        90, 0,
        155, 52,
    ])
    item = hp.parse_day_summary(payload)
    assert item.day.isoformat() == "2026-08-19"
    assert item.steps == 1234
    assert item.distance_m == 456
    assert item.calories == 2 * 256 + 4 * 256 + 3 + 1
    assert item.activity_minutes == 90
    assert item.max_heart_rate == 155
    assert item.min_heart_rate == 52


def test_non_fit_history_batch_and_manager_boundary_are_hard_bounded():
    # Load only the provider/dataclass modules required by the generic history contract.
    root_pkg = sys.modules.setdefault("direct_history_contract_test", types.ModuleType("direct_history_contract_test"))
    root_pkg.__path__ = [str(FITNESS)]
    providers_pkg = sys.modules.setdefault(
        "direct_history_contract_test.providers", types.ModuleType("direct_history_contract_test.providers")
    )
    providers_pkg.__path__ = [str(FITNESS / "providers")]
    adapters_pkg = sys.modules.setdefault(
        "direct_history_contract_test.device_adapters", types.ModuleType("direct_history_contract_test.device_adapters")
    )
    adapters_pkg.__path__ = [str(FITNESS / "device_adapters")]
    load_module("direct_history_contract_test.providers.workouts", "providers/workouts.py")
    sleep = load_module("direct_history_contract_test.providers.sleep", "providers/sleep.py")
    history = load_module("direct_history_contract_test.device_adapters.history", "device_adapters/history.py")

    points = [
        history.DeviceMetricPoint("steps", float(i), "2026-08-19T00:00:00+00:00", "test")
        for i in range(history.MAX_DEVICE_METRIC_POINTS + 10)
    ]
    sleeps = [
        sleep.SleepRecord(
            source="test",
            provider_domain="test",
            start="2026-08-18T22:00:00+00:00",
            end="2026-08-19T06:00:00+00:00",
        )
        for _ in range(history.MAX_DEVICE_SLEEP_RECORDS + 10)
    ]
    batch = history.DeviceHistoryBatch.bounded(metric_points=points, sleep_records=sleeps)
    assert len(batch.metric_points) == history.MAX_DEVICE_METRIC_POINTS
    assert len(batch.sleep_records) == history.MAX_DEVICE_SLEEP_RECORDS

    manager = (FIT / "manager.py").read_text(encoding="utf-8")
    assert "async def async_import_device_history" in manager
    assert "validate_sleep(record, now)" in manager
    assert "await self._save()" in manager


def test_wellness_only_archive_adapters_are_visible_in_smart_fitness_flow():
    pkg = sys.modules.setdefault("direct_history_smart_pkg", types.ModuleType("direct_history_smart_pkg"))
    pkg.__path__ = [str(FITNESS)]
    load_module("direct_history_smart_pkg.const", "const.py")
    smart = load_module("direct_history_smart_pkg.smart_workout_devices", "smart_workout_devices.py")

    class Endpoint:
        def __init__(self, metadata):
            self.metadata = metadata

    class Sensor:
        metadata = {}
        capabilities = set()
        endpoints = {
            "bluetooth": Endpoint(
                {
                    "archive_adapter": "ultrahuman_air",
                    "workout_archive": False,
                    "fitness_vendor_identity": "ultrahuman",
                }
            )
        }

    sensor = Sensor()
    assert smart.smart_workout_archive_compatibility(sensor) is None
    # Smart Fitness Devices intentionally includes health/sleep-only direct
    # devices; workout archive compatibility remains a separate capability.
    assert smart.is_smart_workout_candidate(sensor) is True


def test_new_device_specific_fingerprints_stay_out_of_generic_bluetooth_hot_path():
    bluetooth_source = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8").lower()
    for token in (
        "ultrahuman",
        "zetime",
        "mykronoz",
        "hplus",
        "86f65000",
        "14701820",
        "6006",
    ):
        assert token not in bluetooth_source

    registry = (FIT / "device_adapters" / "registry.py").read_text(encoding="utf-8")
    for adapter in ("ULTRAHUMAN_AIR_ARCHIVE_ADAPTER", "ZETIME_ARCHIVE_ADAPTER", "HPLUS_ARCHIVE_ADAPTER"):
        assert adapter in registry
