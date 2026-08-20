"""Verified physical serials are a universal pre-discovery dedupe invariant."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
CYCPLUS_ADAPTER = (FIT / "device_adapters" / "cycplus_adapter.py").read_text(
    encoding="utf-8"
)


def test_runtime_serial_match_includes_canonical_sensor_metadata():
    block = RUNTIME.split("    def _match_sensor", 1)[1].split(
        "    @staticmethod", 1
    )[0]
    assert "serial in _sensor_serials(sensor)" in block
    helper = RUNTIME.split("def _sensor_serials", 1)[1].split(
        "def _sensor_verified_serials", 1
    )[0]
    assert "_serial(sensor.metadata)" in helper
    assert "_serial(endpoint.metadata)" in helper


def test_runtime_verified_serial_absorbs_endpointless_legacy_clones():
    block = RUNTIME.split("    def _match_sensor", 1)[1].split(
        "    @staticmethod", 1
    )[0]
    serial_block = block.split("serial = _serial(endpoint.metadata)", 1)[1].split(
        "family = catalog_product_id", 1
    )[0]
    assert "verified = _verified_serial(endpoint.metadata)" in serial_block
    assert "or not candidate.endpoints" in serial_block
    assert 'canonical.metadata["merge_evidence"] = "verified_serial_identity"' in serial_block
    assert "self._merge_physical_sensors(canonical, candidate)" in serial_block


def test_restart_absorbs_endpointless_same_serial_clones_before_materialization():
    register_hub = RUNTIME.split("    async def async_register_hub", 1)[1].split(
        "    def _start_presence_monitor", 1
    )[0]
    assert "self._consolidate_restored_verified_serials()" in register_hub
    assert register_hub.index("self._consolidate_restored_verified_serials()") < register_hub.index(
        "self.ensure_sensor_device(sensor_id)"
    )

    consolidate = RUNTIME.split(
        "    def _consolidate_restored_verified_serials", 1
    )[1].split("    def _consolidate_restored_exact_physical_identities", 1)[0]
    assert "witnesses" in consolidate
    assert "_sensor_verified_serials(sensor)" in consolidate
    assert "if duplicate.endpoints or serial not in _sensor_serials(duplicate)" in consolidate
    assert "_vendor_conflicts(canonical, duplicate.metadata)" in consolidate
    assert "self._merge_physical_sensors(canonical, duplicate)" in consolidate


def test_vendor_guard_treats_canonical_vendor_and_legal_manufacturer_as_alias_evidence():
    aliases = RUNTIME.split("def _vendor_identities", 1)[1].split(
        "def _vendor_identity", 1
    )[0]
    assert 'metadata.get("fitness_vendor_identity")' in aliases
    assert 'metadata.get("manufacturer")' in aliases

    conflict = RUNTIME.split("def _vendor_conflicts", 1)[1].split(
        "def _sensor_physical_identity", 1
    )[0]
    assert "incoming = _vendor_identities(metadata)" in conflict
    assert "current = _sensor_vendor_identities(sensor)" in conflict
    assert "incoming.isdisjoint(current)" in conflict
    assert "incoming != current" not in conflict


def test_cycplus_adapter_exports_verified_serial_into_universal_contract():
    enrich = CYCPLUS_ADAPTER.split("def _enrich_connected_metadata", 1)[1].split(
        "ARCHIVE_ADAPTER =", 1
    )[0]
    assert 'result["cycplus_gatt_identity_verified"] = True' in enrich
    assert 'result["fitness_serial_identity_verified"] = True' in enrich
