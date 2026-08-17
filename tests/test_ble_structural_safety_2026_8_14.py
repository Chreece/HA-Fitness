"""Regression guards for BLE advertisement/device-registry runtime safety."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "custom_components/fitness/live"
BT = (LIVE / "bluetooth.py").read_text(encoding="utf-8")
RUNTIME = (LIVE / "runtime.py").read_text(encoding="utf-8")


def _method_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(name)


def test_raw_ble_payloads_are_not_structural_endpoint_metadata():
    discovered = _method_source(BT, "_async_discovered")
    register_call = discovered.split("sensor = self.runtime.register_transport_sensor(", 1)[1].split(")\n", 1)[0]
    assert '"manufacturer_data":' not in register_call
    assert '"service_data":' not in register_call
    assert '"manufacturer_data_ids"' in register_call
    assert '"service_uuids"' in register_call


def test_raw_ble_diagnostics_are_changed_and_rate_limited():
    discovered = _method_source(BT, "_async_discovered")
    assert "RAW_DIAGNOSTIC_MIN_INTERVAL = 10.0" in BT
    assert "_raw_diag_last_value" in discovered
    assert "_raw_diag_last_publish" in discovered
    assert ">= RAW_DIAGNOSTIC_MIN_INTERVAL" in discovered
    assert '"bluetooth_manufacturer_data"' in discovered
    assert '"bluetooth_service_data"' in discovered
    # HA Bluetooth route/source is also volatile and shares the slow diagnostic path.
    assert '"bluetooth_source": bluetooth_source' in discovered


def test_scanner_count_is_not_polled_per_advertisement():
    discovered = _method_source(BT, "_async_discovered")
    assert "_refresh_available()" not in discovered
    assert "set_adapter_presence" not in discovered
    setup = _method_source(BT, "async_setup")
    assert "_refresh_available()" in setup


def test_structural_metadata_strips_volatile_fields_and_accumulates_ble_caps():
    method = _method_source(RUNTIME, "_stable_endpoint_metadata")
    for key in ('"manufacturer_data"', '"service_data"', '"rssi"', '"last_seen"', '"source"'):
        assert key in method
    assert 'for key in ("service_uuids", "manufacturer_data_ids")' in method
    assert "set(old.get(key) or []) | set(clean.get(key) or [])" in method
    assert 'clean["connectable"] = True' in method


def test_source_and_availability_do_not_count_as_topology_changes():
    register = _method_source(RUNTIME, "register_transport_sensor")
    structural = register.split("structural_change = (", 1)[1].split(")\n\n", 1)[0]
    assert "previous_endpoint.source" not in structural
    assert "previous_endpoint.available" not in structural
    assert "previous_endpoint.metadata" in structural
    fast = register.split("if (", 1)[1].split("endpoint_capabilities", 1)[0]
    assert "known_endpoint.source == source" not in fast
    assert "refresh_transport_endpoint(" in register
    refresh = _method_source(RUNTIME, "refresh_transport_endpoint")
    assert "endpoint.source = source" in refresh


def test_semantic_name_stops_advertisement_aliases_forcing_slow_path():
    register = _method_source(RUNTIME, "register_transport_sensor")
    assert "current_name_is_generic" in register
    assert "catalog_product_id(normalized_name" not in register
    assert "Advertisement/local names may alternate" in register


def test_device_registry_updates_are_signature_cached():
    ensure = _method_source(RUNTIME, "ensure_sensor_device")
    assert "_sensor_device_signatures" in RUNTIME
    assert "self._sensor_device_signatures.get(sensor_id) == signature" in ensure
    assert "and sensor_id in self._sensor_device_ids" in ensure
    assert "self._sensor_device_signatures[sensor_id] = signature" in ensure


def test_persisted_topology_drops_rssi_and_raw_ad_payloads():
    serialize = _method_source(RUNTIME, "_serialize_sensors")
    assert '"rssi": endpoint.rssi' not in serialize
    assert "_stable_endpoint_metadata" in serialize
    stable = _method_source(RUNTIME, "_stable_sensor_metadata")
    assert "transport_details" in stable
    initialize = _method_source(RUNTIME, "async_initialize")
    assert "sanitized_topology" in initialize
    assert "raw.get(\"rssi\") is not None" in initialize
    assert "self._schedule_save()" in initialize


def test_radio_driven_structure_materialization_is_coalesced():
    method = _method_source(RUNTIME, "_notify_structure_throttled")
    assert "_structure_notify_handle" in method
    assert "call_later(2.0" in method
    publish_details = _method_source(RUNTIME, "publish_details")
    assert "_notify_structure_throttled()" in publish_details
    register = _method_source(RUNTIME, "register_transport_sensor")
    assert "_notify_structure_throttled()" in register


def test_ble_stable_diagnostics_are_cached_and_raw_serialization_runs_only_on_slow_clock():
    discovered = _method_source(BT, "_async_discovered")
    assert "_stable_diag_last_value" in discovered
    assert "stable_signature" in discovered
    slow = discovered.split("last_raw_check", 1)[1]
    assert "if now_mono - last_raw_check >= RAW_DIAGNOSTIC_MIN_INTERVAL" in slow
    # Expensive hex/string conversion happens inside the slow branch.
    assert slow.index("raw_manufacturer = str(") > slow.index("if now_mono - last_raw_check")


def test_silent_endpoints_expire_without_topology_churn():
    expire = _method_source(RUNTIME, "_expire_stale_sensor_endpoints")
    assert "DISCOVERY_RECENT_SECONDS" in expire
    assert "endpoint.available = False" in expire
    assert 'dirty.add((sensor.sensor_id, "availability", None))' in expire
    assert "_notify_structure" not in expire
    assert "_schedule_save" not in expire
    assert 'transport == "bluetooth"' in expire
    assert "sensor_connected" in expire


def test_accept_flow_defers_device_and_entity_materialization():
    flow = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
    mark = _method_source(RUNTIME, "mark_sensor_accepted")
    assert "_notify_structure()" not in mark
    finalize = flow.split("async def _finalize_assignment()", 1)[1].split(
        'return self.async_abort(reason="live_sensor_assigned")', 1
    )[0]
    assert "await asyncio.sleep(0.5)" in finalize
    assert "runtime.finalize_sensor_acceptance(canonical_id)" in finalize
    assert "finalize_sensor_acceptance" in RUNTIME and "self._notify_structure_throttled()" in RUNTIME.split("def finalize_sensor_acceptance", 1)[1].split("def _schedule_sensor_device_refresh", 1)[0]


def test_bluetooth_callback_is_filtered_by_standard_fitness_services():
    setup = _method_source(BT, "async_setup")
    assert "for service_uuid in SERVICE_CAPABILITIES" in setup
    assert "service_uuid=service_uuid" in setup
    assert "replay=bluetooth.BluetoothCallbackReplay.DISABLED" in setup
    assert "BluetoothCallbackMatcher(connectable=False)" not in setup
    discovered = _method_source(BT, "_async_discovered")
    assert "_provisional_identity_signature" in discovered
    assert "_last_discovery_fingerprint" in discovered
    assert "previous_discovery[0] == discovery_fingerprint" in discovered
    assert "known_sensor is not None and previous_identity == identity_signature" in discovered
    assert "previous_identity == identity_signature" in discovered


def test_accepted_ble_sensor_uses_cheap_identity_path_and_rate_limited_passive_decode():
    discovered = _method_source(BT, "_async_discovered")
    cheap = discovered.split(
        "if known_sensor is not None and previous_identity == identity_signature:", 1
    )[1].split("else:", 1)[0]
    assert "sensor = known_sensor" in cheap
    assert "register_transport_sensor" not in cheap
    assert "refresh_transport_endpoint" in cheap
    assert "PASSIVE_DECODE_MIN_INTERVAL = 5.0" in BT
    assert "_provisional_passive_last_decode" in discovered
    assert "now_mono - last_passive_decode >= PASSIVE_DECODE_MIN_INTERVAL" in discovered


def test_bluetooth_presence_uses_advertisement_scanners_not_connectable_only():
    refresh = _method_source(BT, "_refresh_available")
    assert "scanner_count(self.hass, connectable=False)" in refresh
    assert "scanner_count(self.hass, connectable=True)" not in refresh


def test_long_protocol_diagnostics_do_not_exceed_ha_state_limit():
    entities = (LIVE / "ha_entities.py").read_text(encoding="utf-8")
    detail = entities.split("class PhysicalDetailSensor", 1)[1].split(
        "class PhysicalActiveTransportSensor", 1
    )[0]
    assert "len(rendered) > 255" in detail
    assert 'attributes["full_value"] = rendered' in detail
    assert 'return f"{len(rendered)} characters"' in detail


def test_active_transport_does_not_duplicate_full_gatt_protocol_metadata():
    entities = (LIVE / "ha_entities.py").read_text(encoding="utf-8")
    block = entities.split("class PhysicalActiveTransportSensor", 1)[1].split(
        "class PhysicalSignalStrengthSensor", 1
    )[0]
    assert '"capabilities": sorted(endpoint.capabilities)' in block
    assert "sensor_transport_details" not in block


def test_live_metric_entity_follows_physical_sensor_availability():
    entities = (LIVE / "ha_entities.py").read_text(encoding="utf-8")
    block = entities.split("class PhysicalMetricSensor", 1)[1].split(
        "class PhysicalPassiveSensor", 1
    )[0]
    assert 'self.sensor_id, "availability", None, self._update' in block
    assert "def available(self) -> bool" in block
    assert "sensor.available" in block


def test_active_transport_distinguishes_known_from_currently_available_transports():
    entities = (LIVE / "ha_entities.py").read_text(encoding="utf-8")
    block = entities.split("class PhysicalActiveTransportSensor", 1)[1].split(
        "class PhysicalSignalStrengthSensor", 1
    )[0]
    assert '"known_transports"' in block
    assert '"available_transports"' in block
    assert "sensor.endpoints[t].available" in block


def test_shared_gatt_connect_disconnect_is_serialized_per_sensor():
    bluetooth = (
        ROOT / "custom_components/fitness/live/bluetooth.py"
    ).read_text(encoding="utf-8")

    assert "self._connect_locks: dict[str, asyncio.Lock] = {}" in bluetooth
    assert "def _connect_lock(self, sensor_id: str) -> asyncio.Lock:" in bluetooth
    connect = bluetooth.split("async def async_connect_profile", 1)[1].split(
        "async def _async_enrich_identity", 1
    )[0]
    assert "async with lock:" in connect
    assert "existing = self._clients.get(sensor_id)" in connect
    assert connect.index("async with lock:") < connect.index("existing = self._clients.get(sensor_id)")

    disconnect = bluetooth.split("async def async_disconnect_sensor", 1)[1].split(
        "async def async_disconnect_profile", 1
    )[0]
    assert "async with lock:" in disconnect
    assert "await self._async_disconnect_client(" in disconnect
    assert "async with asyncio.timeout(BLE_DISCONNECT_TIMEOUT * 2)" in disconnect


def test_failed_gatt_connect_cleans_partial_owner_and_client_state():
    bluetooth = (
        ROOT / "custom_components/fitness/live/bluetooth.py"
    ).read_text(encoding="utf-8")
    connect = bluetooth.split("async def async_connect_profile", 1)[1].split(
        "async def _async_enrich_identity", 1
    )[0]
    assert "users.discard(profile_id)" in connect
    assert "self._clients.pop(current_id, None)" in connect
    assert "await self._async_disconnect_client(" in connect
    assert 'reason="failed live connection cleanup"' in connect


def test_normal_advertisement_does_not_even_resolve_device_registry_identity():
    runtime = (
        ROOT / "custom_components/fitness/live/runtime.py"
    ).read_text(encoding="utf-8")
    registration = runtime.split("def register_transport_sensor", 1)[1].split(
        "# Compatibility for older provider code/tests", 1
    )[0]
    # Normal advertisements return through the fast path; structural identity
    # changes only schedule a debounced control-plane DeviceInfo refresh.
    assert "self._schedule_sensor_device_refresh(sensor.sensor_id)" in registration
    assert "self.ensure_sensor_device(sensor.sensor_id)" not in registration

def test_enabled_availability_entity_does_not_duplicate_full_transport_metadata():
    binary = (
        ROOT / "custom_components/fitness/binary_sensor.py"
    ).read_text(encoding="utf-8")
    section = binary.split("class LiveSensorAvailable", 1)[1].split(
        "class BluetoothGattConnected", 1
    )[0]
    assert "sensor_transport_details" not in section
    assert '"known_transports"' in section
    assert "if endpoint.available" in section
