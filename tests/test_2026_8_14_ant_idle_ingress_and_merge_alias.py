"""Movement-woken configured ANT sensors must be free while Fitness is idle."""
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


def test_receiver_has_hard_accepted_idle_ingress_gate_before_structural_work():
    helper = _method_source(RECEIVER, "fast_ignore_idle_packet")
    assert "device_id in self._accepted_devices" in helper
    assert "device_id not in self._telemetry_enabled_devices" in helper
    assert "device_type in self._known_profiles_snapshot" in helper

    block = _method_source(RECEIVER, "process_packet")
    guard = block.index("fast_ignore_idle_packet")
    diagnostics = block.index('diagnostics.inc("receiver_packets_seen")')
    structural = block.index("new_device = False")
    main_lock = block.index("with self._lock:", structural)
    capability = block.index("record_observed_page(")
    decode = block.index("decode_packet(")
    assert guard < diagnostics < structural < main_lock < capability < decode


def test_receiver_tracks_acceptance_separately_from_live_telemetry():
    init = _method_source(RECEIVER, "__init__")
    assert "self._accepted_devices: frozenset[int]" in init
    accepted = _method_source(RECEIVER, "set_device_accepted")
    assert "current | {device_id} if accepted else current - {device_id}" in accepted
    forget = _method_source(RECEIVER, "forget_device")
    assert "self._accepted_devices = self._accepted_devices - {device_id}" in forget


def test_ant_provider_keeps_receiver_acceptance_and_canonical_id_in_sync():
    refresh = _method_source(ANT, "refresh_telemetry_gates")
    assert "canonical_id = self.runtime.resolve_sensor_id(sensor_id)" in refresh
    publish = _method_source(ANT, "_publish_device")
    assert "canonical_id = self.runtime.resolve_sensor_id(mapped_sensor_id)" in publish
    assert "self.receiver.set_device_accepted(device_id, accepted)" in publish

    changed = _method_source(ANT, "sensor_acceptance_changed")
    assert "target_sensor_id = self.runtime.resolve_sensor_id(sensor_id)" in changed
    assert "canonical_id = self.runtime.resolve_sensor_id(mapped_sensor_id)" in changed


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
