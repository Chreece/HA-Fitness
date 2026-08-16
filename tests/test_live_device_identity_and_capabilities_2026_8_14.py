"""Regression guards for merged ANT+/BLE physical sensor identity and surfaces."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "custom_components/fitness/live"


def _load_identity():
    spec = importlib.util.spec_from_file_location("fitness_device_identity_test", LIVE / "device_identity.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _sensor(name="Fitness sensor", metadata=None, endpoints=None):
    return SimpleNamespace(name=name, metadata=metadata or {}, endpoints=endpoints or {})


def _endpoint(metadata):
    return SimpleNamespace(metadata=metadata)


def test_numeric_ant_model_is_never_user_facing_model():
    identity = _load_identity()
    sensor = _sensor(
        endpoints={"antplus": _endpoint({"manufacturer_id": 1, "model_no": 123, "profiles": [11]})}
    )
    result = identity.resolve_identity(sensor)
    assert result["manufacturer"] == "Garmin"
    assert result["model"] == "Power Meter"
    assert result["name"] == "Garmin Power Meter"
    assert result.get("model_id") in (None, "123")
    assert result["model"] != "123"
    assert result["name"] != "Garmin 123"


def test_stryd_merges_ant_and_ble_to_pretty_identity():
    identity = _load_identity()
    sensor = _sensor(
        name="StrydX",
        endpoints={
            "antplus": _endpoint({"manufacturer_id": 95, "model_no": 7, "profiles": [11, 124]}),
            "bluetooth": _endpoint({"manufacturer_data_ids": [43690], "advertised_name": "StrydX"}),
        },
    )
    result = identity.resolve_identity(sensor)
    assert result["manufacturer"] == "Stryd"
    assert result["model"] == "Stryd (non-wind model)"
    assert result["name"] == "Stryd (non-wind model)"
    assert result["ready"] is True


def test_gatt_device_information_wins_and_keeps_versions():
    identity = _load_identity()
    sensor = _sensor(
        endpoints={
            "antplus": _endpoint({"manufacturer_id": 1, "profiles": [120], "serial_no": 42}),
            "bluetooth": _endpoint({
                "identity_source": "gatt_device_information",
                "manufacturer": "Example",
                "model": "Chest Strap Pro",
                "serial_number": "ABC123",
                "hardware_revision": "2.1",
                "software_revision": "5.4",
            }),
        }
    )
    result = identity.resolve_identity(sensor)
    assert result["manufacturer"] == "Example"
    assert result["model"] == "Chest Strap Pro"
    assert result["serial_number"] == "ABC123"
    assert result["hw_version"] == "2.1"
    assert result["sw_version"] == "5.4"


def test_catalog_is_data_driven_and_expandable():
    catalog = json.loads((LIVE / "device_catalog.json").read_text(encoding="utf-8"))
    assert catalog["version"] >= 1
    assert isinstance(catalog["manufacturers"], dict)
    assert isinstance(catalog["products"], list)
    assert isinstance(catalog["profile_models"], dict)
    runtime = (LIVE / "runtime.py").read_text(encoding="utf-8")
    assert 'manufacturer_id == 95' not in runtime
    assert '"Stryd"' not in runtime


def test_ant_exposes_all_decoded_noncore_metrics_and_capabilities():
    ant = (LIVE / "antplus.py").read_text(encoding="utf-8")
    assert "def _publish_extra_metrics" in ant
    assert "getattr(device, \"metrics\", {}).items()" in ant
    assert '"protocol_controls": {"antplus": sorted(snapshot.controls)}' in ant
    assert '"protocol_events": {"antplus": sorted(snapshot.events)}' in ant
    assert '"ant_supported_controls"' in ant
    assert '"ant_supported_events"' in ant
    assert '"hardware_rev"' in ant
    assert '"software_ver"' in ant
    assert '"transmission_types"' in ant


def test_battery_is_one_merged_passive_entity_across_ant_and_ble():
    ant = (LIVE / "antplus.py").read_text(encoding="utf-8")
    entities = (LIVE / "ha_entities.py").read_text(encoding="utf-8")
    assert '{"battery": details.pop("battery_level")}' in ant
    assert "sensor_passive_sources" in entities
    assert '"transport": next(iter(sources), None) if len(sources) == 1 else "merged"' in entities


def test_ble_keeps_advertisement_and_gatt_information_as_diagnostics():
    bt = (LIVE / "bluetooth.py").read_text(encoding="utf-8")
    for token in (
        "bluetooth_address", "bluetooth_advertised_name", "bluetooth_services",
        "bluetooth_manufacturer_data", "bluetooth_service_data",
        "bluetooth_gatt_services", "bluetooth_gatt_characteristics",
        "hardware_revision", "software_revision", "firmware_revision",
    ):
        assert token in bt
    assert '"enabled_default": False' in bt


def test_gatt_is_automatic_and_ant_preference_is_guarded():
    buttons = (ROOT / "custom_components/fitness/button.py").read_text(encoding="utf-8")
    runtime = (LIVE / "runtime.py").read_text(encoding="utf-8")
    bt = (LIVE / "bluetooth.py").read_text(encoding="utf-8")
    assert "SensorGattConnectButton" not in buttons
    assert "SensorGattDisconnectButton" not in buttons
    assert 'return "antplus"' in runtime
    assert 'return "bluetooth"' in runtime
    assert "async_connect_profile" in runtime
    assert "async_disconnect_sensor" in runtime
    assert "async_ble_device_from_address" in bt

def test_protocol_events_have_real_event_entities():
    init = (ROOT / "custom_components/fitness/__init__.py").read_text(encoding="utf-8")
    event = (ROOT / "custom_components/fitness/event.py").read_text(encoding="utf-8")
    assert '"event"' in init.split("HUB_PLATFORMS", 1)[1].split("\n", 1)[0]
    assert "class PhysicalProtocolEvent(EventEntity)" in event
    assert "add_sensor_event_listener" in event
    assert "_trigger_event" in event


def test_unknown_control_writes_are_not_guessed():
    # Capability discovery is complete, but command payloads must come from a
    # verified encoder/spec rather than an advertised writable characteristic.
    bt = (LIVE / "bluetooth.py").read_text(encoding="utf-8")
    assert '"ftms_control_point"' in bt
    assert "write_gatt_char(CHAR_FTMS_CONTROL_POINT" not in bt


def test_noncore_ant_telemetry_is_opt_in_and_rate_bounded():
    ant = (LIVE / "antplus.py").read_text(encoding="utf-8")
    assert '"enabled_default": False' in ant
    assert "_extra_telemetry_last_publish" in ant
    assert ">= 1.0" in ant
    assert "_extra_metric_cache" in ant


def test_rssi_is_available_without_high_frequency_state_churn():
    entities = (LIVE / "ha_entities.py").read_text(encoding="utf-8")
    assert "class PhysicalSignalStrengthSensor" in entities
    assert '_attr_entity_registry_enabled_default = False' in entities
    assert 'return ("last_seen", None)' in entities
    assert '"sampling": "5_minute_diagnostic_bucket"' in entities


def test_ble_control_point_requires_write_and_response_properties():
    bt = (LIVE / "bluetooth.py").read_text(encoding="utf-8")
    assert "control_writable" in bt
    assert "control_reports" in bt
    assert '{"write", "write-without-response"}' in bt
    assert '{"indicate", "notify"}' in bt
    assert "bluetooth_gatt_characteristic_properties" in bt


def test_pnp_id_is_decomposed_but_not_assumed_to_be_consumer_model_id():
    bt = (LIVE / "bluetooth.py").read_text(encoding="utf-8")
    assert "bluetooth_vendor_id_source" in bt
    assert "bluetooth_vendor_id" in bt
    assert "bluetooth_product_id" in bt
    assert "bluetooth_product_version" in bt
    assert 'metadata.setdefault("model_id", f"0x{product_id:04X}")' not in bt
    assert "PnP product ID is *not* a" in bt


def test_automatic_gatt_is_dropped_when_ant_returns():
    runtime = (LIVE / "runtime.py").read_text(encoding="utf-8")
    assert "async_manual_gatt_connect" not in runtime
    assert "async_manual_gatt_disconnect" not in runtime
    assert 'if transport == "antplus" and self.bluetooth_gatt_connected(sensor_id):' in runtime
    assert "self._schedule_sensor_claim_reconcile(sensor_id)" in runtime

def test_each_detected_control_is_a_diagnostic_ha_entity():
    binary = (ROOT / "custom_components/fitness/binary_sensor.py").read_text(encoding="utf-8")
    assert "class PhysicalControlSupported" in binary
    assert "_sensor_control_capabilities" in binary
    assert '"actionable": False' in binary
    assert "verified protocol encoder" in binary


def test_gatt_connection_status_has_shared_owners():
    binary = (ROOT / "custom_components/fitness/binary_sensor.py").read_text(encoding="utf-8")
    assert "class BluetoothGattConnected" in binary
    assert '"owners": sorted(users(self.sensor_id))' in binary
