from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / 'custom_components/fitness/live/runtime.py').read_text()
INIT = (ROOT / 'custom_components/fitness/__init__.py').read_text()
ANT = (ROOT / 'custom_components/fitness/live/antplus_core/adapter.py').read_text()
SWITCH = (ROOT / 'custom_components/fitness/switch.py').read_text()


def test_native_live_devices_opt_into_ha_device_deletion():
    assert 'async def async_remove_config_entry_device' in INIT
    assert 'runtime.async_forget_sensor' in INIT
    assert 'value.startswith("usb_adapter:")' in INIT
    assert 'value.startswith("live_adapter:")' in INIT


def test_ant_receivers_are_flat_physical_devices_in_ant_group():
    assert 'config_subentry_id=adapters_subentry_id' in ANT
    assert 'live_adapter:antplus' not in ANT
    assert 'kwargs["via_device_id"] = None' in ANT
    assert 'def ensure_ant_receiver_topology' in RUNTIME
    assert 'kwargs["via_device_id"] = None' in RUNTIME


def test_presence_detection_never_auto_enables_user_disabled_backend():
    presence = RUNTIME[RUNTIME.index('def set_adapter_presence'):RUNTIME.index('async def _async_scan_local_ant_usb')]
    assert 'if present and not self.adapter_enabled(transport):' not in presence
    assert 'fitness auto-enable {transport} backend' not in presence
    assert 'async_set_transport_enabled(transport, True)' not in presence

    block = RUNTIME[RUNTIME.index('def _start_presence_monitor'):RUNTIME.index('def publish_passive')]
    assert 'EVENT_HOMEASSISTANT_STARTED' in block
    assert 'async_create_background_task' in block
    assert 'self.hass.async_create_task(_poll())' not in block
