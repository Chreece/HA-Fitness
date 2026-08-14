"""Unaccepted BLE discovery must become a zero-control-plane background object."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BT = (ROOT / "custom_components/fitness/live/bluetooth.py").read_text()


def _discovery_block() -> str:
    return BT.split("def _async_discovered", 1)[1].split(
        "def sensor_connected", 1
    )[0]


def test_provisional_ble_has_stable_identity_fast_path():
    block = _discovery_block()
    assert "_provisional_identity_signature" in block
    assert "known_sensor is not None and previous_identity == identity_signature" in block
    assert "previous_identity == identity_signature" in block
    assert "if not accepted:" in block


def test_recurring_unaccepted_advertisement_returns_before_runtime_registration():
    block = _discovery_block()
    guard = block.index("if known_sensor is not None and previous_identity == identity_signature")
    reject = block.index("if not accepted:", guard)
    ret = block.index("return", reject)
    register = block.index("self.runtime.register_transport_sensor(")
    assert guard < reject < ret < register


def test_unaccepted_fast_path_only_refreshes_volatile_memory():
    block = _discovery_block()
    guard = block.index("if known_sensor is not None and previous_identity == identity_signature")
    reject = block.index("if not accepted:", guard)
    ret = block.index("return", reject)
    fast = block[guard:ret]
    assert "self.runtime.refresh_transport_endpoint(" in fast
    assert "publish_details" not in fast
    assert "publish_passive" not in fast
    assert "decode_bluetooth_advertisement" not in fast
    assert "_schedule_save" not in fast


def test_unaccepted_ble_does_not_decode_dynamic_payloads():
    block = _discovery_block()
    reject = block.index("if not accepted:")
    passive = block.index("_passive_advertisement_values(info)")
    raw = block.index("raw_manufacturer =")
    assert reject < raw
    assert reject < passive


def test_identity_signature_excludes_rssi_and_payload_bytes():
    block = _discovery_block()
    sig = block.split("identity_signature = (", 1)[1].split(")", 1)[0]
    assert "rssi" not in sig
    assert "bytes(" not in sig
    assert "service_data" not in sig
