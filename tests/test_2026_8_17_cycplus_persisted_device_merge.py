"""CYCPLUS M1 persisted route/device-registry merge regressions."""
from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
CYCPLUS = (FIT / "live" / "cycplus_m1.py").read_text(encoding="utf-8")
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
BLUETOOTH = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")
REMOTE = (FIT / "remote_gateway.py").read_text(encoding="utf-8")


def _load_function(source: str, name: str):
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    namespace = {"re": re}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), "<production>", "exec"),
        namespace,
    )
    return namespace[name]


def test_m1_gatt_serial_recovers_the_advertised_device_number():
    serial_identity = _load_function(CYCPLUS, "cycplus_m1_serial_identity")
    assert serial_identity("M102PS1742738143F298C6") == {
        "cycplus_model_id": "M1",
        "cycplus_device_number": "98C6",
        "fitness_physical_identity": "cycplus:m1:98c6",
    }
    assert serial_identity("3489673987") is None
    assert serial_identity("OTHER1742738143F298C6") is None
    assert serial_identity("M102PS1742738143F29XYZ") is None


def test_plain_m1_browser_name_falls_back_to_verified_gatt_serial():
    registration = REMOTE.split(
        "    async def async_register_ble_device", 1
    )[1].split("    def disconnect_ble_device", 1)[0]
    assert 'not route_identity.get("fitness_physical_identity")' in registration
    assert "CYCPLUS_M1_SERVICE_UUID in services" in registration
    assert "cycplus_m1_serial_identity" in registration
    assert "route_identity.update(serial_identity)" in registration


def test_persisted_fit_identity_is_scrubbed_before_route_consolidation():
    setup = CYCPLUS.split("    async def async_setup", 1)[1].split(
        "    def _migrate_persisted_m1_route_identities", 1
    )[0]
    assert "self._apply_fit_device_attributes(raw_sensor_id, attributes)" in setup
    assert "self._migrate_persisted_m1_route_identities()" in setup
    assert setup.index("self._apply_fit_device_attributes") < setup.index(
        "self._migrate_persisted_m1_route_identities"
    )


def test_restart_restores_aliases_and_collapses_only_local_browser_pairs():
    assert 'stored.get("sensor_aliases")' in RUNTIME
    assert '"sensor_aliases": self._serialize_sensor_aliases()' in RUNTIME
    consolidation = RUNTIME.split(
        "    def _consolidate_restored_exact_physical_identities", 1
    )[1].split("    def _cleanup_persisted_sensor_alias_devices", 1)[0]
    assert "len(local) != 1 or not browser" in consolidation
    assert "_browser_ble_endpoint(endpoint)" in consolidation
    assert "self._merge_physical_sensors(canonical, duplicate)" in consolidation


def test_merged_device_gets_stable_identifier_and_old_registry_surface_is_removed():
    device_info = RUNTIME.split("    def sensor_device_info", 1)[1].split(
        "    def sensor_identity", 1
    )[0]
    assert 'f"physical_sensor:{physical_identity}"' in device_info
    assert 'sensor.metadata.get("merge_evidence")' in device_info
    cleanup = RUNTIME.split(
        "    def _cleanup_persisted_sensor_alias_devices", 1
    )[1].split("    def _select_merge_primary", 1)[0]
    assert "entity.device_id in obsolete_device_ids" in cleanup
    assert "entity_registry.async_remove" in cleanup
    assert "device_registry.async_remove_device" in cleanup


def test_garmin_archive_registry_from_the_supplied_baseline_is_preserved():
    assert "DeviceArchiveRegistry" in BLUETOOTH
    assert "self.device_archives = DeviceArchiveRegistry(self)" in BLUETOOTH
    assert "await self.device_archives.async_setup()" in BLUETOOTH
    assert "await self.device_archives.async_shutdown()" in BLUETOOTH
