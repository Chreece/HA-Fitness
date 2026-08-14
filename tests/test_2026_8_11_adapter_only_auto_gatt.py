"""Adapter switches own transport lifecycle; Bluetooth GATT is automatic."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components/fitness"
RUNTIME = (FIT / "live/runtime.py").read_text(encoding="utf-8")
BT = (FIT / "live/bluetooth.py").read_text(encoding="utf-8")
ANT = (FIT / "live/antplus.py").read_text(encoding="utf-8")
BUTTON = (FIT / "button.py").read_text(encoding="utf-8")
BINARY = (FIT / "binary_sensor.py").read_text(encoding="utf-8")


def test_no_capture_or_manual_gatt_buttons_exist():
    for name in (
        "SensorTransportStartCaptureButton",
        "SensorTransportStopCaptureButton",
        "AntReceiverStartCaptureButton",
        "AntReceiverStopCaptureButton",
        "SensorGattConnectButton",
        "SensorGattDisconnectButton",
    ):
        assert name not in BUTTON


def test_no_capture_state_entity_is_materialized():
    assert "AdapterCapture" not in BINARY
    assert "AntReceiverCapture" not in BINARY
    assert "SensorTransportCaptureActive" not in BINARY


def test_workout_transport_claims_never_start_or_stop_provider_capture():
    claim = RUNTIME.split("async def _claim_transport", 1)[1].split(
        "async def _release_transport", 1
    )[0]
    release = RUNTIME.split("async def _release_transport", 1)[1].split(
        "async def _reconcile_profile_transports", 1
    )[0]
    assert "async_start_capture" not in claim
    assert "async_stop_capture" not in claim
    assert "async_start_capture" not in release
    assert "async_stop_capture" not in release


def test_setup_discovery_does_not_change_transport_state():
    block = RUNTIME.split("async def async_begin_setup_discovery", 1)[1].split(
        "@property\n    def live_enabled", 1
    )[0]
    assert "async_start_capture" not in block
    assert "async_stop_capture" not in block


def test_bluetooth_provider_has_no_capture_gate():
    assert "async def async_start_capture" not in BT
    assert "async def async_stop_capture" not in BT
    connect = BT.split("async def async_connect_profile", 1)[1].split(
        "async def _async_enrich_device_info", 1
    )[0]
    assert "capture_active" not in connect


def test_ant_provider_is_enabled_for_provider_lifetime():
    assert "async def async_start_capture" not in ANT
    assert "async def async_stop_capture" not in ANT
    assert "await self._async_restore_receiver_states()" in ANT
    setup = ANT.split("async def _async_create_adapter_manager", 1)[1].split("async def async_bind_hub", 1)[0]
    assert "await self._async_enable_receivers()" not in setup
    assert "await self._async_disable_receivers()" in ANT


def test_gatt_is_selected_only_when_ant_is_not_fresh():
    choose = RUNTIME.split("def choose_transport", 1)[1].split(
        "async def _claim_transport", 1
    )[0]
    ant_pos = choose.index("self.ant_data_fresh(sensor)")
    bt_pos = choose.index('return "bluetooth"')
    assert ant_pos < bt_pos
    assert 'return "antplus"' in choose


def test_runtime_automatically_connects_and_disconnects_gatt():
    reconcile = RUNTIME.split("async def _reconcile_profile_transports", 1)[1].split(
        "def _start_profile_handover_monitor", 1
    )[0]
    assert "await bt_provider.async_connect_profile(entry.entry_id, [sensor])" in reconcile
    assert "await disconnect_one(entry.entry_id, sensor.sensor_id)" in reconcile
    assert "SensorGattConnectButton" not in BUTTON


def test_fresh_ant_schedules_handover_off_gatt():
    publish = RUNTIME.split("def publish(", 1)[1].split("def live_values", 1)[0]
    assert 'if transport == "antplus" and self.bluetooth_gatt_connected(sensor_id):' in publish
    assert "self._schedule_sensor_claim_reconcile(sensor_id)" in publish


def test_old_capture_and_manual_gatt_entities_are_pruned():
    cleanup = RUNTIME.split("def _cleanup_obsolete_hub_capture_entities", 1)[1].split(
        "async def _async_start_hub_modules", 1
    )[0]
    for suffix in (
        "_bluetooth_start_capture",
        "_bluetooth_stop_capture",
        "_antplus_start_capture",
        "_antplus_stop_capture",
        "_gatt_connect",
        "_gatt_disconnect",
    ):
        assert suffix in cleanup
