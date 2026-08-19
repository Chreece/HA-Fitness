from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
I = (ROOT / "custom_components/fitness/__init__.py").read_text()
S = (ROOT / "custom_components/fitness/live/ha_entities.py").read_text()
B = (ROOT / "custom_components/fitness/binary_sensor.py").read_text()


def test_sensors_use_separate_fitness_devices_config_entry():
    assert 'DEVICES_HUB_ENTRY_TYPE = "devices_hub"' in R
    assert 'self.devices_entry = entry' in R
    assert '"config_entry_id": self.devices_entry.entry_id' in R
    assert 'runtime.ensure_sensors_subentry()' not in S
    assert 'runtime.ensure_sensors_subentry()' not in B
    assert '_remove_legacy_sensor_subentry_if_empty' in R

def test_adapters_use_real_adapters_subentry():
    assert 'ANTPLUS_SUBENTRY_TYPE = "antplus_adapters"' in R
    assert 'BLUETOOTH_SUBENTRY_TYPE = "bluetooth_adapters"' in R
    assert '_migrate_adapter_devices_to_transport_subentries()' in R
