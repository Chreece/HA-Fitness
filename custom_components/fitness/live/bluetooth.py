"""Bluetooth SIG fitness-sensor transport for Fitness."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..const import (
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
)
from .runtime import LiveSensor
from .vendor_registry import decode_bluetooth_advertisement, vendor_registry_issues

_LOGGER = logging.getLogger(__name__)

BASE = "0000{}-0000-1000-8000-00805f9b34fb"
SERVICE_HR = BASE.format("180d")
SERVICE_CYCLING_POWER = BASE.format("1818")
SERVICE_CSC = BASE.format("1816")
SERVICE_RSC = BASE.format("1814")
SERVICE_FTMS = BASE.format("1826")

CHAR_HR = BASE.format("2a37")
CHAR_CYCLING_POWER = BASE.format("2a63")
CHAR_CSC = BASE.format("2a5b")
CHAR_RSC = BASE.format("2a53")
CHAR_FTMS_TREADMILL = BASE.format("2acd")
CHAR_FTMS_CROSS_TRAINER = BASE.format("2ace")
CHAR_FTMS_ROWER = BASE.format("2ad1")
CHAR_FTMS_INDOOR_BIKE = BASE.format("2ad2")
CHAR_FTMS_CONTROL_POINT = BASE.format("2ad9")
CHAR_FTMS_FEATURE = BASE.format("2acc")

# Bluetooth Device Information Service (DIS) characteristics.
CHAR_SYSTEM_ID = BASE.format("2a23")
CHAR_MODEL_NUMBER = BASE.format("2a24")
CHAR_SERIAL_NUMBER = BASE.format("2a25")
CHAR_FIRMWARE_REVISION = BASE.format("2a26")
CHAR_HARDWARE_REVISION = BASE.format("2a27")
CHAR_SOFTWARE_REVISION = BASE.format("2a28")
CHAR_MANUFACTURER_NAME = BASE.format("2a29")
CHAR_PNP_ID = BASE.format("2a50")

SERVICE_CAPABILITIES = {
    SERVICE_HR: {METRIC_HEART_RATE},
    SERVICE_CYCLING_POWER: {METRIC_POWER, METRIC_CADENCE},
    SERVICE_CSC: {METRIC_CADENCE},
    SERVICE_RSC: {METRIC_SPEED, METRIC_CADENCE, METRIC_DISTANCE},
    SERVICE_FTMS: {
        METRIC_SPEED,
        METRIC_CADENCE,
        METRIC_POWER,
        METRIC_DISTANCE,
        METRIC_HEART_RATE,
    },
}

BATTERY_SERVICE = BASE.format("180f")
RAW_DIAGNOSTIC_MIN_INTERVAL = 10.0
PASSIVE_DECODE_MIN_INTERVAL = 5.0
DISCOVERY_DEDUPE_WINDOW = 0.5


def _passive_advertisement_values(info) -> tuple[dict[str, float], dict[str, dict]]:
    """Decode connectionless standard and catalog-selected proprietary values."""
    values: dict[str, float] = {}
    metadata: dict[str, dict] = {}

    # Bluetooth SIG standard Battery Service handling remains protocol-generic.
    service_data = getattr(info, "service_data", {}) or {}
    for key, payload in service_data.items():
        if str(key).lower() == BATTERY_SERVICE and payload:
            battery = int(bytes(payload)[0])
            if 0 <= battery <= 100:
                values["battery"] = float(battery)
                metadata["battery"] = {
                    "name": "Battery",
                    "unit": "%",
                    "device_class": "battery",
                    "state_class": "measurement",
                    "icon": "mdi:battery",
                    "passive": True,
                    "decoder": "bluetooth_sig_battery_service",
                }

    vendor_values, vendor_metadata = decode_bluetooth_advertisement(info)
    values.update(vendor_values)
    metadata.update(vendor_metadata)
    return values, metadata


@dataclass
class _RevolutionState:
    crank_revs: int | None = None
    crank_time: int | None = None


class BluetoothFitnessProvider:
    """Discover via HA Bluetooth and actively connect through HA/proxy routes."""

    transport = "bluetooth"

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self.hass = runtime.hass
        self.available = False
        self.last_error: str | None = None
        self._unsubs: list[object] = []
        self._last_discovery_fingerprint: dict[str, tuple[tuple[object, ...], float]] = {}
        self._clients: dict[str, BleakClient] = {}
        self._connect_locks: dict[str, asyncio.Lock] = {}
        self._profile_clients: dict[str, set[str]] = {}
        self._sensor_users: dict[str, set[str]] = {}
        self._revolution_state: dict[str, _RevolutionState] = {}
        self._raw_diag_last_publish: dict[str, float] = {}
        self._raw_diag_last_value: dict[str, tuple[str, str, str]] = {}
        self._stable_diag_last_value: dict[str, tuple[tuple[str, object], ...]] = {}
        # Unaccepted discovery devices are control-plane objects, not telemetry
        # consumers. Once their stable advertisement identity has been registered,
        # recurring advertisements only refresh volatile presence in runtime.
        self._provisional_identity_signature: dict[str, tuple[object, ...]] = {}
        self._provisional_passive_last_decode: dict[str, float] = {}
        self._identity_probe_tasks: dict[str, asyncio.Task] = {}
        self._identity_probe_last_attempt: dict[str, float] = {}

    async def async_setup(self) -> None:
        """Register one HA Bluetooth discovery callback; no private scanner."""
        from homeassistant.setup import async_setup_component

        for issue in vendor_registry_issues():
            _LOGGER.warning("Fitness vendor registry: %s", issue)

        if not await async_setup_component(self.hass, "bluetooth", {}):
            self.available = False
            self.last_error = "Home Assistant Bluetooth could not be initialized"
            return

        # Let Home Assistant's Bluetooth manager discard unrelated devices before
        # our callback runs. One registration per standard fitness service gives
        # us OR semantics without receiving every changing BLE advertisement in
        # the installation. Disable per-registration history replay because the
        # cache is replayed exactly once below after every matcher is installed.
        # `_async_discovered` also deduplicates multi-service hits from one packet.
        for service_uuid in SERVICE_CAPABILITIES:
            self._unsubs.append(
                bluetooth.async_register_callback(
                    self.hass,
                    self._async_discovered,
                    BluetoothCallbackMatcher(
                        service_uuid=service_uuid, connectable=False
                    ),
                    BluetoothScanningMode.PASSIVE,
                    replay=bluetooth.BluetoothCallbackReplay.DISABLED,
                )
            )
        self._refresh_available()
        self.runtime.set_adapter_presence("bluetooth", self.available)

        # Include already-cached advertisements, including ESPHome proxy paths.
        for info in bluetooth.async_discovered_service_info(self.hass, False):
            self._async_discovered(info, None)

    def _refresh_available(self) -> None:
        scanner_count = getattr(bluetooth, "async_scanner_count", None)
        if scanner_count is None:
            self.available = True
            return
        try:
            # Passive Fitness discovery only needs a scanner capable of receiving
            # advertisements. GATT connectivity is resolved separately at connect
            # time with async_ble_device_from_address(..., connectable=True).
            self.available = bool(scanner_count(self.hass, connectable=False))
        except TypeError:
            try:
                self.available = bool(scanner_count(self.hass))
            except Exception:
                self.available = True
        except Exception:
            self.available = False

    def _async_discovered(self, info, _change) -> None:
        """Consume one HA Bluetooth advertisement without discovery hot-loop work."""
        address = str(info.address).upper()
        manufacturer_data = getattr(info, "manufacturer_data", {}) or {}
        service_data = getattr(info, "service_data", {}) or {}
        uuids = {str(x).lower() for x in (info.service_uuids or [])}

        capabilities: set[str] = set()
        for service, caps in SERVICE_CAPABILITIES.items():
            if service in uuids:
                capabilities.update(caps)
        if not capabilities:
            return

        endpoint_id = f"bluetooth:{address}"
        now_mono = self.hass.loop.time()

        # One advertisement can match several service-specific callback
        # registrations.  Collapse those callbacks before any runtime registration,
        # vendor decoding or diagnostic publication. Include the volatile payload
        # so genuinely new advertisements still pass immediately.
        discovery_fingerprint = (
            str(info.name or ""),
            tuple(sorted(uuids)),
            tuple(sorted((int(key), bytes(value)) for key, value in manufacturer_data.items())),
            tuple(sorted((str(key).lower(), bytes(value)) for key, value in service_data.items())),
            str(getattr(info, "source", None) or ""),
            bool(getattr(info, "connectable", False)),
        )
        previous_discovery = self._last_discovery_fingerprint.get(endpoint_id)
        if (
            previous_discovery is not None
            and previous_discovery[0] == discovery_fingerprint
            and now_mono - previous_discovery[1] <= DISCOVERY_DEDUPE_WINDOW
        ):
            return
        self._last_discovery_fingerprint[endpoint_id] = (
            discovery_fingerprint,
            now_mono,
        )

        known_sensor_id = self.runtime.endpoint_aliases.get(endpoint_id)
        known_sensor = (
            self.runtime.sensors.get(self.runtime.resolve_sensor_id(known_sensor_id))
            if known_sensor_id
            else None
        )
        accepted = bool(
            known_sensor is not None
            and self.runtime.sensor_is_accepted(known_sensor.sensor_id)
        )

        # For a provisional discovery device, the advertisement payload itself is
        # not useful after stable identity has been registered. RSSI, service bytes,
        # manufacturer bytes and passive telemetry can change continuously. Feeding
        # those through vendor decoding/diagnostic publication before acceptance
        # gives an untouched discovery card a permanent background workload.
        identity_signature = (
            address,
            str(info.name or ""),
            tuple(sorted(uuids)),
            tuple(sorted(int(key) for key in manufacturer_data)),
            bool(getattr(info, "connectable", False)),
        )
        previous_identity = self._provisional_identity_signature.get(endpoint_id)

        if known_sensor is not None and previous_identity == identity_signature:
            self.runtime.refresh_transport_endpoint(
                known_sensor.sensor_id,
                self.transport,
                last_seen=datetime.now(timezone.utc),
                rssi=getattr(info, "rssi", None),
                source=getattr(info, "source", None),
                available=True,
            )
            if not accepted:
                # Recurring provisional advertisements stop here; only volatile
                # in-memory presence fields above are refreshed.
                return
            # Accepted sensors also stay on the cheap path when their stable
            # advertisement identity is unchanged.  They may continue below for
            # rate-limited passive values, but do not re-run merge/registry logic.
            sensor = known_sensor
        else:
            sensor = self.runtime.register_transport_sensor(
                transport=self.transport,
                endpoint_id=endpoint_id,
                name=info.name or info.address,
                capabilities=capabilities,
                address=info.address,
                source=getattr(info, "source", None),
                last_seen=datetime.now(timezone.utc),
                rssi=getattr(info, "rssi", None),
                available=True,
                metadata={
                    "advertised_name": info.name,
                    "service_uuids": sorted(uuids),
                    "connectable": bool(getattr(info, "connectable", False)),
                    "manufacturer_data_ids": sorted(int(x) for x in manufacturer_data),
                },
            )
            self._provisional_identity_signature[endpoint_id] = identity_signature
            accepted = self.runtime.sensor_is_accepted(sensor.sensor_id)

        endpoint = sensor.endpoints.get(self.transport)
        endpoint_meta = dict(endpoint.metadata) if endpoint is not None else {}
        stable_details = {
            "bluetooth_address": info.address,
            "bluetooth_advertised_name": endpoint_meta.get("advertised_name") or info.name or "",
            "bluetooth_services": ", ".join(endpoint_meta.get("service_uuids") or sorted(uuids)),
            "bluetooth_connectable": bool(endpoint_meta.get("connectable", False)),
            "bluetooth_manufacturer_data_ids": ", ".join(
                str(int(x)) for x in (
                    endpoint_meta.get("manufacturer_data_ids")
                    or sorted(manufacturer_data)
                )
            ),
        }
        detail_meta = {
            "bluetooth_address": {"name": "Bluetooth address", "icon": "mdi:bluetooth", "enabled_default": False, "entity_category": "diagnostic"},
            "bluetooth_advertised_name": {"name": "Bluetooth advertised name", "icon": "mdi:form-textbox", "enabled_default": False, "entity_category": "diagnostic"},
            "bluetooth_services": {"name": "Bluetooth services", "icon": "mdi:bluetooth-settings", "enabled_default": False, "entity_category": "diagnostic"},
            "bluetooth_connectable": {"name": "Bluetooth connectable", "icon": "mdi:bluetooth-connect", "enabled_default": False, "entity_category": "diagnostic"},
            "bluetooth_source": {"name": "Bluetooth source", "icon": "mdi:access-point", "enabled_default": False, "entity_category": "diagnostic"},
            "bluetooth_manufacturer_data_ids": {"name": "Bluetooth manufacturer data IDs", "icon": "mdi:identifier", "enabled_default": False, "entity_category": "diagnostic"},
            "bluetooth_manufacturer_data": {"name": "Bluetooth manufacturer data", "icon": "mdi:code-json", "enabled_default": False, "entity_category": "diagnostic"},
            "bluetooth_service_data": {"name": "Bluetooth service data", "icon": "mdi:code-json", "enabled_default": False, "entity_category": "diagnostic"},
        }
        stable_signature = tuple(sorted(stable_details.items()))
        if self._stable_diag_last_value.get(endpoint_id) != stable_signature:
            self._stable_diag_last_value[endpoint_id] = stable_signature
            self.runtime.publish_details(
                sensor.sensor_id,
                stable_details,
                transport="bluetooth_advertisement",
                priority=5,
                metadata=detail_meta,
            )

        # Raw changing payload diagnostics and proprietary passive decoders are
        # useful only after the user accepts the sensor. Before acceptance they
        # must not create a permanent telemetry workload behind a discovery card.
        if not accepted:
            return

        last_raw_check = self._raw_diag_last_publish.get(
            endpoint_id, -RAW_DIAGNOSTIC_MIN_INTERVAL
        )
        if now_mono - last_raw_check >= RAW_DIAGNOSTIC_MIN_INTERVAL:
            self._raw_diag_last_publish[endpoint_id] = now_mono
            raw_manufacturer = str({
                int(key): bytes(value).hex()
                for key, value in manufacturer_data.items()
            })
            raw_service = str({
                str(key).lower(): bytes(value).hex()
                for key, value in service_data.items()
            })
            bluetooth_source = str(getattr(info, "source", None) or "")
            raw_pair = (raw_manufacturer, raw_service, bluetooth_source)
            if self._raw_diag_last_value.get(endpoint_id) != raw_pair:
                self._raw_diag_last_value[endpoint_id] = raw_pair
                self.runtime.publish_details(
                    sensor.sensor_id,
                    {
                        "bluetooth_manufacturer_data": raw_manufacturer,
                        "bluetooth_service_data": raw_service,
                        "bluetooth_source": bluetooth_source,
                    },
                    transport="bluetooth_advertisement",
                    priority=5,
                    metadata=detail_meta,
                )

        last_passive_decode = self._provisional_passive_last_decode.get(
            endpoint_id, -PASSIVE_DECODE_MIN_INTERVAL
        )
        if now_mono - last_passive_decode >= PASSIVE_DECODE_MIN_INTERVAL:
            self._provisional_passive_last_decode[endpoint_id] = now_mono
            passive, passive_meta = _passive_advertisement_values(info)
            if passive:
                self.runtime.publish_passive(
                    sensor.sensor_id,
                    passive,
                    transport=self.transport,
                    metadata=passive_meta,
                )

    def sensor_acceptance_changed(self, sensor_id: str, accepted: bool) -> None:
        """Probe stable BLE Device Information once after a sensor is accepted."""
        if accepted:
            self._schedule_identity_probe(sensor_id)

    def schedule_identity_probe_candidates(self, capabilities: set[str]) -> None:
        """Probe accepted BLE-only sensors that could be the new ANT endpoint.

        This is invoked only for structural ANT discovery/identity changes.  It
        never merges by capability/name; the probe merely obtains stable DIS
        identity so Runtime's exact serial matcher can make a safe decision.
        """
        wanted = set(capabilities)
        for sensor in tuple(self.runtime.sensors.values()):
            sensor_id = self.runtime.resolve_sensor_id(sensor.sensor_id)
            current = self.runtime.sensors.get(sensor_id)
            if current is None or not self.runtime.sensor_is_accepted(sensor_id):
                continue
            endpoint = current.endpoints.get(self.transport)
            if endpoint is None or "antplus" in current.endpoints:
                continue
            if wanted and not (current.capabilities & wanted):
                continue
            self._schedule_identity_probe(sensor_id)

    def _schedule_identity_probe(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get(self.transport) if sensor is not None else None
        if sensor is None or endpoint is None or not endpoint.address:
            return
        if endpoint.metadata.get("identity_source") == "gatt_device_information":
            return
        # `BluetoothServiceInfoBleak.connectable` describes the scanner/path that
        # delivered an advertisement, not whether *any* Home Assistant Bluetooth
        # controller can connect to this address. A Forerunner may therefore be
        # observed by a passive/non-connectable proxy while a local adapter or a
        # different proxy has a connectable route. HA explicitly recommends
        # resolving a connectable BLEDevice for this decision.
        if bluetooth.async_ble_device_from_address(
            self.hass, endpoint.address, connectable=True
        ) is None:
            return
        existing = self._identity_probe_tasks.get(sensor_id)
        if existing is not None and not existing.done():
            return
        now = self.hass.loop.time()
        if now - self._identity_probe_last_attempt.get(sensor_id, -60.0) < 30.0:
            return
        self._identity_probe_last_attempt[sensor_id] = now

        async def _probe() -> None:
            try:
                await self._async_probe_identity(sensor_id)
            finally:
                self._identity_probe_tasks.pop(sensor_id, None)

        self._identity_probe_tasks[sensor_id] = self.hass.async_create_background_task(
            _probe(),
            f"fitness probe BLE identity {sensor_id}",
            eager_start=False,
        )

    async def _async_probe_identity(self, requested_sensor_id: str) -> None:
        """Read DIS metadata using a short-lived connection, then disconnect."""
        sensor_id = self.runtime.resolve_sensor_id(requested_sensor_id)
        lock = self._connect_lock(sensor_id)
        async with lock:
            sensor_id = self.runtime.resolve_sensor_id(sensor_id)
            sensor = self.runtime.sensors.get(sensor_id)
            endpoint = sensor.endpoints.get(self.transport) if sensor is not None else None
            if sensor is None or endpoint is None or not endpoint.address:
                return
            if endpoint.metadata.get("identity_source") == "gatt_device_information":
                return
            existing = self._clients.get(sensor_id)
            if existing is not None and existing.is_connected:
                return
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, endpoint.address, connectable=True
            )
            if ble_device is None:
                return
            client = None
            try:
                client = await establish_connection(
                    BleakClient,
                    device=ble_device,
                    name=sensor.name or endpoint.address,
                    max_attempts=2,
                )
                await self._async_enrich_identity(
                    sensor, endpoint, client, manage_client_state=False
                )
            except Exception as err:
                _LOGGER.debug(
                    "Bluetooth identity probe failed for %s: %s", sensor_id, err
                )
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass

    def sensor_connected(self, sensor_id: str) -> bool:
        client = self._clients.get(str(sensor_id))
        return bool(client is not None and client.is_connected)

    def sensor_users(self, sensor_id: str) -> set[str]:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        return set(self._sensor_users.get(sensor_id, set()))

    def _connect_lock(self, sensor_id: str) -> asyncio.Lock:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        return self._connect_locks.setdefault(sensor_id, asyncio.Lock())

    async def async_connect_profile(
        self, profile_id: str, sensors: list[LiveSensor]
    ) -> None:
        """Connect GATT only when runtime selected Bluetooth as fallback."""
        for requested_sensor in sensors:
            sensor_id = self.runtime.resolve_sensor_id(requested_sensor.sensor_id)
            lock = self._connect_lock(sensor_id)
            async with lock:
                # Re-resolve and re-check after acquiring the lock: another profile
                # may have completed the shared GATT connection while we waited.
                sensor_id = self.runtime.resolve_sensor_id(sensor_id)
                sensor = self.runtime.sensors.get(sensor_id, requested_sensor)
                endpoint = sensor.endpoints.get(self.transport)
                if endpoint is None or not endpoint.address:
                    continue

                existing = self._clients.get(sensor_id)
                if existing is not None and existing.is_connected:
                    self._profile_clients.setdefault(profile_id, set()).add(sensor_id)
                    self._sensor_users.setdefault(sensor_id, set()).add(profile_id)
                    continue

                # HA resolves the best connectable path. The BLEDevice can therefore
                # point at local Bluetooth or a compatible remote Bluetooth proxy.
                ble_device = bluetooth.async_ble_device_from_address(
                    self.hass, endpoint.address, connectable=True
                )
                if ble_device is None:
                    continue

                client = None
                try:
                    client = await establish_connection(
                        BleakClient,
                        device=ble_device,
                        name=sensor.name or endpoint.address,
                        max_attempts=4,
                    )
                    # Publish ownership only after the connection is established.
                    # This prevents a failed/racing connect from leaving phantom users.
                    self._clients[sensor_id] = client
                    self._profile_clients.setdefault(profile_id, set()).add(sensor_id)
                    self._sensor_users.setdefault(sensor_id, set()).add(profile_id)
                    sensor = await self._async_enrich_identity(sensor, endpoint, client)
                    new_id = self.runtime.resolve_sensor_id(sensor.sensor_id)
                    if new_id != sensor_id:
                        # Identity enrichment can merge the provisional BLE sensor into
                        # an existing ANT+ physical sensor. Keep both IDs serialized by
                        # the same lock so a second owner cannot race the hand-over.
                        self._connect_locks.setdefault(new_id, lock)
                        sensor_id = new_id
                    await self._subscribe(sensor, client)
                    self.runtime._notify_values_throttled({
                        (sensor.sensor_id, "gatt_connection", None)
                    })
                except Exception as err:
                    self.last_error = f"{sensor.name}: {err}"
                    _LOGGER.debug(
                        "Bluetooth fitness connect failed for %s: %s",
                        sensor.sensor_id,
                        err,
                    )
                    # If failure happened after the client was registered, clean the
                    # partial ownership/connection before another profile retries.
                    current_id = self.runtime.resolve_sensor_id(sensor.sensor_id)
                    self._profile_clients.get(profile_id, set()).discard(current_id)
                    users = self._sensor_users.get(current_id)
                    if users is not None:
                        users.discard(profile_id)
                        if not users:
                            self._sensor_users.pop(current_id, None)
                    if client is not None and self._clients.get(current_id) is client:
                        self._clients.pop(current_id, None)
                        try:
                            await client.disconnect()
                        except Exception:
                            pass

    async def _async_enrich_identity(
        self, sensor: LiveSensor, endpoint, client: BleakClient, *,
        manage_client_state: bool = True,
    ) -> LiveSensor:
        """Read standard DIS/GATT metadata and refine the canonical identity."""
        metadata = dict(endpoint.metadata)
        details: dict[str, object] = {}
        detail_meta: dict[str, dict] = {}
        identity_fields_found = False
        char_map = (
            (CHAR_MANUFACTURER_NAME, "manufacturer", "Manufacturer"),
            (CHAR_MODEL_NUMBER, "model", "Model"),
            (CHAR_SERIAL_NUMBER, "serial_number", "Serial number"),
            (CHAR_HARDWARE_REVISION, "hardware_revision", "Hardware revision"),
            (CHAR_SOFTWARE_REVISION, "software_revision", "Software revision"),
            (CHAR_FIRMWARE_REVISION, "firmware_revision", "Firmware revision"),
        )
        for uuid, key, label in char_map:
            try:
                raw = await client.read_gatt_char(uuid)
                value = bytes(raw).decode("utf-8", errors="ignore").strip("\x00 ")
            except Exception:
                continue
            if value:
                metadata[key] = value
                details[key] = value
                identity_fields_found = True
                detail_meta[key] = {
                    "name": label, "icon": "mdi:information-outline",
                    "enabled_default": False, "entity_category": "diagnostic",
                }
        for uuid, key, label in (
            (CHAR_SYSTEM_ID, "bluetooth_system_id", "Bluetooth system ID"),
            (CHAR_PNP_ID, "bluetooth_pnp_id", "Bluetooth PnP ID"),
        ):
            try:
                raw = bytes(await client.read_gatt_char(uuid))
            except Exception:
                continue
            if not raw:
                continue
            details[key] = raw.hex()
            metadata[key] = raw.hex()
            identity_fields_found = True
            detail_meta[key] = {
                "name": label, "icon": "mdi:identifier",
                "enabled_default": False, "entity_category": "diagnostic",
            }
            # Bluetooth SIG Device Information PnP ID is a stable 7-byte tuple:
            # vendor-ID source, vendor ID, product ID and product version. Keep
            # every field separately and use the product ID as HA model_id when
            # the device did not provide a stronger model identifier.
            if uuid == CHAR_PNP_ID and len(raw) >= 7:
                vendor_source = raw[0]
                vendor_id = int.from_bytes(raw[1:3], "little")
                product_id = int.from_bytes(raw[3:5], "little")
                product_version = int.from_bytes(raw[5:7], "little")
                pnp_values = {
                    "bluetooth_vendor_id_source": vendor_source,
                    "bluetooth_vendor_id": vendor_id,
                    "bluetooth_product_id": product_id,
                    "bluetooth_product_version": product_version,
                }
                details.update(pnp_values)
                metadata.update(pnp_values)
                metadata.setdefault("model_id", f"0x{product_id:04X}")
                for pnp_key in pnp_values:
                    detail_meta[pnp_key] = {
                        "name": pnp_key.replace("bluetooth_", "Bluetooth ").replace("_", " ").title(),
                        "icon": "mdi:identifier", "enabled_default": False,
                        "entity_category": "diagnostic",
                    }

        # Only mark identity enrichment complete if Device Information actually
        # yielded identity facts. Some HR peripherals accept a GATT connection
        # but expose only Heart Rate/Battery; marking those complete would prevent
        # a later retry if a different connectable route exposes DIS.
        if identity_fields_found:
            metadata["identity_source"] = "gatt_device_information"
        # Record actual discovered GATT surface after connection. This is useful
        # diagnostics and the basis for safe future control entities.
        try:
            service_uuids = sorted(str(service.uuid).lower() for service in client.services)
            characteristic_properties = {
                str(char.uuid).lower(): sorted(str(prop).lower() for prop in (getattr(char, "properties", []) or []))
                for service in client.services
                for char in service.characteristics
            }
            characteristic_uuids = sorted(characteristic_properties)
        except Exception:
            service_uuids, characteristic_uuids, characteristic_properties = [], [], {}
        if service_uuids:
            metadata["gatt_services"] = service_uuids
            details["bluetooth_gatt_services"] = ", ".join(service_uuids)
            detail_meta["bluetooth_gatt_services"] = {
                "name": "Bluetooth GATT services", "icon": "mdi:bluetooth-settings",
                "enabled_default": False, "entity_category": "diagnostic",
            }
        if characteristic_uuids:
            metadata["gatt_characteristics"] = characteristic_uuids
            details["bluetooth_gatt_characteristics"] = ", ".join(characteristic_uuids)
            detail_meta["bluetooth_gatt_characteristics"] = {
                "name": "Bluetooth GATT characteristics", "icon": "mdi:format-list-bulleted",
                "enabled_default": False, "entity_category": "diagnostic",
            }
        if characteristic_properties:
            metadata["gatt_characteristic_properties"] = characteristic_properties
            details["bluetooth_gatt_characteristic_properties"] = str(characteristic_properties)
            detail_meta["bluetooth_gatt_characteristic_properties"] = {
                "name": "Bluetooth GATT characteristic properties",
                "icon": "mdi:format-list-checks", "enabled_default": False,
                "entity_category": "diagnostic",
            }
        control_props = set(characteristic_properties.get(CHAR_FTMS_CONTROL_POINT, []))
        control_writable = bool(control_props & {"write", "write-without-response"})
        control_reports = bool(control_props & {"indicate", "notify"})
        if CHAR_FTMS_CONTROL_POINT in characteristic_uuids and control_writable and control_reports:
            metadata.setdefault("protocol_controls", {})["bluetooth"] = ["ftms_control_point"]
            details["bluetooth_supported_controls"] = "ftms_control_point"
            detail_meta["bluetooth_supported_controls"] = {
                "name": "Bluetooth supported controls",
                "icon": "mdi:gamepad-variant-outline",
                "enabled_default": False,
                "entity_category": "diagnostic",
            }
        refined_name = metadata.get("model") or sensor.name
        merged = self.runtime.register_transport_sensor(
            transport=self.transport, endpoint_id=endpoint.endpoint_id,
            name=str(refined_name), capabilities=set(endpoint.capabilities),
            address=endpoint.address, source=endpoint.source,
            last_seen=datetime.now(timezone.utc), rssi=endpoint.rssi,
            available=True, metadata=metadata,
        )
        if details:
            self.runtime.publish_details(
                merged.sensor_id, details, transport="bluetooth_gatt",
                metadata=detail_meta, priority=80,
            )
        self.runtime.ensure_sensor_device(merged.sensor_id)
        if merged.sensor_id != sensor.sensor_id and manage_client_state:
            old_id = sensor.sensor_id
            new_id = merged.sensor_id
            self._clients[new_id] = self._clients.pop(old_id, client)
            for profile_id, ids in self._profile_clients.items():
                if old_id in ids:
                    ids.discard(old_id); ids.add(new_id)
            users = self._sensor_users.pop(old_id, set())
            if users:
                self._sensor_users.setdefault(new_id, set()).update(users)
            state = self._revolution_state.pop(old_id, None)
            if state is not None:
                self._revolution_state[new_id] = state
            old_lock = self._connect_locks.get(old_id)
            if old_lock is not None:
                self._connect_locks.setdefault(new_id, old_lock)
        return merged

    async def _subscribe(self, sensor: LiveSensor, client: BleakClient) -> None:
        def notify(parser):
            def _callback(_char, data):
                try:
                    values = parser(bytes(data))
                except Exception:
                    _LOGGER.debug(
                        "Bluetooth fitness parser failed for %s",
                        sensor.sensor_id,
                        exc_info=True,
                    )
                    return
                if values:
                    self.runtime.publish(sensor.sensor_id, values, transport=self.transport)
            return _callback

        async def start(uuid: str, parser) -> None:
            try:
                await client.start_notify(uuid, notify(parser))
            except Exception:
                # A service may advertise a family while omitting a particular
                # optional characteristic. That is normal, not an adapter fault.
                return

        state = self._revolution_state.setdefault(sensor.sensor_id, _RevolutionState())
        await start(CHAR_HR, _parse_hr)
        await start(
            CHAR_CYCLING_POWER,
            lambda data: _parse_cycling_power(data, state),
        )
        await start(CHAR_RSC, _parse_rsc)
        await start(CHAR_CSC, lambda data: _parse_csc(data, state))
        await start(CHAR_FTMS_INDOOR_BIKE, _parse_ftms_indoor_bike)
        # These parsers intentionally consume only the common instantaneous
        # fields whose byte layout is unambiguous across the FTMS profile.
        await start(CHAR_FTMS_TREADMILL, _parse_ftms_treadmill)

    async def async_disconnect_sensor(self, profile_id: str, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        lock = self._connect_lock(sensor_id)
        async with lock:
            # A connect/enrichment that completed while we waited may have merged
            # the sensor ID, so resolve it again under the same serialization point.
            sensor_id = self.runtime.resolve_sensor_id(sensor_id)
            self._profile_clients.get(profile_id, set()).discard(sensor_id)
            users = self._sensor_users.setdefault(sensor_id, set())
            users.discard(profile_id)
            if users:
                return
            self._sensor_users.pop(sensor_id, None)
            self._revolution_state.pop(sensor_id, None)
            client = self._clients.pop(sensor_id, None)
            if client is not None:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            self.runtime._notify_values_throttled({
                (sensor_id, "gatt_connection", None)
            })

    async def async_disconnect_profile(
        self, profile_id: str, *, keep_heart_rate: bool = False
    ) -> None:
        ids = self._profile_clients.get(profile_id, set()).copy()
        for sensor_id in ids:
            sensor = self.runtime.sensors.get(sensor_id)
            if keep_heart_rate and sensor and METRIC_HEART_RATE in sensor.capabilities:
                continue

            await self.async_disconnect_sensor(profile_id, sensor_id)

        if not self._profile_clients.get(profile_id):
            self._profile_clients.pop(profile_id, None)

    @property
    def receiver_count(self) -> int:
        scanner_count = getattr(bluetooth, "async_scanner_count", None)
        if scanner_count is None:
            return 1 if self.available else 0
        try:
            return int(scanner_count(self.hass, connectable=True))
        except TypeError:
            try:
                return int(scanner_count(self.hass))
            except Exception:
                return 0
        except Exception:
            return 0

    @property
    def connected_sensor_count(self) -> int:
        return sum(1 for client in self._clients.values() if client.is_connected)

    @property
    def receiver_details(self) -> list[dict]:
        return [
            {
                "type": "Home Assistant Bluetooth",
                "scanner_count": self.receiver_count,
                "proxy_capable": True,
            }
        ]

    async def async_shutdown(self) -> None:
        for unsub in tuple(self._unsubs):
            try:
                unsub()
            except Exception:
                pass
        self._unsubs.clear()
        self._last_discovery_fingerprint.clear()
        for task in tuple(self._identity_probe_tasks.values()):
            if not task.done():
                task.cancel()
        self._identity_probe_tasks.clear()
        self._identity_probe_last_attempt.clear()
        for profile_id in tuple(self._profile_clients):
            await self.async_disconnect_profile(profile_id, keep_heart_rate=False)
        self._connect_locks.clear()
        self.available = False
        self.hass.async_create_task(self.runtime.async_refresh_adapter_presence())
        self.runtime.notify_changed()


def _parse_hr(data: bytes) -> dict[str, float]:
    if len(data) < 2:
        return {}
    flags = data[0]
    if flags & 0x01 and len(data) >= 3:
        hr = int.from_bytes(data[1:3], "little")
    else:
        hr = data[1]
    return {METRIC_HEART_RATE: float(hr)} if 20 <= hr <= 260 else {}


def _counter_delta(current: int, previous: int, modulus: int) -> int:
    return (current - previous) % modulus


def _parse_cycling_power(
    data: bytes, state: _RevolutionState | None = None
) -> dict[str, float]:
    if len(data) < 4:
        return {}
    flags = int.from_bytes(data[0:2], "little")
    power = int.from_bytes(data[2:4], "little", signed=True)
    result: dict[str, float] = {}
    if -2000 <= power <= 5000:
        result[METRIC_POWER] = float(power)

    # Cycling Power Measurement optional fields are consumed in flag order.
    idx = 4
    if flags & (1 << 0):  # pedal power balance
        idx += 1
    if flags & (1 << 2):  # accumulated torque
        idx += 2
    if flags & (1 << 4):  # wheel revolution data
        idx += 6
    if flags & (1 << 5) and len(data) >= idx + 4 and state is not None:
        crank_revs = int.from_bytes(data[idx:idx + 2], "little")
        crank_time = int.from_bytes(data[idx + 2:idx + 4], "little")
        if state.crank_revs is not None and state.crank_time is not None:
            rev_delta = _counter_delta(crank_revs, state.crank_revs, 1 << 16)
            time_delta = _counter_delta(crank_time, state.crank_time, 1 << 16)
            if rev_delta > 0 and time_delta > 0:
                cadence = rev_delta * 60.0 * 1024.0 / time_delta
                if 0.0 <= cadence <= 300.0:
                    result[METRIC_CADENCE] = round(cadence, 2)
        state.crank_revs = crank_revs
        state.crank_time = crank_time
    return result


def _parse_rsc(data: bytes) -> dict[str, float]:
    if len(data) < 4:
        return {}
    speed_ms = int.from_bytes(data[1:3], "little") / 256.0
    cadence = data[3]
    result: dict[str, float] = {
        METRIC_SPEED: speed_ms * 3.6,
        METRIC_CADENCE: float(cadence),
    }
    idx = 4
    if data[0] & 0x01:  # stride length
        idx += 2
    if data[0] & 0x02 and len(data) >= idx + 4:  # total distance, 1/10 m
        result[METRIC_DISTANCE] = int.from_bytes(data[idx:idx + 4], "little") / 10000.0
    return result


def _parse_csc(
    data: bytes, state: _RevolutionState | None = None
) -> dict[str, float]:
    """Decode standard CSC crank cadence; wheel speed needs circumference."""
    if len(data) < 1 or state is None:
        return {}
    flags = data[0]
    idx = 1
    if flags & 0x01:  # cumulative wheel revs + last wheel event time
        if len(data) < idx + 6:
            return {}
        idx += 6
    if not (flags & 0x02) or len(data) < idx + 4:
        return {}

    crank_revs = int.from_bytes(data[idx:idx + 2], "little")
    crank_time = int.from_bytes(data[idx + 2:idx + 4], "little")
    result: dict[str, float] = {}
    if state.crank_revs is not None and state.crank_time is not None:
        rev_delta = _counter_delta(crank_revs, state.crank_revs, 1 << 16)
        time_delta = _counter_delta(crank_time, state.crank_time, 1 << 16)
        if rev_delta > 0 and time_delta > 0:
            cadence = rev_delta * 60.0 * 1024.0 / time_delta
            if 0.0 <= cadence <= 300.0:
                result[METRIC_CADENCE] = round(cadence, 2)
    state.crank_revs = crank_revs
    state.crank_time = crank_time
    return result


def _parse_ftms_indoor_bike(data: bytes) -> dict[str, float]:
    """Decode the common FTMS Indoor Bike Data fields in flag order."""
    if len(data) < 2:
        return {}
    flags = int.from_bytes(data[0:2], "little")
    idx = 2
    result: dict[str, float] = {}

    # Bit 0 is "More Data": instantaneous speed is present when it is clear.
    if not (flags & (1 << 0)):
        if len(data) < idx + 2:
            return result
        result[METRIC_SPEED] = int.from_bytes(data[idx:idx + 2], "little") / 100.0
        idx += 2
    if flags & (1 << 1):  # average speed
        idx += 2
    if flags & (1 << 2) and len(data) >= idx + 2:
        result[METRIC_CADENCE] = int.from_bytes(data[idx:idx + 2], "little") / 2.0
        idx += 2
    if flags & (1 << 3):  # average cadence
        idx += 2
    if flags & (1 << 4) and len(data) >= idx + 3:
        result[METRIC_DISTANCE] = int.from_bytes(data[idx:idx + 3], "little") / 1000.0
        idx += 3
    if flags & (1 << 5):  # resistance level
        idx += 2
    if flags & (1 << 6) and len(data) >= idx + 2:
        result[METRIC_POWER] = float(int.from_bytes(data[idx:idx + 2], "little", signed=True))
        idx += 2
    if flags & (1 << 7):  # average power
        idx += 2
    if flags & (1 << 8):  # expended energy block
        idx += 5
    if flags & (1 << 9) and len(data) > idx:
        hr = data[idx]
        if 20 <= hr <= 260:
            result[METRIC_HEART_RATE] = float(hr)
    return result


def _parse_ftms_treadmill(data: bytes) -> dict[str, float]:
    """Decode safe common FTMS Treadmill Data fields."""
    if len(data) < 4:
        return {}
    flags = int.from_bytes(data[0:2], "little")
    idx = 2
    result: dict[str, float] = {}
    if not (flags & 0x01) and len(data) >= idx + 2:
        result[METRIC_SPEED] = int.from_bytes(data[idx:idx + 2], "little") / 100.0
        idx += 2
    # Treadmill's remaining optional fields differ from Indoor Bike. We avoid
    # guessing their offsets here; speed is still a useful canonical live input.
    return result
