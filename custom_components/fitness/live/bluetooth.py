"""Bluetooth SIG fitness-sensor transport for Fitness."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..device_archives import DeviceArchiveRegistry
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

_SOURCE_PINNED_CLIENT_CLASSES: dict[str, type] = {}

def _source_pinned_client_class(source: str):
    """Return an HA Bleak client class constrained to one scanner source.

    Home Assistant's HA Bleak wrapper intentionally re-ranks every scanner that
    can see an address at connect time.  That behavior is excellent for normal
    stateless sensors, but a secure bond belongs to one Bluetooth central.
    Archive adapters may therefore request a source pin while still going through
    bleak-retry-connector and HA's connection-slot allocator.

    This helper is transport-generic: callers provide only HA's scanner source ID.
    No vendor or physical-device matching belongs here.
    """
    source = str(source or "")
    if not source:
        return BleakClient
    cached = _SOURCE_PINNED_CLIENT_CLASSES.get(source)
    if cached is not None:
        return cached

    class FitnessSourcePinnedBleakClient(BleakClient):
        _fitness_required_source = source

        def __init__(self, address_or_ble_device, *args, **kwargs):
            self._fitness_address = str(
                getattr(address_or_ble_device, "address", address_or_ble_device)
            )
            super().__init__(address_or_ble_device, *args, **kwargs)

        def _async_get_best_available_backend_and_device(self, manager):
            routes_for_address = getattr(
                manager, "async_scanner_devices_by_address", None
            )
            backend_for_route = getattr(
                self, "_async_get_backend_for_ble_device", None
            )
            if routes_for_address is None or backend_for_route is None:
                raise BleakError(
                    "Bluetooth source pinning requires Home Assistant's HA Bluetooth client"
                )

            saw_source = False
            for route in routes_for_address(self._fitness_address, True):
                scanner = getattr(route, "scanner", None)
                route_source = str(getattr(scanner, "source", None) or "")
                if route_source != self._fitness_required_source:
                    continue
                saw_source = True
                backend = backend_for_route(
                    manager, scanner, getattr(route, "ble_device", None)
                )
                if backend is not None:
                    _LOGGER.debug(
                        "Bluetooth source pin selected %s (%s) for %s",
                        getattr(scanner, "name", route_source),
                        route_source,
                        self._fitness_address,
                    )
                    return backend
                raise BleakError(
                    f"Bluetooth source {route_source} has no free connection slot "
                    f"for {self._fitness_address}"
                )

            if saw_source:
                raise BleakError(
                    f"Bluetooth source {self._fitness_required_source} cannot connect "
                    f"to {self._fitness_address}"
                )
            raise BleakError(
                f"Bluetooth source {self._fitness_required_source} cannot currently "
                f"reach {self._fitness_address}"
            )

    FitnessSourcePinnedBleakClient.__name__ = "FitnessSourcePinnedBleakClient"
    _SOURCE_PINNED_CLIENT_CLASSES[source] = FitnessSourcePinnedBleakClient
    return FitnessSourcePinnedBleakClient

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
CHAR_BATTERY_LEVEL = BASE.format("2a19")

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

CHARACTERISTIC_CAPABILITIES = {
    CHAR_HR: {METRIC_HEART_RATE},
    CHAR_CYCLING_POWER: {METRIC_POWER, METRIC_CADENCE},
    CHAR_CSC: {METRIC_CADENCE},
    CHAR_RSC: {METRIC_SPEED, METRIC_CADENCE, METRIC_DISTANCE},
    CHAR_FTMS_INDOOR_BIKE: {
        METRIC_SPEED,
        METRIC_CADENCE,
        METRIC_POWER,
        METRIC_DISTANCE,
        METRIC_HEART_RATE,
    },
    CHAR_FTMS_TREADMILL: {METRIC_SPEED},
}

BATTERY_SERVICE = BASE.format("180f")
RAW_DIAGNOSTIC_MIN_INTERVAL = 10.0
PASSIVE_DECODE_MIN_INTERVAL = 5.0
DISCOVERY_DEDUPE_WINDOW = 0.5
BLE_DISCONNECT_TIMEOUT = 5.0
DISCOVERY_CACHE_REPLAY_LIMIT = 512
DISCOVERY_CACHE_SCAN_LIMIT = 2048
DISCOVERY_REFRESH_MIN_INTERVAL = 20.0
DISCOVERY_ACTIVE_SCAN_DURATION = 8.0
DISCOVERY_ACTIVE_SCAN_TIMEOUT = 12.0


def _battery_metadata() -> dict[str, object]:
    """Return one translated metadata contract for every BLE battery source."""
    return {
        "translation_key": "physical_battery",
        "unit": "%",
        "device_class": "battery",
        "state_class": "measurement",
        "icon": "mdi:battery",
        "passive": True,
        "decoder": "bluetooth_sig_battery_level",
    }


def _parse_battery(data: bytes) -> dict[str, float]:
    """Decode the Bluetooth SIG Battery Level characteristic."""
    if not data:
        return {}
    value = int(data[0])
    return {"battery": float(value)} if 0 <= value <= 100 else {}


def _passive_advertisement_values(info) -> tuple[dict[str, float], dict[str, dict]]:
    """Decode connectionless standard and catalog-selected proprietary values."""
    values: dict[str, float] = {}
    metadata: dict[str, dict] = {}

    # Bluetooth SIG standard Battery Service handling remains protocol-generic.
    service_data = getattr(info, "service_data", {}) or {}
    for key, payload in service_data.items():
        if str(key).lower() == BATTERY_SERVICE and payload:
            battery_values = _parse_battery(bytes(payload))
            if battery_values:
                values.update(battery_values)
                metadata["battery"] = _battery_metadata()

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
        # Device deletion rediscovery is one bounded timer per address. It exists
        # only to bridge Fitness's short anti-resurrection quarantine; normal BLE
        # discovery never polls or starts a private scanner.
        self._rediscovery_handles: dict[str, asyncio.TimerHandle] = {}
        # Setup/config-flow discovery is control-plane work.  Coalesce concurrent
        # requests and enforce a short cooldown so opening the guide repeatedly
        # cannot force the Bluetooth stack into continuous active scanning.
        self._discovery_refresh_lock = asyncio.Lock()
        self._last_discovery_refresh = -DISCOVERY_REFRESH_MIN_INTERVAL
        self.device_archives = DeviceArchiveRegistry(self)
        # Raw BLE fitness measurements require an active GATT subscription, but
        # Fitness deliberately does not keep telemetry GATT open while idle.
        # Accepted sensors get only a short Device Information probe. A persistent
        # GATT subscription is owned by a live profile and is opened only when
        # Bluetooth is that live session's selected/fallback transport.

    async def async_setup(self) -> None:
        """Register one HA Bluetooth discovery callback; no private scanner."""
        from homeassistant.setup import async_setup_component

        for issue in vendor_registry_issues():
            _LOGGER.warning("Fitness vendor registry: %s", issue)

        if not await async_setup_component(self.hass, "bluetooth", {}):
            self.available = False
            self.last_error = "Home Assistant Bluetooth could not be initialized"
            return

        await self.device_archives.async_setup()

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
        # Direct workout-archive adapters contribute their own low-cost HA
        # Bluetooth matchers through a vendor-neutral registry. Actual protocol
        # capability verification is deferred until a user accepts the sensor.
        for matcher in self.device_archives.bluetooth_matchers():
            self._unsubs.append(
                bluetooth.async_register_callback(
                    self.hass,
                    self._async_discovered,
                    matcher,
                    BluetoothScanningMode.PASSIVE,
                    replay=bluetooth.BluetoothCallbackReplay.DISABLED,
                )
            )
        self._refresh_available()
        self.runtime.set_adapter_presence("bluetooth", self.available)

        # Register all matchers first, then replay the HA cache exactly once.
        # This avoids N matcher registrations each replaying the same cache while
        # still discovering devices that were already present before Fitness.
        self._replay_cached_discovery()

    def _cached_discovery_relevant(self, info) -> bool:
        """Cheaply reject unrelated cached BLE devices before runtime work."""
        manufacturer_data = getattr(info, "manufacturer_data", {}) or {}
        uuids = {str(value).lower() for value in (getattr(info, "service_uuids", None) or [])}
        if any(service_uuid in uuids for service_uuid in SERVICE_CAPABILITIES):
            return True
        return self.device_archives.match_bluetooth(
            getattr(info, "name", None), uuids, manufacturer_data
        ) is not None

    def _replay_cached_discovery(self) -> int:
        """Replay a bounded relevant subset of Home Assistant's current cache."""
        try:
            infos = bluetooth.async_discovered_service_info(self.hass, connectable=False)
        except TypeError:
            infos = bluetooth.async_discovered_service_info(self.hass, False)
        except Exception:
            _LOGGER.debug("Unable to read Home Assistant Bluetooth discovery cache", exc_info=True)
            return 0

        processed = 0
        seen: set[tuple[str, str]] = set()
        for cache_index, info in enumerate(infos):
            if cache_index >= DISCOVERY_CACHE_SCAN_LIMIT:
                _LOGGER.debug(
                    "Fitness Bluetooth cache scan reached safety limit %s",
                    DISCOVERY_CACHE_SCAN_LIMIT,
                )
                break
            key = (
                str(getattr(info, "address", "")).upper(),
                str(getattr(info, "source", None) or ""),
            )
            if key in seen or not key[0] or not self._cached_discovery_relevant(info):
                continue
            seen.add(key)
            self._async_discovered(info, None)
            processed += 1
            if processed >= DISCOVERY_CACHE_REPLAY_LIMIT:
                _LOGGER.debug(
                    "Fitness Bluetooth cache replay reached safety limit %s",
                    DISCOVERY_CACHE_REPLAY_LIMIT,
                )
                break
        return processed

    async def async_refresh_discovery(self) -> None:
        """Perform one bounded control-plane scan and replay relevant cache.

        No GATT client is opened here.  Home Assistant deduplicates concurrent
        one-shot active scans globally; Fitness additionally coalesces its own UI
        requests and rate-limits repeated guide opens.
        """
        async with self._discovery_refresh_lock:
            now = self.hass.loop.time()
            if now - self._last_discovery_refresh >= DISCOVERY_REFRESH_MIN_INTERVAL:
                self._last_discovery_refresh = now
                request_scan = getattr(bluetooth, "async_request_active_scan", None)
                if request_scan is not None:
                    try:
                        async with asyncio.timeout(DISCOVERY_ACTIVE_SCAN_TIMEOUT):
                            try:
                                await request_scan(
                                    self.hass, duration=DISCOVERY_ACTIVE_SCAN_DURATION
                                )
                            except TypeError:
                                # Compatibility with the first HA API shape.
                                await request_scan(self.hass)
                    except TimeoutError:
                        _LOGGER.debug("Timed out requesting Fitness Bluetooth discovery sweep")
                    except Exception:
                        _LOGGER.debug(
                            "Unable to request Fitness Bluetooth discovery sweep",
                            exc_info=True,
                        )
            self._replay_cached_discovery()

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
        archive_advertisement = self.device_archives.match_bluetooth(
            info.name, uuids, manufacturer_data
        )

        capabilities: set[str] = set()
        for service, caps in SERVICE_CAPABILITIES.items():
            if service in uuids:
                capabilities.update(caps)
        if archive_advertisement is not None:
            capabilities.update(archive_advertisement.capabilities)
        # A direct archive advertisement may be only a vendor candidate until a
        # bounded GATT handshake proves archive compatibility. Keep that candidate
        # discoverable without prematurely granting workout-history capability.
        if not capabilities and archive_advertisement is None:
            return

        endpoint_id = f"bluetooth:{address}"
        identity_metadata = {
            "advertised_name": info.name,
            "service_uuids": sorted(uuids),
            "connectable": bool(getattr(info, "connectable", False)),
            "manufacturer_data_ids": sorted(int(x) for x in manufacturer_data),
            **(archive_advertisement.metadata if archive_advertisement is not None else {}),
        }

        # A restored endpoint alias is not authoritative when the newly observed
        # protocol/vendor identity contradicts the old physical device. Release
        # the route first, then let normal registration create the correct
        # protocol-owned candidate.
        detached_sensor_id = self.runtime.detach_conflicting_endpoint_alias(
            endpoint_id, self.transport, identity_metadata
        )
        if detached_sensor_id is not None:
            self.device_archives.identity_conflict_repaired(detached_sensor_id)
            self._provisional_identity_signature.pop(endpoint_id, None)
            self._last_discovery_fingerprint.pop(endpoint_id, None)

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
        known_endpoint = (
            known_sensor.endpoints.get(self.transport)
            if known_sensor is not None
            else None
        )
        was_available = bool(known_endpoint is not None and known_endpoint.available)

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
                metadata=identity_metadata,
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

        if archive_advertisement is not None:
            endpoint_now = sensor.endpoints.get(self.transport)
            self.device_archives.advertise(
                sensor.sensor_id,
                archive_advertisement,
                became_available=bool(
                    accepted
                    and not was_available
                    and endpoint_now is not None
                    and endpoint_now.available
                ),
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

        # Do not subscribe to raw GATT telemetry while idle.  A short identity
        # probe is allowed; live-session transport reconciliation owns any later
        # persistent notification connection.
        self._schedule_identity_probe(sensor.sensor_id)

    def _archive_coordinator(self, sensor_id: str):
        """Return the accepted device archive owner without model checks."""
        sensor = self.runtime.sensors.get(self.runtime.resolve_sensor_id(sensor_id))
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        metadata = endpoint.metadata if endpoint is not None else {}
        return self.device_archives.coordinator_for_metadata(metadata)

    def sensor_acceptance_changed(self, sensor_id: str, accepted: bool) -> None:
        """Probe identity on acceptance; never keep idle telemetry GATT open."""
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        metadata = endpoint.metadata if endpoint is not None else {}
        self.device_archives.acceptance_changed(sensor_id, accepted, metadata)
        if accepted:
            # Archive adapters may own a pairing-sensitive first connection.  The
            # generic DIS probe must stay out of the way when the adapter declares
            # that policy; this keeps the transport vendor-neutral while avoiding a
            # second short-lived GATT session before a stable bond is established.
            if self.device_archives.generic_identity_probe_allowed(metadata):
                self._schedule_identity_probe(sensor_id)
            else:
                pending_probe = self._identity_probe_tasks.pop(sensor_id, None)
                if pending_probe is not None and not pending_probe.done():
                    pending_probe.cancel()
        else:
            self._schedule_unowned_disconnect(sensor_id)

    def forget_sensor(self, sensor_id: str, endpoint_id: str | None = None) -> None:
        """Clear per-device BLE state after a user deletes a physical sensor.

        Runtime keeps a short anti-resurrection quarantine, but provider-local
        advertisement fingerprints, identity signatures and reconnect throttles
        must not survive the delete. Otherwise a restarted watch broadcast can
        look like the same already-consumed BLE observation and rediscovery may be
        delayed even though the physical sensor was explicitly removed from HA.
        """
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        if endpoint_id:
            endpoint_id = str(endpoint_id)
            self._last_discovery_fingerprint.pop(endpoint_id, None)
            self._provisional_identity_signature.pop(endpoint_id, None)
            self._provisional_passive_last_decode.pop(endpoint_id, None)
            self._raw_diag_last_publish.pop(endpoint_id, None)
            self._raw_diag_last_value.pop(endpoint_id, None)
            self._stable_diag_last_value.pop(endpoint_id, None)

        task = self._identity_probe_tasks.pop(canonical, None)
        if task is not None and not task.done():
            task.cancel()
        self._identity_probe_last_attempt.pop(canonical, None)
        self.device_archives.forget_sensor(canonical)

        if endpoint_id and endpoint_id.startswith("bluetooth:") and not endpoint_id.startswith("bluetooth:web:"):
            address = endpoint_id.split(":", 1)[1].strip().upper()
            if re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address):
                # Prepare the next live advertisement immediately, then trigger
                # one cached rediscovery after Runtime's five-second tombstone
                # quarantine. Home Assistant explicitly recommends rediscovery
                # after a Bluetooth-backed device is removed.
                clear_match = getattr(bluetooth, "async_clear_address_from_match_history", None)
                if clear_match is not None:
                    try:
                        clear_match(self.hass, address)
                    except Exception:
                        _LOGGER.debug("Unable to clear Bluetooth match history for %s", address, exc_info=True)
                previous = self._rediscovery_handles.pop(address, None)
                if previous is not None:
                    previous.cancel()

                def _rediscover() -> None:
                    self._rediscovery_handles.pop(address, None)
                    try:
                        bluetooth.async_rediscover_address(self.hass, address)
                    except Exception:
                        _LOGGER.debug("Unable to rediscover deleted Bluetooth device %s", address, exc_info=True)

                self._rediscovery_handles[address] = self.hass.loop.call_later(5.5, _rediscover)

        self._schedule_unowned_disconnect(canonical)

    def sensor_assignment_changed(self, sensor_id: str) -> None:
        """Refresh an archive device when its allowed Fitness profiles change."""
        coordinator = self._archive_coordinator(sensor_id)
        if coordinator is not None:
            coordinator.assignment_changed(sensor_id)

    def _schedule_unowned_disconnect(self, sensor_id: str) -> None:
        """Close a GATT client unless an active live profile currently owns it."""
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)

        async def _disconnect() -> None:
            lock = self._connect_lock(sensor_id)
            try:
                async with asyncio.timeout(BLE_DISCONNECT_TIMEOUT * 2):
                    async with lock:
                        canonical = self.runtime.resolve_sensor_id(sensor_id)
                        if self._sensor_users.get(canonical):
                            return
                        client = self._clients.pop(canonical, None)
                        self._revolution_state.pop(canonical, None)
                        if client is not None:
                            await self._async_disconnect_client(
                                client, reason="unowned sensor cleanup"
                            )
                        self.runtime._notify_values_throttled({
                            (canonical, "gatt_connection", None)
                        })
            except TimeoutError:
                _LOGGER.warning(
                    "Timed out waiting to clean up unowned Bluetooth sensor %s",
                    sensor_id,
                )

        self.hass.async_create_background_task(
            _disconnect(),
            f"fitness BLE unowned disconnect {sensor_id}",
            eager_start=False,
        )

    def schedule_identity_probe_candidates(self, capabilities: set[str]) -> None:
        """Probe recently seen BLE-only sensors that could match a new ANT endpoint.

        Discovery-stage identity matters too: obtaining DIS model/serial before Add
        lets Runtime name the card from the model catalog and gives exact serial
        matching a chance to collapse BT + ANT into one provisional physical device.
        The probe still only collects identity; it never merges by capability/name.
        """
        wanted = set(capabilities)
        for sensor in tuple(self.runtime.sensors.values()):
            sensor_id = self.runtime.resolve_sensor_id(sensor.sensor_id)
            current = self.runtime.sensors.get(sensor_id)
            if current is None:
                continue
            endpoint = current.endpoints.get(self.transport)
            if endpoint is None or "antplus" in current.endpoints:
                continue
            if not self.runtime.sensor_recently_observed(sensor_id):
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
        if not self.device_archives.generic_identity_probe_allowed(endpoint.metadata):
            return
        if endpoint.metadata.get("identity_source") == "gatt_device_information":
            return
        # `BluetoothServiceInfoBleak.connectable` describes the scanner/path that
        # delivered an advertisement, not whether *any* Home Assistant Bluetooth
        # controller can connect to this address. A wearable may therefore be
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
            # Re-check after taking the device lock.  A probe may have been queued
            # while discovery metadata was still incomplete and then become
            # forbidden when a secure archive adapter claimed the endpoint.
            if not self.device_archives.generic_identity_probe_allowed(endpoint.metadata):
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
                    await self._async_disconnect_client(
                        client, reason="identity probe cleanup"
                    )

    def sensor_connected(self, sensor_id: str) -> bool:
        client = self._clients.get(str(sensor_id))
        return bool(client is not None and client.is_connected)

    def sensor_users(self, sensor_id: str) -> set[str]:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        return set(self._sensor_users.get(sensor_id, set()))

    def _connect_lock(self, sensor_id: str) -> asyncio.Lock:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        return self._connect_locks.setdefault(sensor_id, asyncio.Lock())

    async def _async_disconnect_client(self, client, *, reason: str) -> None:
        """Disconnect one BLE client without ever blocking HA shutdown forever."""
        try:
            async with asyncio.timeout(BLE_DISCONNECT_TIMEOUT):
                await client.disconnect()
        except TimeoutError:
            _LOGGER.warning("Timed out during Bluetooth disconnect: %s", reason)
        except Exception:
            _LOGGER.debug(
                "Bluetooth disconnect failed during %s", reason, exc_info=True
            )

    async def establish_connection(
        self,
        ble_device,
        name: str,
        *,
        max_attempts: int,
        pair: bool = False,
        source: str | None = None,
    ):
        """Use HA's retry connector, optionally pairing on one exact scanner.

        ``pair`` and ``source`` are transport-level capabilities, not vendor logic.
        A source pin is needed for secure devices whose bond belongs to a specific
        Bluetooth central; the client still uses Home Assistant's backend and
        connection-slot allocation through ``bleak-retry-connector``.
        """
        client_class = _source_pinned_client_class(source) if source else BleakClient
        return await establish_connection(
            client_class,
            device=ble_device,
            name=name,
            max_attempts=max_attempts,
            pair=pair,
        )

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
                        await self._async_disconnect_client(
                            client, reason="failed live connection cleanup"
                        )

    async def _async_enrich_identity(
        self, sensor: LiveSensor, endpoint, client: BleakClient, *,
        manage_client_state: bool = True,
    ) -> LiveSensor:
        """Read standard DIS/GATT metadata and refine the canonical identity."""
        metadata = dict(endpoint.metadata)
        details: dict[str, object] = {}
        detail_meta: dict[str, dict] = {}
        battery_values: dict[str, float] = {}
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
            # every field separately. The Bluetooth PnP product ID is *not* a
            # consumer model/generation number and must never be promoted to HA
            # model_id; vendor catalogs may interpret it explicitly if documented.
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
                for pnp_key in pnp_values:
                    detail_meta[pnp_key] = {
                        "name": pnp_key.replace("bluetooth_", "Bluetooth ").replace("_", " ").title(),
                        "icon": "mdi:identifier", "enabled_default": False,
                        "entity_category": "diagnostic",
                    }

        # Battery Service normally exposes its value through readable/notify
        # characteristic 0x2A19, not advertisement service data. Reading it on
        # every short identity/archive connection prevents a valid battery entity
        # from remaining unavailable when the peripheral does not advertise the
        # level inline.
        try:
            battery_values = _parse_battery(
                bytes(await client.read_gatt_char(CHAR_BATTERY_LEVEL))
            )
        except Exception:
            battery_values = {}

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
        # Device-specific interpretation of generic GATT identity facts belongs
        # to the archive adapter registry, never to the Bluetooth transport.
        verified_services = list(metadata.get("service_uuids") or []) + service_uuids
        metadata = self.device_archives.enrich_connected_metadata(
            metadata, verified_services
        )
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

        # Advertisements frequently list only one primary service because their
        # payload is small. The connected GATT database is authoritative for the
        # live entities Fitness can actually decode, so enrich capabilities from
        # every discovered measurement characteristic rather than freezing the
        # first advertised service forever.
        gatt_capabilities = set(endpoint.capabilities)
        for characteristic_uuid in characteristic_uuids:
            gatt_capabilities.update(
                CHARACTERISTIC_CAPABILITIES.get(characteristic_uuid, set())
            )
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
            name=str(refined_name), capabilities=gatt_capabilities,
            address=endpoint.address, source=endpoint.source,
            last_seen=datetime.now(timezone.utc), rssi=endpoint.rssi,
            available=True, metadata=metadata,
        )
        if battery_values:
            self.runtime.publish_passive(
                merged.sensor_id,
                battery_values,
                transport=self.transport,
                metadata={"battery": _battery_metadata()},
            )
        if details:
            self.runtime.publish_details(
                merged.sensor_id, details, transport="bluetooth_gatt",
                metadata=detail_meta, priority=80,
            )
        if self.runtime.sensor_is_accepted(merged.sensor_id):
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
        def notify(parser, *, passive: bool = False):
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
                    if passive:
                        self.runtime.publish_passive(
                            sensor.sensor_id,
                            values,
                            transport=self.transport,
                            metadata={"battery": _battery_metadata()},
                        )
                    else:
                        self.runtime.publish(
                            sensor.sensor_id, values, transport=self.transport
                        )
            return _callback

        async def start(uuid: str, parser, *, passive: bool = False) -> None:
            try:
                await client.start_notify(uuid, notify(parser, passive=passive))
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
        await start(CHAR_BATTERY_LEVEL, _parse_battery, passive=True)

    async def async_disconnect_sensor(self, profile_id: str, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        lock = self._connect_lock(sensor_id)
        try:
            async with asyncio.timeout(BLE_DISCONNECT_TIMEOUT * 2):
                async with lock:
                    # A connect/enrichment that completed while we waited may have
                    # merged the sensor ID, so resolve it again under the same
                    # serialization point.
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
                        await self._async_disconnect_client(
                            client, reason="profile sensor disconnect"
                        )
                    self.runtime._notify_values_throttled({
                        (sensor_id, "gatt_connection", None)
                    })
        except TimeoutError:
            _LOGGER.warning(
                "Timed out waiting to disconnect Bluetooth sensor %s for profile %s",
                sensor_id,
                profile_id,
            )

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
        await self.device_archives.async_shutdown()
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
        for handle in tuple(self._rediscovery_handles.values()):
            handle.cancel()
        self._rediscovery_handles.clear()
        for profile_id in tuple(self._profile_clients):
            await self.async_disconnect_profile(profile_id, keep_heart_rate=False)
        # Defensive cleanup: any remaining client should be profile-owned, but
        # explicitly close all clients during integration shutdown.
        for sensor_id, client in tuple(self._clients.items()):
            self._clients.pop(sensor_id, None)
            await self._async_disconnect_client(
                client, reason="integration shutdown"
            )
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
