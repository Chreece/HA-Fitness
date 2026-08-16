"""Regression guards for live-only GATT fallback, protocol labels and VO2 zoom-out."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BT = (ROOT / "custom_components/fitness/live/bluetooth.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_idle_ble_never_opens_raw_telemetry_gatt():
    assert "_schedule_idle_connection" not in BT
    assert "_async_connect_idle" not in BT
    assert "BLE-only sensor therefore needs a GATT subscription even while Fitness" not in BT
    assert "self._schedule_identity_probe(sensor.sensor_id)" in BT
    assert "Probe identity on acceptance; never keep idle telemetry GATT open" in BT


def test_live_profile_is_the_only_owner_of_persistent_gatt_subscription():
    assert "async def async_connect_profile" in BT
    assert "Connect GATT only when runtime selected Bluetooth as fallback" in BT
    assert "self._profile_clients.setdefault(profile_id, set()).add(sensor_id)" in BT
    assert "if not self._profile_is_using_live_runtime(entry.entry_id):\n            return" in RUNTIME


def test_ant_fallback_health_uses_real_metric_production_not_identity_last_seen():
    block = RUNTIME.split("def ant_data_fresh", 1)[1].split("def bluetooth_gatt_supported", 1)[0]
    assert "sensor_metric_transport_seen" in block
    assert 'get("antplus")' in block
    assert "endpoint.last_seen" not in block
    assert "ANT_DATA_FRESH_SECONDS" in block


def test_gatt_capability_does_not_trust_advertisement_connectable_flag():
    block = RUNTIME.split("def bluetooth_gatt_supported", 1)[1].split("def bluetooth_gatt_capable", 1)[0]
    assert 'endpoint.metadata.get("connectable"' not in block
    assert "endpoint.address" in block


def test_discovery_protocol_list_uses_commas_not_plus_separator():
    block = RUNTIME.split("def protocol_label", 1)[1].split("def discovery_name", 1)[0]
    assert 'return ", ".join(transports)' in block
    assert '"antplus": "ANT+"' in block
    assert '"bluetooth": "BT"' in block


def test_vo2_zoom_out_can_expand_vertical_range_to_reveal_prediction():
    assert "this._vo2HistoryYExpand" in JS
    assert "Math.min(32, (this._vo2HistoryYExpand || 1) * 1.35)" in JS
    assert "baseHalfSpan * yExpand" in JS
    assert "zoomOutOneStep" in JS
    assert "zoomInOneStep" in JS
    assert "this._vo2HistoryYExpand = 1" in JS
