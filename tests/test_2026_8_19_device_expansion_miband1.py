from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from conftest import FITNESS
import importlib.util
import sys


def _pure_protocol():
    spec = importlib.util.spec_from_file_location("miband1_protocol_test", FITNESS / "device_adapters/miband1/protocol.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mb = _pure_protocol()

from miband1_protocol_test import (
    ACTIVITY_TYPE_DEEP_SLEEP,
    ACTIVITY_TYPE_LIGHT_SLEEP,
    MIBAND1_SERVICE_UUID,
    build_activity_ack,
    miband1_identity,
    parse_activity_header,
    parse_activity_records,
    parse_battery_state,
    parse_realtime_steps,
)


def test_miband1_identity_requires_legacy_name_and_service():
    assert miband1_identity("MI", [MIBAND1_SERVICE_UUID])["archive_adapter"] == "xiaomi_miband1"
    assert miband1_identity("MI1S", [MIBAND1_SERVICE_UUID])["model"] == "Xiaomi Mi Band 1S"
    assert miband1_identity("Amazfit Bip", [MIBAND1_SERVICE_UUID]) is None
    assert miband1_identity("MI", []) is None


def test_activity_header_records_and_ack_are_timestamped():
    # 2026-08-19 07:14:33 local, two records in this block.
    header = parse_activity_header(bytes([1, 26, 7, 19, 7, 14, 33, 2, 0, 2, 0]))
    assert header.start_local == datetime(2026, 8, 19, 7, 14, 33)
    assert header.block_bytes == 6
    assert build_activity_ack(header) == bytes([0x0A, 26, 7, 19, 7, 14, 33, 6, 0])

    samples = parse_activity_records(
        bytes([ACTIVITY_TYPE_LIGHT_SLEEP, 3, 0, ACTIVITY_TYPE_DEEP_SLEEP, 1, 0]),
        start=header.start_local,
        timezone_info=ZoneInfo("Europe/Berlin"),
    )
    assert len(samples) == 2
    assert samples[0].activity_name == "light_sleep"
    assert samples[1].activity_name == "deep_sleep"
    assert samples[1].timestamp > samples[0].timestamp
    assert samples[0].timestamp.tzinfo == timezone.utc


def test_battery_and_realtime_steps_parsers_are_bounded():
    state = parse_battery_state(bytes([81, 26, 7, 18, 22, 5, 0, 4, 0, 2]))
    assert state.battery == 81
    assert state.charge_cycles == 4
    assert state.charging is True
    assert state.last_charge_local == datetime(2026, 8, 18, 22, 5, 0)
    assert parse_realtime_steps((959).to_bytes(4, "little")) == 959


def test_manager_preserves_bounded_intraday_device_samples_and_daily_summary():
    manager = (FITNESS / "manager.py").read_text()
    assert "device_intraday_history" in manager
    assert "MAX_DEVICE_INTRADAY_POINTS_PER_METRIC = 4096" in manager
    assert '"measurement_context") or "") == "current_total"' in manager
    assert 'source_type="direct_device_daily_summary"' in manager


def test_miband1_coordinator_never_partially_acks_a_history_block():
    coordinator = (FITNESS / "device_adapters/miband1/coordinator.py").read_text()
    guard = "processed_minutes + len(samples) > MAX_MINUTES_PER_SYNC"
    assert guard in coordinator
    assert coordinator.index(guard) < coordinator.index("build_activity_ack(header, len(block))")
