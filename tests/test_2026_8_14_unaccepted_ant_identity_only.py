"""Unaccepted ANT sensors must not run continuous telemetry decoding."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = (
    ROOT / "custom_components/fitness/live/antplus_core/receiver.py"
).read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()


def test_receiver_has_per_device_telemetry_gate():
    assert "def set_device_telemetry_enabled" in RECEIVER
    init = RECEIVER.split("def __init__", 1)[1].split("@property", 1)[0]
    assert "self._telemetry_enabled_devices: frozenset[int] = frozenset()" in init


def test_unaccepted_device_skips_decode_packet():
    block = RECEIVER.split("telemetry_enabled =", 1)[1].split(
        "# FE-C command status", 1
    )[0]
    assert "if telemetry_enabled:" in block
    assert "decode_packet(device, device_type, payload)" in block
    assert "decoded_metrics = []" in block
    assert "telemetry_decode_suppressed" in block


def test_unaccepted_ordinary_telemetry_skips_packet_callbacks():
    assert "if telemetry_enabled or int(device_type) in (16, 115):" in RECEIVER


def test_provider_enables_decode_only_when_live_sensor_is_needed():
    block = ANT.split("def _publish_device", 1)[1].split(
        "def _publish_metric_values", 1
    )[0]
    assert "sensor_live_telemetry_needed" in block
    assert "set_device_telemetry_enabled" in block


def test_acceptance_change_recomputes_live_decode_need():
    block = ANT.split("def sensor_acceptance_changed", 1)[1].split(
        "def forget_device", 1
    )[0]
    assert "sensor_live_telemetry_needed" in block
    assert "set_device_telemetry_enabled" in block
