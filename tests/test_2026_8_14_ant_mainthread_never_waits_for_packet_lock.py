"""HA control-plane calls must never wait for ANT packet-processing locks."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = (
    ROOT / "custom_components/fitness/live/antplus_core/receiver.py"
).read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()


def test_acceptance_setter_is_lock_free():
    block = RECEIVER.split("def set_device_telemetry_enabled", 1)[1].split(
        "def add_device_callback", 1
    )[0]
    assert "with self._lock" not in block
    assert "_telemetry_enabled_devices" in block


def test_forget_request_is_lock_free_for_ha_caller():
    block = RECEIVER.split("def forget_device", 1)[1].split(
        "def set_device_telemetry_enabled", 1
    )[0]
    assert "with self._lock" not in block
    assert "_forget_requested" in block


def test_forget_is_applied_inside_packet_worker():
    process = RECEIVER.split("def process_packet", 1)[1].split(
        "new_device = False", 1
    )[0]
    assert "if device_id in self._forget_requested:" in process
    assert "with self._lock:" in process


def test_unconfigured_ant_defaults_to_no_metric_decode():
    process = RECEIVER.split("def process_packet", 1)[1].split(
        "def _decode_metadata", 1
    )[0]
    assert (
        "telemetry_enabled = device_id in self._telemetry_enabled_devices"
        in process
    )
    assert ".get(device_id, True)" not in process


def test_discovery_capabilities_come_from_profiles_not_live_values():
    assert "def _profile_capabilities" in ANT
    block = ANT.split("def _publish_device", 1)[1].split(
        "def _has_available_receiver", 1
    )[0]
    assert "caps = _profile_capabilities(profiles) | metric_caps" in block
