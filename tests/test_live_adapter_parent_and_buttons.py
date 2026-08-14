from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_ant_usb_receiver_is_child_of_logical_ant_adapter():
    assert '(DOMAIN, "live_adapter:antplus")' in ADAPTER
    assert '"via_device_id": parent.id' in ADAPTER
    assert 'update_kwargs["new_config_subentry_id"] = parent.config_subentry_id' in ADAPTER


def test_capture_buttons_are_receiver_scoped_only():
    # ANT receiver hardware capture controls still follow receiver runtime state.
    assert 'self.runtime.add_listener(self._update)' in BUTTON
    assert 'not record.displayed_capture' in BUTTON
    assert 'record.displayed_capture' in BUTTON
    assert 'self.runtime.notify_changed()' in BUTTON
    # Physical sensors have no logical capture controls; adapter enablement is
    # the module boundary and BLE GATT remains a sensor-specific action.
    assert 'SensorTransportStartCaptureButton' not in BUTTON
    assert 'SensorTransportStopCaptureButton' not in BUTTON
    assert 'SensorGattConnectButton' in BUTTON
    assert 'def notify_changed(self) -> None:' in RUNTIME
    setter = RUNTIME.split("async def async_set_transport_enabled", 1)[1].split(
        "async def async_register_profile", 1
    )[0]
    assert 'await self.async_refresh_modules()' in setter
    assert 'self._mark_transport_runtime_inactive(transport)' in setter
    assert 'self._notify()' in setter
