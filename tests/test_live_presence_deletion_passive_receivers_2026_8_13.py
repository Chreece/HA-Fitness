from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
RUNTIME = (FIT / "live" / "runtime.py").read_text()
BT = (FIT / "live" / "bluetooth.py").read_text()
BUTTON = (FIT / "button.py").read_text()
BINARY = (FIT / "binary_sensor.py").read_text()
SENSOR = (FIT / "live" / "ha_entities.py").read_text()
CONFIG = (FIT / "config_flow.py").read_text()
SELECT = (FIT / "select.py").read_text()


def test_hardware_presence_is_separate_from_module_enabled_state():
    assert "def adapter_present" in RUNTIME
    assert "def adapter_available" in RUNTIME
    assert "async_scanner_count" in RUNTIME
    assert "/sys/bus/usb/devices" in RUNTIME
    assert '"antplus_gateway_hello"' in RUNTIME
    assert '"antplus_gateway_status"' in RUNTIME
    assert "if self.live_available and self.hub_entry is None" in RUNTIME


def test_live_profile_surface_is_hardware_gated():
    assert "runtime.live_surface_available" in CONFIG
    assert "runtime.live_surface_available" in SELECT
    assert "cleanup_profile_live_registry" in RUNTIME


def test_sensor_deletion_forgets_assignment_and_allows_rediscovery():
    assert "EVENT_DEVICE_REGISTRY_UPDATED" in RUNTIME
    assert "def forget_sensor" in RUNTIME
    assert "self._discovery_started.discard(sensor_id)" in RUNTIME
    assert "CONF_LIVE_SENSOR_IDS" in RUNTIME


def test_capture_controls_are_receiver_and_physical_sensor_scoped():
    # Receiver-level ANT scan control remains a hardware control.
    assert "AntReceiverStartCaptureButton" in BUTTON
    assert "AntReceiverStopCaptureButton" in BUTTON
    assert "adapter_manager.async_set_capture(self.stable_key, True)" in BUTTON
    assert "adapter_manager.async_set_capture(self.stable_key, False)" in BUTTON
    assert "AntReceiverCapture" in BINARY
    # Per-sensor logical capture gates exist for whichever transports that
    # physical sensor actually has; Bluetooth no longer gets adapter buttons.
    assert "class SensorTransportStartCaptureButton" in BUTTON
    assert "class SensorTransportStopCaptureButton" in BUTTON
    assert 'SensorTransportStartCaptureButton(runtime, sensor_id, transport)' in BUTTON
    assert 'SensorTransportStopCaptureButton(runtime, sensor_id, transport)' in BUTTON
    assert 'AdapterStartCaptureButton(runtime, "bluetooth")' not in BUTTON
    assert 'AdapterStartCaptureButton(runtime, "antplus")' not in BUTTON


def test_passive_ble_values_use_vendor_registry_and_are_separate_from_gatt():
    assert "STRYD_MANUFACTURER_ID" not in BT
    assert "43690" not in BT
    assert "decode_bluetooth_advertisement" in BT
    assert 'values["battery"]' in BT  # standard SIG Battery Service remains generic
    assert "publish_passive" in BT
    assert "class PhysicalPassiveSensor" in SENSOR
    assert '"passive": True' in SENSOR
