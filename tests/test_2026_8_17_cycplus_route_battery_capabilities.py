"""CYCPLUS alternate-route, battery and live-capability regression contracts."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
BLUETOOTH = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")
CYCPLUS = (FIT / "live" / "cycplus_m1.py").read_text(encoding="utf-8")
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
REMOTE = (FIT / "remote_gateway.py").read_text(encoding="utf-8")
JS = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")


def _load_function(source: str, name: str):
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<production>", "exec"), namespace)
    return namespace[name]


def test_sig_battery_parser_accepts_only_real_percentages():
    parse_battery = _load_function(BLUETOOTH, "_parse_battery")
    assert parse_battery(b"\x00") == {"battery": 0.0}
    assert parse_battery(b"\x64") == {"battery": 100.0}
    assert parse_battery(b"\x65") == {}
    assert parse_battery(b"") == {}


def test_battery_is_read_from_gatt_and_browser_before_notifications():
    assert "read_gatt_char(CHAR_BATTERY_LEVEL)" in BLUETOOTH
    assert "await start(CHAR_BATTERY_LEVEL, _parse_battery, passive=True)" in BLUETOOTH
    assert 'CHAR_BATTERY_LEVEL: (set(), "battery")' in REMOTE
    assert "characteristic.readValue()" in JS
    assert "initialFrames.push" in JS
    assert "for (const frame of initialFrames)" in JS


def test_connected_characteristics_and_real_samples_expand_live_entities():
    assert "CHARACTERISTIC_CAPABILITIES" in BLUETOOTH
    assert "gatt_capabilities.update" in BLUETOOTH
    assert "capabilities=gatt_capabilities" in BLUETOOTH
    publish = RUNTIME.split("    def publish(", 1)[1].split(
        "    def live_values", 1
    )[0]
    assert "observed_capabilities" in publish
    assert "self.enrich_sensor_capabilities(" in publish


def test_fit_container_identity_never_replaces_bluetooth_device_identity():
    apply_attributes = CYCPLUS.split(
        "    def _apply_fit_device_attributes", 1
    )[1].split("    async def _async_sync", 1)[0]
    assert 'metadata["serial_number"]' not in apply_attributes
    assert 'metadata["hardware_revision"]' not in apply_attributes
    assert 'metadata["software_revision"]' not in apply_attributes
    assert "do not share the\n        # identity namespace" in apply_attributes
    assert '("serial_number", "fit_serial_number")' in apply_attributes
    assert "target.pop(metadata_key, None)" in apply_attributes


def test_exact_m1_route_merge_keeps_the_autonomous_local_endpoint():
    assert "fitness_physical_identity" in CYCPLUS
    assert "exact_physical_route_identity" in RUNTIME
    merge = RUNTIME.split("    def _merge_physical_sensors", 1)[1].split(
        "    def _collapse_provisional_discovery_flows_after_merge", 1
    )[0]
    assert "_browser_ble_endpoint(existing_endpoint)" in merge
    assert "not _browser_ble_endpoint(endpoint)" in merge
    assert "primary.endpoints[transport] = endpoint" in merge


def test_exact_m1_reconnect_absorbs_the_pre_route_identity_browser_record():
    lookup = RUNTIME.split(
        "    def find_sensor_for_remote_ble_identity", 1
    )[1].split("    def _match_sensor", 1)[0]
    assert "endpoint_id: str | None = None" in lookup
    assert "previous_route = self.sensors.get" in lookup
    assert "duplicates.append(previous_route)" in lookup
    assert "duplicate.sensor_id in self.sensors" in lookup
    assert "endpoint_id=endpoint_id" in REMOTE
