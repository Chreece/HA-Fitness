"""Pre-configuration radio traffic must be discovery/control-plane only."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = (
    ROOT / "custom_components/fitness/live/antplus_core/receiver.py"
).read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()


def test_telemetry_gate_is_initialized_in_constructor():
    init = RECEIVER.split("def __init__", 1)[1].split("@property", 1)[0]
    assert "self._telemetry_enabled_devices: frozenset[int] = frozenset()" in init


def test_disable_capture_does_not_create_missing_gate_lazily():
    block = RECEIVER.split("def disable_capture", 1)[1].split(
        "def start", 1
    )[0]
    assert "_device_telemetry_enabled: dict" not in block


def test_provisional_ant_returns_before_identity_candidate_and_decoder_work():
    process = RECEIVER.split("def process_packet", 1)[1].split(
        "def _metadata_candidate", 1
    )[0]
    guard = process.index(
        "if not telemetry_enabled and not new_profile and not identity_page:"
    )
    ret = process.index("return", guard)
    metadata = process.index("self._observe_metadata_candidate(", ret)
    decode = process.index("decode_packet(", ret)
    assert guard < ret < metadata < decode


def test_only_profile_qualified_identity_pages_bypass_provisional_gate():
    process = RECEIVER.split("def process_packet", 1)[1].split(
        "def _metadata_candidate", 1
    )[0]
    assert "device_type in COMMON_IDENTITY_PAGE_PROFILES" in process
    assert "page in (0x50, 0x51)" in process


def test_ant_runtime_registration_is_structural_signature_gated():
    block = ANT.split("def _publish_device", 1)[1].split(
        "def _has_available_receiver", 1
    )[0]
    signature = block.index("structure_signature = (")
    previous = block.index("previous_structure == structure_signature")
    register = block.index("self.runtime.register_transport_sensor(")
    assert signature < previous < register
    assert "return" in block[previous:register]
