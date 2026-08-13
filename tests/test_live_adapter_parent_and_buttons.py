from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def test_ant_usb_receiver_is_child_of_logical_ant_adapter():
    assert '(DOMAIN, "live_adapter:antplus")' in ADAPTER
    assert '"via_device_id": parent.id' in ADAPTER
    assert 'update_kwargs["new_config_subentry_id"] = parent.config_subentry_id' in ADAPTER


def test_adapter_buttons_follow_runtime_enable_and_capture_state():
    assert 'self.runtime.add_listener(self._runtime_update)' in BUTTON
    assert 'not provider.capture_active' in BUTTON
    assert 'and provider.capture_active' in BUTTON
    assert 'self.runtime.notify_changed()' in BUTTON
    assert 'def notify_changed(self) -> None:' in RUNTIME
    assert 'await self.async_refresh_modules()\n        self._notify()' in RUNTIME
