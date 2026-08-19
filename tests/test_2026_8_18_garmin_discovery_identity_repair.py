"""Regression contracts for Garmin discovery, compatibility and stale identity repair."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
BT = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
ARCHIVES = (FIT / "device_archives.py").read_text(encoding="utf-8")
COORD = (FIT / "device_adapters" / "garmin" / "coordinator.py").read_text(encoding="utf-8")
GARMIN_ADAPTER = (FIT / "device_adapters" / "garmin" / "adapter.py").read_text(encoding="utf-8")
PROTO = (FIT / "device_adapters" / "garmin" / "protocol.py").read_text(encoding="utf-8")
SMART = (FIT / "smart_workout_devices.py").read_text(encoding="utf-8")
FLOW = (FIT / "config_flow.py").read_text(encoding="utf-8")
BUTTON = (FIT / "button.py").read_text(encoding="utf-8")
CATALOG = json.loads((FIT / "live" / "device_catalog.json").read_text(encoding="utf-8"))
IDENTITY = (FIT / "live" / "device_identity.py").read_text(encoding="utf-8")


def _method(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(name)


def test_garmin_advertisement_is_only_a_candidate_until_gatt_is_verified():
    matcher = _method(ARCHIVES, "match_bluetooth")
    assert "adapter.match_bluetooth" in matcher
    assert "advertisement_capabilities" in matcher
    assert "advertisement_capabilities=frozenset()" in GARMIN_ADAPTER
    assert "CAPABILITY_WORKOUT_HISTORY" not in GARMIN_ADAPTER
    assert '"archive_compatible": None' in PROTO
    assert '"fitness_vendor_identity": "garmin"' in PROTO

    sync = _method(COORD, "_async_sync")
    assert "CAPABILITY_WORKOUT_HISTORY" not in sync
    assert 'compatible=True' in sync
    assert 'compatible=False' in sync
    assert 'last_error_code="unsupported_transport"' in sync
    # A definitively incompatible device is not placed on another periodic
    # Bluetooth retry timer. It remains hidden until explicit rediscovery/reset.
    unsupported = sync.split("except GarminUnsupportedTransport", 1)[1].split("except Exception", 1)[0]
    assert "_schedule_after_current" not in unsupported
    assert "next_attempt=None" in unsupported


def test_smart_workout_choices_hide_verified_incompatible_devices():
    assert "def is_smart_workout_candidate" in SMART
    candidate = _method(SMART, "is_smart_workout_candidate")
    assert 'metadata.get("archive_compatible") is not False' in candidate
    assert "return False" in candidate
    assert 'return "conflict"' in _method(SMART, "smart_workout_vendor")

    choices = _method(FLOW, "_smart_workout_choices")
    assert "is_smart_workout_candidate" in choices
    guide = _method(FLOW, "async_step_smart_workout_vendor_guide")
    assert "smart_workout_archive_compatibility(sensor) is not False" in guide


def test_deleted_bluetooth_device_gets_one_post_quarantine_rediscovery():
    forget = _method(BT, "forget_sensor")
    assert "async_clear_address_from_match_history" in forget
    assert "async_rediscover_address" in forget
    assert "call_later(5.5" in forget
    assert "_rediscovery_handles" in forget
    # No generic/private scan loop is introduced for deletion recovery.
    assert "BleakScanner" not in BT
    assert "while True" not in forget


def test_vendor_conflict_is_resolved_before_known_endpoint_fast_path():
    register = _method(RUNTIME, "register_transport_sensor")
    conflict = register.index("_vendor_conflicts(known_sensor, metadata)")
    fast_path = register.index("# Fast path for recurring advertisements")
    # The check lives inside the fast-path section and before the cheap return.
    assert conflict > fast_path
    assert conflict < register.index("self.refresh_transport_endpoint(")
    assert "detach_conflicting_endpoint_alias" in register

    detach = _method(RUNTIME, "detach_conflicting_endpoint_alias")
    assert "sensor.endpoints.pop(transport, None)" in detach
    assert "self.endpoint_aliases.pop(endpoint_id, None)" in detach
    assert "self.ensure_sensor_device(sensor_id)" in detach
    assert "remove_unaccepted_sensor_device" in detach


def test_a_stale_endpoint_derived_sensor_id_cannot_overwrite_other_vendor():
    """Mirror the audit corruption: Garmin MAC occupied by a CYCPLUS sensor ID."""
    # The audit's corrupt sensor ID was exactly sha1("bluetooth:<Garmin MAC>")[:16].
    endpoint = "bluetooth:E0:48:24:67:85:64"
    assert hashlib.sha1(endpoint.encode()).hexdigest()[:16] == "8872091f19c9250a"

    allocator = _method(RUNTIME, "_new_physical_id")
    assert "existing = self.sensors.get(base)" in allocator
    assert "vendor != existing_vendor" in allocator
    assert 'f"{endpoint_id}\\0{vendor}\\0physical"' in allocator
    assert "live_sensor_identity_collision" in allocator
    register = _method(RUNTIME, "register_transport_sensor")
    assert "self._new_physical_id(endpoint_id, metadata)" in register



def test_device_registry_connections_are_replaced_not_only_merged():
    ensure = _method(RUNTIME, "ensure_sensor_device")
    assert "new_identifiers=set(info[\"identifiers\"])" in ensure
    assert "new_connections=set(info.get(\"connections\") or set())" in ensure
    assert ensure.index("new_connections=") < ensure.index("registry.async_get_or_create")


def test_conflict_cleanup_removes_wrong_garmin_state_from_other_physical_device():
    repair = _method(ARCHIVES, "identity_conflict_repaired")
    assert "self.forget_sensor(sensor_id)" in repair
    assert 'getattr(coordinator, "identity_conflict_repaired", None)' in repair
    adapter_repair = _method(COORD, "identity_conflict_repaired")
    assert 'clear_sensor_details_prefix(sensor_id, "garmin_")' in adapter_repair
    assert 'fitness_{sensor_id}_garmin_sync_workouts' in adapter_repair
    assert "registry.async_remove(entity_id)" in adapter_repair

    archive_button = BUTTON.split("class DeviceDataSyncButton", 1)[1].split("class BaseLiveFitnessButton", 1)[0]
    # The manual retry must be available before workout_history is verified;
    # Garmin grants that capability only after the handshake this button retries.
    assert "CAPABILITY_WORKOUT_HISTORY" not in archive_button
    assert 'endpoint.metadata.get("archive_compatible") is not False' in archive_button
    assert "sensor_is_accepted" in archive_button
    assert "sensor_assigned_profile_ids" in archive_button
    assert "coordinator_for_metadata" in archive_button



def test_archive_button_repairs_only_cross_sensor_generated_entity_ids():
    repair = _method(BUTTON, "_repair_cross_sensor_archive_button_entity_id")
    assert "other_slugs" in repair
    assert "runtime.sensors.values()" in repair
    assert "async_update_entity" in repair
    assert "new_entity_id=desired" in repair
    assert "unique_suffix" in repair
    # Generic platform must not know any physical product/vendor name.
    lower = BUTTON.lower()
    for token in ("garmin", "cycplus", "forerunner"):
        assert token not in lower

def test_garmin_cross_transport_correlation_uses_vendor_protocol_evidence_not_models():
    text = json.dumps(CATALOG, ensure_ascii=False).lower()
    # Garmin company ID is 0x0087 = 135. Runtime/catalog correlation is based on
    # protocol/vendor evidence, not consumer model-family names.
    garmin_rules = [
        rule
        for rule in CATALOG.get("transport_correlation_rules", []) + CATALOG.get("cross_transport_identity_rules", [])
        if "garmin" in json.dumps(rule).lower()
    ]
    assert garmin_rules
    assert any("135" in json.dumps(rule) for rule in garmin_rules)
    for forbidden in ("forerunner", "fenix", "fēnix", "venu", "vivoactive", "instinct"):
        assert forbidden not in text
    assert "manufacturer_data_id" in (FIT / "live" / "device_identity.py").read_text(encoding="utf-8")


def test_hot_bluetooth_router_stays_vendor_neutral_after_repair_logic():
    assert "garmin" not in BT.lower()
    assert "forerunner" not in BT.lower()
    assert "DeviceArchiveRegistry" in BT
    # Repairs add no private active scanner or new recurring background loop.
    assert "BleakScanner" not in BT


def test_tombstoned_stale_catalog_name_is_rebased_from_strong_endpoint_vendor():
    repair = _method(RUNTIME, "_rebase_tombstoned_single_route_identity")
    assert "sensor.sensor_id not in self._requires_reassignment" in repair
    assert "len(sensor.endpoints) != 1" in repair
    assert "catalog_name_vendor(sensor.name)" in repair
    assert "incoming_vendor == stale_name_vendor" in repair
    assert 'sensor.metadata.pop("discovery_confirmed", None)' in repair
    assert "sensor.capabilities.clear()" in repair
    assert 'sensor.metadata["identity_reclassified"]' in repair

    register = _method(RUNTIME, "register_transport_sensor")
    assert "reclassified_tombstone" in register
    assert "remove_unaccepted_sensor_device" in register
    assert "_refresh_provisional_discovery_flow" in register
    # The repair must preserve the tombstone; only explicit Add may assign it.
    assert "_requires_reassignment.discard" not in repair


def test_name_only_catalog_match_cannot_override_strong_other_vendor_endpoint():
    catalog_product = _method(IDENTITY, "_catalog_product")
    assert "_explicit_endpoint_vendors(endpoints)" in catalog_product
    assert "product_vendor not in observed_vendors" in catalog_product
    assert "continue" in catalog_product
    name_vendor = _method(IDENTITY, "catalog_name_vendor")
    assert 'rule.get("name_prefix")' in name_vendor
    assert "len(vendors) == 1" in name_vendor


def test_restore_repairs_corrupt_cycplus_title_before_discovery_is_recreated():
    init = _method(RUNTIME, "async_initialize")
    repair_call = init.index("_rebase_tombstoned_single_route_identity")
    resolve_call = init.index("identity = resolve_identity(sensor)")
    assert repair_call < resolve_call
    assert "sanitized_topology = True" in init[repair_call:resolve_call]


def test_first_fresh_packet_after_restart_reopens_reassignment_even_on_fast_path():
    register = _method(RUNTIME, "register_transport_sensor")
    refresh_pos = register.index("self.refresh_transport_endpoint(")
    return_pos = register.index("return known_sensor", refresh_pos)
    window = register[refresh_pos:return_pos]
    assert "known_sensor.sensor_id in self._requires_reassignment" in window
    assert "self._schedule_sensor_discovery(known_sensor.sensor_id)" in window
