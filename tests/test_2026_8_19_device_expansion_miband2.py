from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "custom_components/fitness/device_adapters/miband2/protocol.py"
spec = importlib.util.spec_from_file_location("fitness_miband2_protocol_test", PROTO)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_miband2_identity_is_strict_to_model_and_fee1():
    services = [module.MIBAND2_SERVICE_UUID]
    assert module.miband2_identity("MI Band 2", services)["archive_adapter"] == "xiaomi_miband2"
    assert module.miband2_identity("Mi Band 3", services) is None
    assert module.miband2_identity("MI Band 2", []) is None


def test_miband2_auth_challenge_and_success_parser():
    challenge = bytes(range(16))
    assert module.parse_auth_notification(b"\x10\x02\x01" + challenge) == ("challenge", challenge)
    assert module.parse_auth_notification(b"\x10\x03\x01") == ("authenticated", None)
    assert module.parse_auth_notification(b"\x10\x02\x04") == ("failed_2", None)


def test_miband2_fetch_request_and_actual_start():
    dt = datetime(2018, 6, 20, 21, 20)
    assert module.build_fetch_request(dt) == b"\x01\x01\xe2\x07\x06\x14\x15\x14\x00\x08"
    actual = module.parse_fetch_start(b"\x10\x01\x01\xe2\x07\x06\x14\x15\x14")
    assert actual == dt


def test_miband2_activity_packet_uses_index_and_four_minute_records():
    packet = bytes([
        0x39,
        0x11, 0x1B, 0x07, 0x3F,
        0x60, 0x2B, 0xF4, 0x41,
        0x60, 0x12, 0x00, 0x4B,
        0x50, 0x09, 0x00, 0xFF,
    ])
    start = datetime(2018, 6, 20, 0, 0)
    samples = module.parse_activity_packet(
        packet,
        transfer_start_local=start,
        packet_number=57,
        timezone_info=timezone.utc,
    )
    assert len(samples) == 4
    assert samples[0].timestamp == datetime(2018, 6, 20, 3, 48, tzinfo=timezone.utc)
    assert samples[0].steps == 7 and samples[0].heart_rate == 63
    assert samples[3].heart_rate is None
    assert 10.0 <= samples[0].activity_level <= 11.0


def test_miband2_simple_device_state_parsers_are_bounded():
    assert module.parse_battery_level(b"\x64\x00") == 100
    assert module.parse_realtime_steps((12345).to_bytes(4, "little")) == 12345


def test_miband2_never_auto_initializes_or_claims_sleep():
    coordinator = (ROOT / "custom_components/fitness/device_adapters/miband2/coordinator.py").read_text()
    adapter = (ROOT / "custom_components/fitness/device_adapters/miband2/adapter.py").read_text()
    assert "AUTH_REQUEST_RANDOM" in coordinator
    assert "AUTH_SEND_KEY" not in coordinator
    assert 'sync_capabilities=frozenset({"health_history", "device_state"})' in adapter
    assert '"sleep_history"' not in adapter
    assert "fitness_device_user_action_required" in coordinator
