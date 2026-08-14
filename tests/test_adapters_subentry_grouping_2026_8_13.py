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


def test_transport_buttons_are_not_owned_by_adapter_or_sensor_subentries():
    # The adapter Activate switches own lifecycle. There are no capture or
    # manual GATT transport buttons to assign to either subentry.
    assert "AntReceiverStartCaptureButton" not in B
    assert "AntReceiverStopCaptureButton" not in B
    assert "SensorGattConnectButton" not in B
    assert "SensorGattDisconnectButton" not in B

def test_existing_adapter_devices_migrate_to_protocol_subentries():
    assert '_migrate_adapter_devices_to_transport_subentries()' in R
    assert 'new_config_subentry_id=subentry_id' in R
    assert 'fitness_antplus_adapters' in ANT
    assert 'antplus_adapters' in ANT
