from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
I = (ROOT / "custom_components/fitness/__init__.py").read_text()
S = (ROOT / "custom_components/fitness/live/ha_entities.py").read_text()
B = (ROOT / "custom_components/fitness/binary_sensor.py").read_text()


def test_sensors_use_real_config_subentry_not_fake_collection_device():
    assert 'SENSORS_SUBENTRY_TYPE = "sensors"' in R
    assert 'ConfigSubentry(' in R
    assert 'async_add_subentry(self.hub_entry, subentry)' in R
    assert 'subentry_id = self._sensor_subentry_id()' in R
    assert 'config_subentry_id=subentry_id' in R
    assert 'new_config_subentry_id=subentry_id' in R
    assert 'config_subentry_id=subentry_id' in R
    assert '_remove_legacy_grouping_devices()' in R
    assert 'runtime.ensure_sensors_subentry()' in S
    assert 'runtime.ensure_sensors_subentry()' in B
    assert 'finalize_sensor_subentry_registry' not in R


def test_adapters_use_real_adapters_subentry():
    assert 'ANTPLUS_SUBENTRY_TYPE = "antplus_adapters"' in R
    assert 'BLUETOOTH_SUBENTRY_TYPE = "bluetooth_adapters"' in R
    assert '_migrate_adapter_devices_to_transport_subentries()' in R
