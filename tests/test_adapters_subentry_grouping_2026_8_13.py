from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
B = (ROOT / "custom_components/fitness/button.py").read_text()
BS = (ROOT / "custom_components/fitness/binary_sensor.py").read_text()
SW = (ROOT / "custom_components/fitness/switch.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus_core/adapter.py").read_text()


def test_protocol_specific_adapter_subentries_exist():
    assert 'ANTPLUS_SUBENTRY_TYPE = "antplus_adapters"' in R
    assert 'BLUETOOTH_SUBENTRY_TYPE = "bluetooth_adapters"' in R
    assert 'title = "ANT+"' in R
    assert 'title = "Bluetooth"' in R
    assert 'SENSORS_SUBENTRY_TYPE = "sensors"' in R


def test_adapter_and_sensor_entities_are_owned_by_correct_subentries():
    # ANT receiver hardware controls remain on the ANT+ adapter subentry.
    assert 'runtime.adapter_subentry_id("antplus")' in B
    # Bluetooth capture controls moved from the logical adapter onto each
    # accepted physical sensor, under the Sensors subentry.
    assert 'SensorTransportStartCaptureButton(runtime, sensor_id, transport)' in B
    assert 'SensorTransportStopCaptureButton(runtime, sensor_id, transport)' in B
    assert 'subentry = runtime.ensure_sensors_subentry()' in B
    assert 'runtime.adapter_subentry_id(transport)' in BS
    assert 'runtime.adapter_subentry_id("antplus")' in BS
    assert 'runtime.adapter_subentry_id(transport)' in SW


def test_existing_adapter_devices_migrate_to_protocol_subentries():
    assert '_migrate_adapter_devices_to_transport_subentries()' in R
    assert 'new_config_subentry_id=subentry_id' in R
    assert 'fitness_antplus_adapters' in ANT
    assert 'antplus_adapters' in ANT
