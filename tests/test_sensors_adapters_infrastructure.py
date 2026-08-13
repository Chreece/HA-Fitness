from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
CONFIG = (FIT / "config_flow.py").read_text(encoding="utf-8")
INIT = (FIT / "__init__.py").read_text(encoding="utf-8")
SWITCH = (FIT / "switch.py").read_text(encoding="utf-8")


def test_adapter_devices_are_permanent_but_modules_are_switch_gated():
    assert 'self._configured[name] = True' in RUNTIME
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
    assert 'if runtime.live_enabled:' in CONFIG


def test_existing_profiles_self_heal_sensors_and_adapters_after_startup():
    assert 'def _schedule_sensors_adapters_entry' in INIT
    assert 'EVENT_HOMEASSISTANT_STARTED' in INIT
    assert 'importlib.import_module' in INIT
    assert 'data={"live_hub": True}' in INIT
    assert '_schedule_sensors_adapters_entry(hass)' in INIT


def test_device_topology_has_adapter_and_sensor_subentries_without_fake_hub_device():
    assert 'ADAPTERS_SUBENTRY_TYPE = "adapters"' in RUNTIME
    assert 'SENSORS_SUBENTRY_TYPE = "sensors"' in RUNTIME
    assert 'title="Adapters"' in RUNTIME
    assert 'title="Sensors"' in RUNTIME
    assert 'async_add_subentry(self.hub_entry, subentry)' in RUNTIME
    assert 'label = "ANT+ Adapter" if transport == "antplus" else "Bluetooth Adapter"' in RUNTIME
    assert 'def ensure_hub_device' not in RUNTIME
    assert '_remove_legacy_grouping_devices()' in RUNTIME
    assert 'def ensure_sensor_collection_device' not in RUNTIME


def test_enable_switch_is_the_only_transport_activation_control():
    assert 'class AdapterEnabledSwitch' in SWITCH
    assert 'await self.runtime.async_set_transport_enabled(self.transport, True)' in SWITCH
    assert 'await self.runtime.async_set_transport_enabled(self.transport, False)' in SWITCH
