from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
CONFIG = (FIT / "config_flow.py").read_text(encoding="utf-8")
INIT = (FIT / "__init__.py").read_text(encoding="utf-8")
SWITCH = (FIT / "switch.py").read_text(encoding="utf-8")


def test_adapter_devices_are_permanent_but_modules_are_switch_gated():
    assert 'self._configured[name] = (' in RUNTIME
    assert 'self._enabled[name] = (' in RUNTIME
    assert 'adapter_device_model' in RUNTIME
    assert 'wanted = {name: self.adapter_enabled(name) for name in TRANSPORTS}' in RUNTIME
    assert 'if wanted["bluetooth"] and "bluetooth" not in self.providers:' in RUNTIME
    assert 'if wanted["antplus"]:' in RUNTIME
    assert 'if not wanted.get(name, False):' in RUNTIME
    assert 'await self.providers.pop(name).async_shutdown()' in RUNTIME


def test_profile_setup_has_no_antplus_or_bluetooth_enable_flow():
    assert 'async def async_step_live_transports' not in CONFIG
    assert 'menu.append("live_transports")' not in CONFIG
    assert 'CONF_BLUETOOTH_ENABLED' not in CONFIG
    assert 'CONF_ANTPLUS_ENABLED' not in CONFIG
    assert 'async def async_step_live_devices' in CONFIG


def test_existing_profiles_self_heal_protocol_and_device_services_after_startup():
    assert 'def _schedule_sensors_adapters_entry' in INIT
    assert 'EVENT_HOMEASSISTANT_STARTED' in INIT
    assert 'async_refresh_adapter_presence' in INIT
    assert 'async_ensure_hub_for_presence' in RUNTIME
    assert 'data={"live_hub": True}' in RUNTIME
    assert 'data={"devices_hub": True}' in RUNTIME
    assert 'await self.async_ensure_devices_hub()' in RUNTIME


def test_topology_is_two_services_with_flat_physical_protocol_hardware():
    assert 'DEVICES_HUB_ENTRY_TYPE = "devices_hub"' in RUNTIME
    assert 'title="Fitness Protocols"' in CONFIG
    assert 'title="Fitness Devices"' in CONFIG
    assert 'ANTPLUS_SUBENTRY_TYPE = "antplus_adapters"' in RUNTIME
    assert 'BLUETOOTH_SUBENTRY_TYPE = "bluetooth_adapters"' in RUNTIME
    assert 'title = "ANT+"' in RUNTIME
    assert 'title = "Bluetooth"' in RUNTIME
    assert 'config_entry_id=self.devices_entry.entry_id' in RUNTIME or '"config_entry_id": self.devices_entry.entry_id' in RUNTIME
    assert 'def ensure_ant_receiver_topology' in RUNTIME
    assert 'kwargs["via_device_id"] = None' in RUNTIME
    assert 'def ensure_hub_device' not in RUNTIME


def test_physical_adapter_switches_own_enable_and_scan_controls():
    assert 'class PhysicalAdapterEnabledSwitch' in SWITCH
    assert 'class PhysicalAdapterAutomaticScanSwitch' in SWITCH
    assert 'await self.runtime.async_set_receiver_enabled(self.transport, self.receiver_id, True)' in SWITCH
    assert 'await self.runtime.async_set_receiver_automatic_scan(self.transport, self.receiver_id, True)' in SWITCH
