"""Regression guards for protocol-labelled discovery and fresh BLE rediscovery."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
BT = (ROOT / "custom_components/fitness/live/bluetooth.py").read_text()
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text()


def test_discovery_titles_name_the_observed_protocols():
    assert '"antplus": "ANT+"' in RUNTIME
    assert '"bluetooth": "BT"' in RUNTIME
    assert 'def discovery_name(self) -> str:' in RUNTIME
    assert 'return f"{self.name} ({self.protocol_label()})"' in RUNTIME
    assert 'sensor.discovery_name()' in FLOW


def test_deleting_ble_sensor_clears_provider_discovery_and_reconnect_state():
    assert 'def forget_sensor(self, sensor_id: str, endpoint_id: str | None = None)' in BT
    for token in (
        '_last_discovery_fingerprint.pop(endpoint_id, None)',
        '_provisional_identity_signature.pop(endpoint_id, None)',
        '_provisional_passive_last_decode.pop(endpoint_id, None)',
        '_identity_probe_last_attempt.pop(canonical, None)',
        'self._schedule_unowned_disconnect(canonical)',
    ):
        assert token in BT
    assert 'forget(sensor_id, endpoint.endpoint_id)' in RUNTIME


def test_delete_keeps_short_transport_quarantine_only():
    assert 'quarantine_until = time.monotonic() + 5.0' in RUNTIME
