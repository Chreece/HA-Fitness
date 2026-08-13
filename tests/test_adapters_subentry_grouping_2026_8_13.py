from pathlib import Path

ROOT = Path(__file__).parents[1]
R = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
B = (ROOT / "custom_components/fitness/button.py").read_text()
BS = (ROOT / "custom_components/fitness/binary_sensor.py").read_text()
SW = (ROOT / "custom_components/fitness/switch.py").read_text()

def test_real_adapters_and_sensors_subentries_exist_without_fake_hub_device():
    assert 'ADAPTERS_SUBENTRY_TYPE = "adapters"' in R
    assert 'SENSORS_SUBENTRY_TYPE = "sensors"' in R
    assert 'title="Adapters"' in R
    assert 'title="Sensors"' in R
    assert 'def ensure_hub_device' not in R
    assert '_remove_legacy_grouping_devices' in R

def test_adapter_entities_are_owned_by_adapters_subentry():
    assert 'config_subentry_id=runtime.adapters_subentry_id' in B
    assert 'config_subentry_id=runtime.adapters_subentry_id' in BS
    assert 'config_subentry_id=runtime.adapters_subentry_id' in SW

def test_existing_adapter_devices_migrate_to_adapters_subentry():
    assert '_migrate_adapter_devices_to_subentry()' in R
    assert 'new_config_subentry_id=subentry_id' in R
    assert 'via_device_id=None' in R
