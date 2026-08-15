"""ANT identity is profile-qualified and confirmed before structural mutation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = (
    ROOT / "custom_components/fitness/live/antplus_core/receiver.py"
).read_text()


def test_known_profile_names_are_not_common_page_permission():
    meta = RECEIVER.split("def _metadata_candidate", 1)[1].split(
        "def _observe_metadata_candidate", 1
    )[0]
    assert "device_type in DEVICE_TYPE_NAMES" not in meta
    assert "device_type in COMMON_IDENTITY_PAGE_PROFILES" in meta


def test_provisional_gate_uses_same_profile_qualified_identity_rule():
    process = RECEIVER.split("def process_packet", 1)[1].split(
        "device.transmission_types.add", 1
    )[0]
    helper = RECEIVER.split("def _is_identity_page", 1)[1].split(
        "class AntPlusReceiver", 1
    )[0]
    assert "identity_page = _is_identity_page(device_type, page)" in process
    assert "COMMON_IDENTITY_PAGE_PROFILES" in helper
    assert "BSC_IDENTITY_PAGE_PROFILES" in helper
    assert "DEVICE_TYPE_HEART_RATE" in helper


def test_identity_requires_repeated_evidence_except_serial_identity_pages():
    block = RECEIVER.split("def _observe_metadata_candidate", 1)[1].split(
        "def ", 1
    )[0]
    assert "IDENTITY_CONFIRM_OBSERVATIONS" in block
    assert "previous[0] == signature" in block
    assert "serial_identity_page" in block
    assert "DEVICE_TYPE_HEART_RATE and page == 2" in block
    assert "BSC_IDENTITY_PAGE_PROFILES and page == 2" in block
    assert "COMMON_IDENTITY_PAGE_PROFILES and page == 0x51" in block
    assert "1 if serial_identity_page else IDENTITY_CONFIRM_OBSERVATIONS" in block
    assert "if count < required_observations:" in block
    assert "setattr(device, attr, value)" in block


def test_single_identity_packet_cannot_mutate_device():
    process = RECEIVER.split("def process_packet", 1)[1].split(
        "# Repeated ANT pages", 1
    )[0]
    assert "metadata_changed = self._observe_metadata_candidate(" in process
    assert "self._decode_metadata(" not in process


def test_raw_only_profiles_are_not_in_common_identity_allowlist_source():
    # Running-dynamics/raw-only recognition may exist elsewhere, but common
    # identity permission is intentionally only the semantic standard set.
    constants = RECEIVER.split(
        "COMMON_IDENTITY_PAGE_PROFILES = frozenset({", 1
    )[1].split("})", 1)[0]
    assert "DEVICE_TYPE_POWER" in constants
    assert "DEVICE_TYPE_FITNESS_EQUIPMENT" in constants
    assert "DEVICE_TYPE_RUNNING_DYNAMICS" not in constants


def test_hr_page2_builds_complete_32bit_serial_from_upper_fragment_and_device_number():
    meta = RECEIVER.split("def _metadata_candidate", 1)[1].split(
        "def _observe_metadata_candidate", 1
    )[0]
    assert "serial_upper = data[2] | (data[3] << 8)" in meta
    assert "(int(serial_upper) << 16) | (int(device_id) & 0xFFFF)" in meta


def test_accepted_ant_has_one_minute_presence_heartbeat_even_when_metric_is_unchanged():
    process = RECEIVER.split("def process_packet", 1)[1].split(
        "def _metadata_candidate", 1
    )[0]
    assert "ANT_LAST_SEEN_CALLBACK_INTERVAL_SECONDS" in process
    assert 'callback_key = "__last_seen__"' in process
