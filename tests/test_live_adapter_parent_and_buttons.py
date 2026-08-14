from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_ant_usb_receiver_is_child_of_logical_ant_adapter():
    assert '(DOMAIN, "live_adapter:antplus")' in ADAPTER
    assert '"via_device_id": parent.id' in ADAPTER
    assert 'update_kwargs["new_config_subentry_id"] = parent.config_subentry_id' in ADAPTER


def test_hub_has_no_capture_or_manual_gatt_buttons():
    assert "AntReceiverStartCaptureButton" not in BUTTON
    assert "AntReceiverStopCaptureButton" not in BUTTON
    assert "SensorGattConnectButton" not in BUTTON
    assert "SensorGattDisconnectButton" not in BUTTON
    assert 'if entry.data.get("entry_type") == HUB_ENTRY_TYPE:' in BUTTON
