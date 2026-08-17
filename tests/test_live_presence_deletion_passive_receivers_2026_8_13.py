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


def test_live_profile_surface_and_controls_are_stable_across_hardware_changes():
    assert "runtime.live_surface_available" in CONFIG
    assert "runtime.live_surface_available" not in SELECT
    assert "def ensure_profile_live_registry" in RUNTIME
    assert "cleanup_profile_live_registry" not in RUNTIME
    ensure = RUNTIME[
        RUNTIME.index("def ensure_profile_live_registry"):
        RUNTIME.index("def _start_presence_monitor")
    ]
    assert "async_get_or_create" in ensure
    assert "async_remove_device" not in ensure


def test_sensor_deletion_forgets_assignment_and_allows_rediscovery():
    assert "EVENT_DEVICE_REGISTRY_UPDATED" in RUNTIME
    assert "def forget_sensor" in RUNTIME
    assert "self._discovery_started.discard(sensor_id)" in RUNTIME
    assert "CONF_LIVE_SENSOR_IDS" in RUNTIME


def test_no_capture_controls_are_exposed_anywhere():
    assert "AntReceiverStartCaptureButton" not in BUTTON
    assert "AntReceiverStopCaptureButton" not in BUTTON
    assert "SensorGattConnectButton" not in BUTTON
    assert "SensorGattDisconnectButton" not in BUTTON

def test_passive_ble_values_use_vendor_registry_and_are_separate_from_gatt():
    assert "STRYD_MANUFACTURER_ID" not in BT
    assert "43690" not in BT
    assert "decode_bluetooth_advertisement" in BT
    assert "_parse_battery" in BT  # standard SIG Battery Service remains generic
    assert "CHAR_BATTERY_LEVEL" in BT
    assert "publish_passive" in BT
    assert "class PhysicalPassiveSensor" in SENSOR
    assert '"passive": True' in SENSOR
