from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_ant_usb_receiver_is_flat_physical_device_under_ant_subentry():
    assert 'live_adapter:antplus' not in ADAPTER
    assert 'kwargs["via_device_id"] = None' in ADAPTER
    assert 'config_subentry_id=adapters_subentry_id' in ADAPTER
    assert 'live_adapter:antplus' not in ADAPTER


def test_hub_has_no_capture_or_manual_gatt_buttons():
    assert "AntReceiverStartCaptureButton" not in BUTTON
    assert "AntReceiverStopCaptureButton" not in BUTTON
    assert "SensorGattConnectButton" not in BUTTON
    assert "SensorGattDisconnectButton" not in BUTTON
    assert 'PhysicalAdapterScanNowButton' in BUTTON


def test_runtime_removes_obsolete_fake_protocol_devices():
    assert 'f"live_adapter:{transport}"' in RUNTIME
    assert 'registry.async_remove_device(device.id)' in RUNTIME
