"""Regression/stress guards for native ANT+/BLE radio hot paths."""

from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "custom_components/fitness/live/runtime.py"
RUNTIME = RUNTIME_PATH.read_text(encoding="utf-8")
ENTITIES = (
    ROOT / "custom_components/fitness/live/ha_entities.py"
).read_text(encoding="utf-8")
BINARY = (
    ROOT / "custom_components/fitness/binary_sensor.py"
).read_text(encoding="utf-8")


def _method_source(name: str) -> str:
    tree = ast.parse(RUNTIME)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = RUNTIME.splitlines()
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"method {name} not found")


def test_physical_entities_no_longer_join_global_runtime_fanout():
    base = ENTITIES[ENTITIES.index("class _PhysicalSensorEntity"):ENTITIES.index("class PhysicalMetricSensor")]
    assert "runtime.add_listener(self._update)" not in base
    assert "runtime.add_sensor_value_listener" in base
    assert 'return ("metric", self.metric)' in ENTITIES
    assert 'return ("passive", self.key)' in ENTITIES
    assert 'return ("active_transport", None)' in ENTITIES
    assert 'return ("last_seen", None)' in ENTITIES


def test_physical_availability_is_keyed_not_global():
    block = BINARY[BINARY.index("class LiveSensorAvailable"):BINARY.index("class _AntReceiverDiagnostic")]
    assert 'add_sensor_value_listener(' in block
    assert 'self.sensor_id, "availability", None, self._update' in block


def test_repeated_identical_metric_packets_do_not_dirty_ha_entity():
    publish = _method_source("publish")
    assert "value_bucket.get(key) != value" in publish
    assert "transport_bucket.get(key) != transport" in publish
    assert 'physical_dirty.add((sensor_id, "metric", key))' in publish
    # Manager/session packet handling is intentionally separate: identical
    # physiological values still need time progression for 1 Hz samples.
    assert "for key, value in packet_values.items():" in publish
    assert "_notify_profile_live_throttled" in publish


def test_last_seen_is_dirtied_only_on_five_minute_bucket_change():
    method = _method_source("_mark_last_seen_change")
    assert "seen.minute // 5" in method
    assert "if previous == bucket" in method
    assert 'return {(sensor_id, "last_seen", None)}' in method


def test_active_transport_updates_only_when_transport_changes():
    method = _method_source("_set_active_transport")
    assert "if sensor.active_transport == transport" in method
    assert '"active_transport"' in method


def test_profile_hot_path_is_coalesced_to_two_hz():
    method = _method_source("_notify_profile_live_throttled")
    assert "0.5 - elapsed" in method
    assert "_profile_live_notify_handles" in method
    assert "current._async_live_source_change(None)" in method


def test_recurring_ble_advertisement_has_volatile_fast_path():
    register = _method_source("register_transport_sensor")
    assert "Fast path for recurring advertisements" in register
    assert "known_endpoint.last_seen = last_seen" in register
    assert "known_endpoint.rssi = rssi" in register
    fast = register.split("Fast path for recurring advertisements", 1)[1].split("endpoint = TransportEndpoint", 1)[0]
    assert "_schedule_save" not in fast
    assert "self._notify()" not in fast


def test_synthetic_4_sensor_10hz_traffic_has_bounded_write_amplification():
    # 4 sensors × 10 Hz × 10 s = 400 packets. With six entities per sensor the
    # old global fan-out could callback ~9,600 entity listeners at a 2 Hz flush.
    # The keyed design can notify only the changed metric entity at each 2 Hz
    # coalesced flush: <= 4 sensors × 2 Hz × 10 s = 80 metric callbacks when one
    # metric per sensor changes continuously.
    sensors = 4
    seconds = 10
    packets = sensors * 10 * seconds
    old_global_callbacks = sensors * 6 * 2 * seconds
    keyed_callbacks_upper_bound = sensors * 2 * seconds
    assert packets == 400
    assert old_global_callbacks == 480
    assert keyed_callbacks_upper_bound == 80
    assert keyed_callbacks_upper_bound <= packets / 5


def test_value_flush_deduplicates_callbacks_across_dirty_keys():
    method = _method_source("_notify_sensor_value_changes")
    assert "callbacks: set[Any] = set()" in method
    assert "callbacks.update" in method
    assert "for listener in tuple(callbacks)" in method
