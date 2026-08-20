"""CYCPLUS M1 rotating-address discovery/duplicate-install regressions."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
CYCPLUS = (FIT / "device_adapters" / "cycplus_m1.py").read_text(encoding="utf-8")
ADAPTER = (FIT / "device_adapters" / "cycplus_adapter.py").read_text(encoding="utf-8")
ARCHIVES = (FIT / "device_archives.py").read_text(encoding="utf-8")
BLUETOOTH = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")


def test_every_m1_discovery_waits_for_verified_gatt_serial_identity():
    identity = CYCPLUS.split("def cycplus_m1_identity", 1)[1].split(
        "def cycplus_request", 1
    )[0]
    assert 'result["archive_discovery_identity_required"] = "cycplus_gatt_identity_verified"' in identity
    assert 'if not name_identity.get("fitness_physical_identity")' not in identity

    ready = RUNTIME.split("    def _sensor_discovery_ready", 1)[1].split(
        "    def _schedule_sensor_discovery", 1
    )[0]
    assert 'bluetooth.metadata.get("archive_discovery_identity_required")' in ready
    gate = "if required_identity and not bluetooth.metadata.get(required_identity)"
    assert gate in ready
    assert "return False" in ready
    # The adapter gate must win before generic product-family/serial readiness.
    assert ready.index(gate) < ready.index("catalog_product_id(sensor.name, sensor.endpoints)")
    assert ready.index(gate) < ready.index("serials = {")


def test_unaccepted_ambiguous_m1_gets_identity_probe_before_add_flow():
    discovered = BLUETOOTH.split("    def _async_discovered", 1)[1].split(
        "    def _archive_coordinator", 1
    )[0]
    marker = "self.device_archives.discovery_identity_probe_required"
    assert marker in discovered
    assert "self._schedule_identity_probe(sensor.sensor_id)" in discovered
    assert discovered.index(marker) < discovered.index("if not accepted:\n            return")


def test_gatt_serial_unlocks_discovery_and_adapter_canonicalizes_route():
    enrich = ADAPTER.split("def _enrich_connected_metadata", 1)[1].split(
        "ARCHIVE_ADAPTER =", 1
    )[0]
    assert "cycplus_m1_serial_identity" in enrich
    assert 'result["cycplus_gatt_identity_verified"] = True' in enrich
    assert 'result.pop("archive_discovery_identity_required", None)' in enrich

    gatt = BLUETOOTH.split("    async def _async_enrich_identity", 1)[1].split(
        "    async def _subscribe", 1
    )[0]
    assert "self.device_archives.canonicalize_connected_sensor(" in gatt

    registry = ARCHIVES.split("    def canonicalize_connected_sensor", 1)[1].split(
        "    def generic_identity_probe_allowed", 1
    )[0]
    assert 'getattr(coordinator, "canonicalize_connected_sensor", None)' in registry


def test_cycplus_adapter_collapses_exact_serial_and_stale_same_route_duplicates():
    canonicalize = CYCPLUS.split("    def canonicalize_connected_sensor", 1)[1].split(
        "    def _repair_persisted_duplicate_m1s", 1
    )[0]
    assert "candidate_serial == serial" in canonicalize
    assert "cycplus_m1_serial_identity(serial)" in canonicalize
    assert 'current.metadata.setdefault("fitness_physical_identity", physical)' in canonicalize
    assert "candidate_physical == physical" in canonicalize
    assert "not candidate.available" in canonicalize
    assert "self.runtime._merge_physical_sensors" in canonicalize
    assert 'canonical.endpoints["bluetooth"] = connected_endpoint' in canonicalize
    assert 'self.runtime.endpoint_aliases[connected_endpoint.endpoint_id]' in canonicalize
    assert '"cycplus_m1_gatt_serial"' in canonicalize
    # Do not regress to unsafe model/name-only merging.
    assert "candidate.name ==" not in canonicalize


def test_startup_repairs_old_duplicate_installs_only_with_archive_evidence():
    legacy = CYCPLUS.split("    def _legacy_archive_duplicate", 1)[1].split(
        "    def canonicalize_connected_sensor", 1
    )[0]
    assert 'a_attrs.get("device_number")' in legacy
    assert 'b_attrs.get("device_number")' in legacy
    assert "return bool(a_files & b_files)" in legacy

    migrate = CYCPLUS.split("    def _migrate_persisted_m1_route_identities", 1)[1].split(
        "    @staticmethod\n    def _sensor_gatt_serial", 1
    )[0]
    assert "self._repair_persisted_duplicate_m1s()" in migrate


def test_suffixed_m1_name_does_not_bypass_connected_identity_probe():
    identity = CYCPLUS.split("def cycplus_m1_identity", 1)[1].split(
        "def cycplus_request", 1
    )[0]
    # The advertisement may still expose a useful short physical token for
    # browser/local correlation, but that token must never unlock an HA Add flow.
    assert 'fitness_physical_identity=f"cycplus:m1:{number.lower()}"' in CYCPLUS
    assert 'archive_discovery_identity_required' in identity
    assert 'cycplus_gatt_identity_verified' in identity

    enrich = ADAPTER.split("def _enrich_connected_metadata", 1)[1].split(
        "ARCHIVE_ADAPTER =", 1
    )[0]
    assert 'result["cycplus_gatt_identity_verified"] = True' in enrich
    assert enrich.index('cycplus_m1_serial_identity') < enrich.index(
        'result["cycplus_gatt_identity_verified"] = True'
    )
