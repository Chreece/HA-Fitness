"""Accepted ANT sensors keep bounded raw telemetry while profiles stay idle."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIVER = (ROOT / "custom_components/fitness/live/antplus_core/receiver.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()


def _method_source(text: str, name: str) -> str:
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


def test_receiver_samples_accepted_idle_pages_before_structural_work():
    helper = _method_source(RECEIVER, "fast_ignore_idle_packet")
    assert "device_id in self._telemetry_enabled_devices" in helper
    assert "device_type not in self._known_profiles_snapshot" in helper
    assert "IDLE_ACCEPTED_PACKET_INTERVAL_SECONDS" in helper
    assert "key = (device_id, device_type, page)" in helper

    block = _method_source(RECEIVER, "process_packet")
    guard = block.index("fast_ignore_idle_packet")
    diagnostics = block.index('diagnostics.inc("receiver_packets_seen")')
    structural = block.index("new_device = False")
    main_lock = block.index("with self._lock:", structural)
    capability = block.index("record_observed_page(")
    decode = block.index("decode_packet(")
    assert guard < diagnostics < structural < main_lock < capability < decode


def test_receiver_tracks_acceptance_separately_from_full_rate_live_telemetry():
    init = _method_source(RECEIVER, "__init__")
    assert "self._accepted_devices: frozenset[int]" in init
    assert "self._idle_packet_last_admitted" in init
    accepted = _method_source(RECEIVER, "set_device_accepted")
    assert "current | {device_id} if accepted else current - {device_id}" in accepted
    forget = _method_source(RECEIVER, "forget_device")
    assert "self._accepted_devices = self._accepted_devices - {device_id}" in forget
    assert "self._idle_packet_last_admitted.pop" in forget


def test_ant_provider_keeps_receiver_acceptance_and_canonical_id_in_sync():
    refresh = _method_source(ANT, "refresh_telemetry_gates")
    assert "canonical_id = self.runtime.resolve_sensor_id(sensor_id)" in refresh
    assert "full-rate ANT decoding" in refresh
    publish = _method_source(ANT, "_publish_device")
    assert "canonical_id = self.runtime.resolve_sensor_id(mapped_sensor_id)" in publish
    assert "self.receiver.set_device_accepted(device_id, accepted)" in publish

    changed = _method_source(ANT, "sensor_acceptance_changed")
    assert "target_sensor_id = self.runtime.resolve_sensor_id(sensor_id)" in changed
    assert "canonical_id = self.runtime.resolve_sensor_id(mapped_sensor_id)" in changed


def test_stride_cadence_maps_to_canonical_physical_cadence():
    assert '"stride_cadence": METRIC_CADENCE' in ANT


def test_idle_raw_physical_updates_happen_before_profile_epoch_gate():
    method = _method_source(RUNTIME, "publish")
    physical_write = method.index("value_bucket = self.sensor_values.setdefault")
    physical_notify = method.index("self._notify_values_throttled(physical_dirty)")
    profile_gate = method.index("if not self._global_workout_epoch_active():")
    claim = method.index("owner = self._claim_sensor_for_workout(sensor_id)")
    assert physical_write < physical_notify < profile_gate < claim



def test_idle_accepted_sampling_is_page_aware_and_live_bypasses():
    method = _method_source(RECEIVER, "fast_ignore_idle_packet")

    class FakeTime:
        values = iter([10.0, 10.1, 10.1, 10.7])

        @classmethod
        def monotonic(cls):
            return next(cls.values)

    namespace: dict[str, object] = {
        "time": FakeTime,
        "IDLE_ACCEPTED_PACKET_INTERVAL_SECONDS": 0.5,
    }
    exec("class Dummy:\n" + "\n".join("    " + line for line in method.splitlines()), namespace)
    receiver = namespace["Dummy"]()
    receiver._accepted_devices = frozenset({4660})
    receiver._telemetry_enabled_devices = frozenset()
    receiver._known_profiles_snapshot = {4660: frozenset({124})}
    receiver._idle_packet_last_admitted = {}

    assert receiver.fast_ignore_idle_packet(4660, 124, 1) is False
    assert receiver.fast_ignore_idle_packet(4660, 124, 1) is True
    # Rotating page 2 must still pass immediately so cadence is not starved.
    assert receiver.fast_ignore_idle_packet(4660, 124, 2) is False
    assert receiver.fast_ignore_idle_packet(4660, 124, 1) is False

    receiver._telemetry_enabled_devices = frozenset({4660})
    assert receiver.fast_ignore_idle_packet(4660, 124, 1) is False
    assert receiver.fast_ignore_idle_packet(4660, 124, 1) is False


def test_unaccepted_or_new_ant_profile_is_never_sampled():
    method = _method_source(RECEIVER, "fast_ignore_idle_packet")
    namespace: dict[str, object] = {
        "time": type("FakeTime", (), {"monotonic": staticmethod(lambda: 1.0)}),
        "IDLE_ACCEPTED_PACKET_INTERVAL_SECONDS": 0.5,
    }
    exec("class Dummy:\n" + "\n".join("    " + line for line in method.splitlines()), namespace)
    receiver = namespace["Dummy"]()
    receiver._accepted_devices = frozenset()
    receiver._telemetry_enabled_devices = frozenset()
    receiver._known_profiles_snapshot = {4660: frozenset({124})}
    receiver._idle_packet_last_admitted = {}
    assert receiver.fast_ignore_idle_packet(4660, 124, 1) is False

    receiver._accepted_devices = frozenset({4660})
    assert receiver.fast_ignore_idle_packet(4660, 11, 1) is False

def test_merge_alias_resolution_is_transitive_and_path_compressed():
    method = _method_source(RUNTIME, "resolve_sensor_id")
    namespace: dict[str, object] = {}
    exec("class Dummy:\n" + "\n".join("    " + line for line in method.splitlines()), namespace)
    runtime = namespace["Dummy"]()
    runtime.endpoint_aliases = {
        "old-ant-id": "merged-id-1",
        "merged-id-1": "canonical-stryd-id",
    }
    assert runtime.resolve_sensor_id("old-ant-id") == "canonical-stryd-id"
    assert runtime.endpoint_aliases["old-ant-id"] == "canonical-stryd-id"
    assert runtime.endpoint_aliases["merged-id-1"] == "canonical-stryd-id"
