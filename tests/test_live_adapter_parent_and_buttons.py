from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_ant_usb_receiver_is_child_of_logical_ant_adapter():
    assert '(DOMAIN, "live_adapter:antplus")' in ADAPTER
    assert '"via_device_id": parent.id' in ADAPTER
    assert 'update_kwargs["new_config_subentry_id"] = parent.config_subentry_id' in ADAPTER


def test_capture_buttons_follow_receiver_and_sensor_runtime_state():
    # ANT receiver hardware capture controls still follow receiver runtime state.
    assert 'self.runtime.add_listener(self._update)' in BUTTON
    assert 'not record.displayed_capture' in BUTTON
    assert 'record.displayed_capture' in BUTTON
    assert 'self.runtime.notify_changed()' in BUTTON
    # Per-physical-sensor transport capture gates are targeted listeners and do
    # not rely on the old logical adapter capture buttons.
    assert 'self.runtime.add_sensor_value_listener(' in BUTTON
    assert '"capture", self.transport, self._update' in BUTTON
    assert 'sensor_transport_capture_enabled' in BUTTON
    assert 'async_set_sensor_transport_capture' in BUTTON
    assert 'def notify_changed(self) -> None:' in RUNTIME
    assert 'await self.async_refresh_modules()\n        self._notify()' in RUNTIME
