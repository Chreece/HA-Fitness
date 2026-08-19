"""Architecture guards: generic Bluetooth code must not own physical devices."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
BT = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")
BUTTON = (FIT / "button.py").read_text(encoding="utf-8")
REGISTRY = (FIT / "device_archives.py").read_text(encoding="utf-8")
ADAPTER_REGISTRY = (FIT / "device_adapters" / "registry.py").read_text(encoding="utf-8")


def test_main_bluetooth_transport_has_no_physical_device_hardcodes():
    lower = BT.lower()
    for token in ("garmin", "cycplus", "forerunner"):
        assert token not in lower
    assert "DeviceArchiveRegistry" in BT
    assert "device_archives.match_bluetooth" in BT
    assert "device_archives.enrich_connected_metadata" in BT
    assert "device_archives.coordinator_for_metadata" in BT


def test_archive_button_platform_is_adapter_driven_too():
    lower = BUTTON.lower()
    for token in ("garmin", "cycplus", "forerunner"):
        assert token not in lower
    assert "sync_action_for_metadata" in BUTTON
    assert "coordinator_for_metadata" in BUTTON
    assert "ArchiveSyncWorkoutsButton" in BUTTON


def test_physical_device_knowledge_lives_in_adapter_registry():
    lower = REGISTRY.lower()
    for token in ("garmin", "cycplus", "forerunner"):
        assert token not in lower
    assert "ARCHIVE_ADAPTERS" in REGISTRY
    assert "cycplus_adapter" in ADAPTER_REGISTRY
    assert ".garmin" in ADAPTER_REGISTRY
