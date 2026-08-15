"""Regression guards for profile-aware ANT discovery and identity layouts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = (ROOT / "custom_components/fitness/live/antplus_core/receiver.py").read_text()
ANTPLUS = (ROOT / "custom_components/fitness/live/antplus.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_semantic_profiles_use_shorter_rf_confirmation_than_unknown_profiles():
    assert "DISCOVERY_CONFIRM_PACKETS = 5" in RECEIVER
    assert "SEMANTIC_DISCOVERY_CONFIRM_PACKETS = 3" in RECEIVER
    helper = RECEIVER.split("def _discovery_confirmation_packets", 1)[1].split(
        "def _is_identity_page", 1
    )[0]
    assert "SEMANTIC_DISCOVERY_PROFILE_TYPES" in helper
    assert "else DISCOVERY_CONFIRM_PACKETS" in helper


def test_semantic_allowlist_covers_non_hr_metric_profiles():
    block = RECEIVER.split("SEMANTIC_DISCOVERY_PROFILE_TYPES = frozenset({", 1)[1].split("})", 1)[0]
    for token in (
        "DEVICE_TYPE_POWER",
        "DEVICE_TYPE_FITNESS_EQUIPMENT",
        "DEVICE_TYPE_ENVIRONMENT",
        "DEVICE_TYPE_BIKE_SPEED_CADENCE",
        "DEVICE_TYPE_BIKE_CADENCE",
        "DEVICE_TYPE_BIKE_SPEED",
        "DEVICE_TYPE_STRIDE_SPEED",
        "DEVICE_TYPE_CORE_TEMP",
    ):
        assert token in block


def test_bsc_uses_profile_pages_2_and_3_not_common_80_81_for_identity():
    common = RECEIVER.split("COMMON_IDENTITY_PAGE_PROFILES = frozenset({", 1)[1].split("})", 1)[0]
    bsc = RECEIVER.split("BSC_IDENTITY_PAGE_PROFILES = frozenset({", 1)[1].split("})", 1)[0]
    assert "DEVICE_TYPE_BIKE_CADENCE" not in common
    assert "DEVICE_TYPE_BIKE_SPEED" not in common
    assert "DEVICE_TYPE_BIKE_SPEED_CADENCE" not in common
    assert "DEVICE_TYPE_BIKE_CADENCE" in bsc
    assert "DEVICE_TYPE_BIKE_SPEED" in bsc
    assert "DEVICE_TYPE_BIKE_SPEED_CADENCE" in bsc


def test_bsc_page2_decodes_manufacturer_and_serial_and_page3_versions():
    meta = RECEIVER.split("def _metadata_candidate", 1)[1].split(
        "def _observe_metadata_candidate", 1
    )[0]
    assert "device_type in BSC_IDENTITY_PAGE_PROFILES and page == 2" in meta
    assert "manufacturer_id = data[1]" in meta
    assert "serial_no = data[2] | (data[3] << 8)" in meta
    assert "device_type in BSC_IDENTITY_PAGE_PROFILES and page == 3" in meta
    assert "hardware_rev = data[1]" in meta
    assert "software_rev = data[2]" in meta
    assert "model_no = data[3]" in meta


def test_common_identity_remains_limited_to_profiles_with_proven_common_pages():
    block = RECEIVER.split("COMMON_IDENTITY_PAGE_PROFILES = frozenset({", 1)[1].split("})", 1)[0]
    assert "DEVICE_TYPE_POWER" in block
    assert "DEVICE_TYPE_FITNESS_EQUIPMENT" in block
    assert "DEVICE_TYPE_STRIDE_SPEED" in block
    assert "DEVICE_TYPE_ENVIRONMENT" not in block
    assert "DEVICE_TYPE_CORE_TEMP" not in block


def test_new_semantic_profile_gets_one_bounded_discovery_decode():
    process = RECEIVER.split("def process_packet", 1)[1].split(
        "if telemetry_enabled or int(device_type)", 1
    )[0]
    assert "discovery_decode_enabled" in process
    assert "new_profile" in process
    assert "SEMANTIC_DISCOVERY_PROFILE_TYPES" in process
    assert "if telemetry_enabled or discovery_decode_enabled:" in process


def test_receiver_confirmation_is_forwarded_to_runtime_discovery():
    publish = ANTPLUS.split("def _publish_device", 1)[1].split(
        "def _has_available_receiver", 1
    )[0]
    ready = RUNTIME.split("def _sensor_discovery_ready", 1)[1].split(
        "def _schedule_sensor_discovery", 1
    )[0]
    assert '"rf_identity_confirmed": True' in publish
    assert 'ant.metadata.get("rf_identity_confirmed")' in ready
    assert "and sensor.capabilities" in ready


def test_background_identity_enriches_but_no_longer_blocks_basic_ant_discovery():
    ready = RUNTIME.split("def _sensor_discovery_ready", 1)[1].split(
        "def _schedule_sensor_discovery", 1
    )[0]
    rf_pos = ready.index('ant.metadata.get("rf_identity_confirmed")')
    fallback_pos = ready.index('manufacturer_id = ant.metadata.get("manufacturer_id")')
    assert rf_pos < fallback_pos
