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


def test_ant_receivers_are_real_children_of_logical_ant_adapter():
    assert 'via_device_id=parent.id' in ANT
    assert 'config_subentry_id=adapters_subentry_id' in ANT
    assert 'def ensure_ant_receiver_topology' in RUNTIME
    assert 'kwargs["via_device_id"] = parent.id' in RUNTIME
    assert 'self.runtime.ensure_ant_receiver_topology()' in SWITCH


def test_presence_detection_auto_enables_backend_without_startup_task_leak():
    assert 'if present and not self.adapter_enabled(transport):' in RUNTIME
    assert 'fitness auto-enable {transport} backend' in RUNTIME
    assert 'async_create_background_task' in RUNTIME
    block = RUNTIME[RUNTIME.index('def _start_presence_monitor'):RUNTIME.index('def publish_passive')]
    assert 'EVENT_HOMEASSISTANT_STARTED' in block
    assert 'async_create_background_task' in block
    assert 'self.hass.async_create_task(_poll())' not in block
