"""Global live-workout transport runtime for Fitness."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any
from types import MappingProxyType

from homeassistant.config_entries import ConfigSubentry

from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.helpers.storage import Store

from .device_identity import (
    canonical_identity_fields,
    catalog_cross_transport_ids,
    catalog_product_id,
    catalog_transport_correlation,
    resolve_identity,
)

from ..const import (
    CONF_LIVE_SENSOR_IDS,
    DOMAIN,
    LIVE_ADAPTER_STORE_KEY,
    LIVE_ADAPTER_STORE_VERSION,
    METRIC_ALTITUDE,
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
)

LIVE_METRICS = (
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_CADENCE,
    METRIC_SPEED,
    METRIC_DISTANCE,
    METRIC_ALTITUDE,
)
TRANSPORTS = ("bluetooth", "antplus")
DISCOVERY_RECENT_SECONDS = 30.0
TRANSPORT_PRIORITY = ("antplus", "bluetooth")
HUB_ENTRY_TYPE = "live_hub"
HUB_UNIQUE_ID = "local_sensors"
HUB_DEVICE_ID = "sensors_adapters"
SENSOR_COLLECTION_DEVICE_ID = "sensors"  # legacy v2 device identifier; removed by migration
SENSORS_SUBENTRY_TYPE = "sensors"
SENSORS_SUBENTRY_UNIQUE_ID = "fitness_sensors"
ANTPLUS_SUBENTRY_TYPE = "antplus_adapters"
ANTPLUS_SUBENTRY_UNIQUE_ID = "fitness_antplus_adapters"
BLUETOOTH_SUBENTRY_TYPE = "bluetooth_adapters"
BLUETOOTH_SUBENTRY_UNIQUE_ID = "fitness_bluetooth_adapters"
LEGACY_ADAPTERS_SUBENTRY_TYPE = "adapters"
LEGACY_ADAPTERS_SUBENTRY_UNIQUE_ID = "fitness_adapters"
ADAPTER_DEVICE_MODEL_VERSION = 1
ANT_DATA_FRESH_SECONDS = 3.0
TRANSPORT_HANDOVER_INTERVAL_SECONDS = 1.0
_LOGGER = logging.getLogger(__name__)



def _clean(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _normalize_name(value: str | None) -> str:
    text = str(value or "").strip()
    return text or "Fitness sensor"


def _serial(metadata: dict[str, Any]) -> str | None:
    for key in ("serial_number", "serial_no", "serial", "device_serial"):
        value = metadata.get(key)
        if value not in (None, "", 0, "0"):
            return _clean(value)
    return None



@dataclass(slots=True)
class TransportEndpoint:
    transport: str
    endpoint_id: str
    address: str | None = None
    capabilities: set[str] = field(default_factory=set)
    source: str | None = None
    last_seen: datetime | None = None
    rssi: int | None = None
    available: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LiveSensor:
    """One physical fitness sensor, potentially reachable by many transports."""

    sensor_id: str
    name: str
    capabilities: set[str] = field(default_factory=set)
    endpoints: dict[str, TransportEndpoint] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    active_transport: str | None = None

    @property
    def transports(self) -> set[str]:
        return set(self.endpoints)

    @property
    def preferred_transport(self) -> str | None:
        for transport in TRANSPORT_PRIORITY:
            if transport in self.endpoints:
                return transport
        return next(iter(self.endpoints), None)

    @property
    def transport(self) -> str:
        return self.active_transport or self.preferred_transport or "unknown"

    def endpoint(self, transport: str | None = None) -> TransportEndpoint | None:
        return self.endpoints.get(transport or self.transport)

    @property
    def address(self) -> str | None:
        endpoint = self.endpoint()
        return endpoint.address if endpoint else None

    @property
    def source(self) -> str | None:
        endpoint = self.endpoint()
        return endpoint.source if endpoint else None

    @property
    def rssi(self) -> int | None:
        values = [x.rssi for x in self.endpoints.values() if x.rssi is not None]
        return max(values) if values else None

    @property
    def last_seen(self) -> datetime | None:
        values = [x.last_seen for x in self.endpoints.values() if x.last_seen]
        return max(values) if values else None

    @property
    def available(self) -> bool:
        return any(x.available for x in self.endpoints.values())

    def label(self) -> str:
        metrics = ", ".join(sorted(self.capabilities)) or "fitness sensor"
        transports = "+".join(x.upper() for x in TRANSPORT_PRIORITY if x in self.endpoints)
        return f"{self.name} — {transports or 'LOCAL'} · {metrics}"


class LiveRuntime:
    """One global transport runtime shared by every Fitness profile."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.sensors: dict[str, LiveSensor] = {}
        self.endpoint_aliases: dict[str, str] = {}
        self.providers: dict[str, Any] = {}
        self.profile_entries: dict[str, Any] = {}
        self.hub_entry = None
        self.sensors_subentry_id: str | None = None
        self.antplus_subentry_id: str | None = None
        self.bluetooth_subentry_id: str | None = None
        self.measurements: dict[str, dict[str, float]] = {}
        self.measurement_sources: dict[str, dict[str, str]] = {}
        self.measurement_time: dict[str, datetime] = {}
        self.sensor_values: dict[str, dict[str, float]] = {}
        self.sensor_value_transport: dict[str, dict[str, str]] = {}
        self._listeners: set[Any] = set()
        self._structure_listeners: set[Any] = set()
        # High-frequency physical-sensor entities subscribe by exact sensor/value
        # key instead of joining the global runtime listener fan-out.
        self._sensor_value_listeners: dict[tuple[str, str, str | None], set[Any]] = {}
        self._pending_sensor_value_changes: set[tuple[str, str, str | None]] = set()
        self._last_seen_notify_bucket: dict[str, datetime | None] = {}
        self._suppress_entry_reload_once: set[str] = set()
        self._value_notify_handle = None
        self._last_value_notify_monotonic = 0.0
        # Profile/session work is also coalesced. Multi-characteristic FTMS/BLE
        # notifications must not invoke the workout manager once per packet.
        self._profile_live_notify_handles: dict[str, Any] = {}
        self._profile_last_live_notify_monotonic: dict[str, float] = {}
        self._transport_claims: dict[str, set[str]] = {}
        self._profile_claims: dict[str, set[str]] = {}
        self._profile_sensor_transport: dict[str, dict[str, str]] = {}
        # A physical fitness sensor can be assigned to many profiles, but it can
        # measure only one person at a time. Workout ownership is therefore
        # exclusive per canonical physical sensor. Locks survive the original
        # owner's stop while any overlapping Fitness session/recovery remains
        # active, and are cleared only when the global workout epoch becomes idle.
        self._sensor_workout_owner: dict[str, str] = {}
        self._profile_claimed_sensors: dict[str, set[str]] = {}
        self._profile_session_order: dict[str, int] = {}
        self._session_order_counter = 0
        self._sensor_claim_reconcile_pending: set[str] = set()
        self._sensor_claim_reconcile_last_attempt: dict[str, float] = {}
        self._store = Store[dict[str, Any]](
            hass, LIVE_ADAPTER_STORE_VERSION, LIVE_ADAPTER_STORE_KEY, private=True
        )
        self._configured = {name: False for name in TRANSPORTS}
        self._enabled = {name: False for name in TRANSPORTS}
        self._initialized = False
        self._discovery_started: set[str] = set()
        self._discovery_tasks: dict[str, asyncio.Task] = {}
        self._sensor_device_refresh_handles: dict[str, asyncio.TimerHandle] = {}
        self._sensor_materialization_pending: set[str] = set()
        self._save_pending = False
        self._save_handle = None
        self._hub_reload_pending = False
        # Lightweight radio presence tracking. This layer deliberately does not
        # import/load the Fitness Bluetooth or ANT+ provider modules.
        self._adapter_presence = {name: False for name in TRANSPORTS}
        self._remote_ant_last_seen: dict[str, float] = {}
        self._presence_task = None
        self._presence_unsubs: list[Any] = []
        self._presence_started = False
        self.sensor_passive_values: dict[str, dict[str, Any]] = {}
        self.sensor_passive_meta: dict[str, dict[str, dict[str, Any]]] = {}
        self.sensor_passive_sources: dict[str, dict[str, dict[str, Any]]] = {}
        # Protocol/device-information observations which are not core live metrics.
        # Keys are canonical across transports so ANT+/BLE descriptions of the same
        # physical fact materialize as one Home Assistant entity.
        self.sensor_detail_values: dict[str, dict[str, Any]] = {}
        self.sensor_detail_meta: dict[str, dict[str, dict[str, Any]]] = {}
        self.sensor_detail_sources: dict[str, dict[str, dict[str, Any]]] = {}
        self.sensor_detail_source: dict[str, dict[str, str]] = {}
        self._sensor_event_listeners: dict[tuple[str, str], set[Any]] = {}
        self._profile_handover_tasks: dict[str, asyncio.Task] = {}
        self._device_registry_unsub = None
        self._sensor_device_ids: dict[str, str] = {}
        self._sensor_device_signatures: dict[str, tuple[Any, ...]] = {}
        self._structure_notify_handle: Any | None = None
        # Sensor IDs explicitly deleted by the user must be rediscovered and
        # reassigned before they may become HA devices again. Persist this set
        # so a restart cannot resurrect an accepted sensor from stale profile/store state.
        self._requires_reassignment: set[str] = set()
        self._rediscovery_quarantine_until: dict[str, float] = {}
        self._stall_watchdog = None

    async def async_initialize(self) -> None:
        if self._initialized:
            return
        stored = await self._store.async_load() or {}
        sanitized_topology = False
        enabled = stored.get("enabled") or {}
        adapter_model = int(stored.get("adapter_device_model") or 0)
        self._requires_reassignment = {
            str(item) for item in (stored.get("requires_reassignment") or []) if str(item)
        }
        # Legacy per-sensor capture preferences are intentionally ignored.
        # The adapter Enable switch is the single module/capture control surface.

        # ANT+ and Bluetooth adapter devices are permanent Fitness infrastructure.
        # Their provider modules are loaded only when the user explicitly turns
        # on the adapter's Enable switch.  Migrating from the old config-flow
        # transport model therefore creates both adapters disabled.
        for name in TRANSPORTS:
            self._configured[name] = True
            self._enabled[name] = (
                bool(enabled.get(name, False))
                if adapter_model >= ADAPTER_DEVICE_MODEL_VERSION
                else False
            )

        # Restore physical identity aliases so one sensor stays one HA device
        # even when ANT+/BLE advertisements arrive in a different order.
        for item in stored.get("physical_sensors") or []:
            try:
                sensor = LiveSensor(
                    sensor_id=str(item["sensor_id"]),
                    name=str(item.get("name") or "Fitness sensor"),
                    capabilities=set(item.get("capabilities") or []),
                    metadata=dict(item.get("metadata") or {}),
                )
                for transport, raw in dict(item.get("endpoints") or {}).items():
                    raw_metadata = dict(raw.get("metadata") or {})
                    stable_metadata = self._stable_endpoint_metadata(
                        transport, raw_metadata, None
                    )
                    if stable_metadata != raw_metadata or raw.get("rssi") is not None:
                        sanitized_topology = True
                    endpoint = TransportEndpoint(
                        transport=transport,
                        endpoint_id=str(raw["endpoint_id"]),
                        address=raw.get("address"),
                        capabilities=set(raw.get("capabilities") or []),
                        source=raw.get("source"),
                        rssi=None,
                        available=False,
                        metadata=stable_metadata,
                    )
                    sensor.endpoints[transport] = endpoint
                    self.endpoint_aliases[endpoint.endpoint_id] = sensor.sensor_id
                stable_sensor_metadata = self._stable_sensor_metadata(sensor)
                if stable_sensor_metadata != sensor.metadata:
                    sensor.metadata = stable_sensor_metadata
                    sanitized_topology = True
                self.sensors[sensor.sensor_id] = sensor
            except Exception:
                continue

        self._initialized = True
        if sanitized_topology:
            self._schedule_save()
        if adapter_model < ADAPTER_DEVICE_MODEL_VERSION:
            # Persist the new disabled-by-default adapter model outside the
            # profile setup critical path.
            self._schedule_save()

    def _stable_sensor_metadata(self, sensor: LiveSensor) -> dict[str, Any]:
        """Return canonical sensor metadata without volatile endpoint payloads."""
        metadata = dict(sensor.metadata)
        transport_details = {}
        for transport, raw in dict(metadata.get("transport_details") or {}).items():
            endpoint = sensor.endpoints.get(str(transport))
            transport_details[str(transport)] = self._stable_endpoint_metadata(
                str(transport), dict(raw or {}), endpoint
            )
        if transport_details:
            metadata["transport_details"] = transport_details
        elif "transport_details" in metadata:
            metadata.pop("transport_details", None)
        return metadata

    def _serialize_sensors(self) -> list[dict[str, Any]]:
        result = []
        for sensor in self.sensors.values():
            result.append(
                {
                    "sensor_id": sensor.sensor_id,
                    "name": sensor.name,
                    "capabilities": sorted(sensor.capabilities),
                    "metadata": self._stable_sensor_metadata(sensor),
                    "endpoints": {
                        transport: {
                            "endpoint_id": endpoint.endpoint_id,
                            "address": endpoint.address,
                            "capabilities": sorted(endpoint.capabilities),
                            "source": endpoint.source,
                            "metadata": self._stable_endpoint_metadata(
                                transport, dict(endpoint.metadata), None
                            ),
                        }
                        for transport, endpoint in sensor.endpoints.items()
                    },
                }
            )
        return result

    async def _async_save_adapter_config(self) -> None:
        await self._store.async_save(
            {
                "configured": {name: True for name in TRANSPORTS},
                "enabled": dict(self._enabled),
                "adapter_device_model": ADAPTER_DEVICE_MODEL_VERSION,
                "physical_sensors": self._serialize_sensors(),
                "requires_reassignment": sorted(self._requires_reassignment),
            }
        )

    def _schedule_save(self) -> None:
        """Persist topology only after structural radio activity goes quiet."""
        self._save_pending = True
        if self._save_handle is not None:
            self._save_handle.cancel()

        def _flush() -> None:
            self._save_handle = None
            if not self._save_pending:
                return
            self._save_pending = False
            self.hass.async_create_background_task(
                self._async_save_adapter_config(),
                "fitness persist live sensor topology",
                eager_start=False,
            )

        # ANT common pages/capabilities arrive in bursts. Writing .storage while
        # that burst is still active is pure control-plane churn.
        self._save_handle = self.hass.loop.call_later(3.0, _flush)

    def adapter_present(self, transport: str) -> bool:
        """Return hardware/gateway presence independent of module enabled state."""
        return bool(self._adapter_presence.get(transport, False))

    @property
    def present_transports(self) -> set[str]:
        return {name for name in TRANSPORTS if self.adapter_present(name)}

    @property
    def adapter_entity_transports(self) -> set[str]:
        # Adapter entities are control-plane infrastructure, not a reflection of
        # momentary radio presence.  Keeping both configured adapters materialized
        # means a scanner appearing/disappearing never needs a config-entry reload
        # merely to create or remove an Enable switch/device.
        return self.configured_transports | self.present_transports

    @property
    def live_available(self) -> bool:
        """Whether at least one native live transport has usable HA-side hardware."""
        return bool(self.present_transports)

    def adapter_available(self, transport: str) -> bool:
        provider = self.providers.get(transport)
        if provider is not None:
            # Provider availability is authoritative once loaded, but keep the
            # lightweight presence detector as a fallback while it initializes.
            return bool(getattr(provider, "available", False) or self.adapter_present(transport))
        return self.adapter_present(transport)

    def set_adapter_presence(self, transport: str, present: bool) -> None:
        """Update hardware presence without changing the user's enable switch.

        Presence detection is control-plane only. A disabled module stays
        disabled across restart, disappearance/reappearance and proxy changes.
        No provider callbacks are registered until the user explicitly enables
        that transport.
        """
        if transport not in TRANSPORTS:
            return
        present = bool(present)
        old = self._adapter_presence.get(transport, False)
        if old == present:
            return
        self._adapter_presence[transport] = present

        # Presence is volatile runtime state.  Never turn a radio observation into
        # config-entry reload work: reloads rebuild platforms, registry listeners
        # and Bluetooth callbacks and can form a feedback loop when hardware/proxy
        # presence itself is changing.
        self._notify()

    async def _async_scan_local_ant_usb(self) -> bool:
        def _scan() -> bool:
            from pathlib import Path
            root = Path("/sys/bus/usb/devices")
            if not root.exists():
                return False
            for dev in root.iterdir():
                try:
                    vid = (dev / "idVendor").read_text().strip().lower()
                    pid = (dev / "idProduct").read_text().strip().lower()
                except (OSError, FileNotFoundError):
                    continue
                if (vid, pid) in {("0fcf", "1008"), ("0fcf", "1009")}:
                    return True
            return False
        return await self.hass.async_add_executor_job(_scan)

    def _bluetooth_scanner_present(self) -> bool:
        try:
            from homeassistant.components import bluetooth
            counter = getattr(bluetooth, "async_scanner_count", None)
            if counter is None:
                return bool(bluetooth.async_discovered_service_info(self.hass, False))
            try:
                # Fitness discovery consumes advertisements and does not require a
                # connectable GATT route.  Use the same definition as the provider.
                return bool(counter(self.hass, connectable=False))
            except TypeError:
                return bool(counter(self.hass))
        except Exception:
            return False

    async def async_refresh_adapter_presence(self) -> None:
        """Refresh cheap adapter presence without loading Fitness transport modules."""
        bt_provider = self.providers.get("bluetooth")
        bt = (
            bool(getattr(bt_provider, "available", False))
            if bt_provider is not None
            else self._bluetooth_scanner_present()
        )
        now = time.monotonic()
        self._remote_ant_last_seen = {
            gateway: seen
            for gateway, seen in self._remote_ant_last_seen.items()
            if now - seen <= 45.0
        }
        ant_provider = self.providers.get("antplus")
        adapter_manager = getattr(ant_provider, "adapter_manager", None)
        if adapter_manager is not None:
            # Once the ANT provider is loaded, its manager is the single source of
            # truth.  Do not perform a second /sys USB scan every ten seconds.
            ant = any(record.available for record in adapter_manager.records.values())
        else:
            local_ant = await self._async_scan_local_ant_usb()
            ant = local_ant or bool(self._remote_ant_last_seen)
        self.set_adapter_presence("bluetooth", bt)
        self.set_adapter_presence("antplus", ant)
        if self.live_available and self.hub_entry is None:
            await self.async_ensure_hub_for_presence()

    async def async_ensure_hub_for_presence(self) -> None:
        """Create the global hub in the background only after hardware exists."""
        if not self.live_available or self.hub_entry is not None:
            return
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
                self.hub_entry = entry
                return
        try:
            import importlib
            await self.hass.async_add_executor_job(
                importlib.import_module, "custom_components.fitness.config_flow"
            )
            await self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "integration_discovery"},
                data={"live_hub": True},
            )
        except Exception:
            _LOGGER.debug("Unable to create Sensors & Adapters discovery entry", exc_info=True)

    def ensure_profile_live_registry(self, entry) -> None:
        """Keep the per-profile Live Workout device as stable infrastructure.

        Radio availability and physical-sensor assignment are runtime state.  They
        must never create/delete the profile's HA device because device-registry
        churn can cascade into entity/platform reconciliation while ANT+/BLE is
        waking up.  Create the device once with the profile and leave it in place
        until the profile config entry itself is removed.
        """
        from homeassistant.helpers import device_registry as dr

        from ..entity import device_info

        info = device_info(entry, "live")
        registry = dr.async_get(self.hass)
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=info["identifiers"],
            manufacturer=info.get("manufacturer"),
            model=info.get("model"),
            name=info.get("name"),
            translation_key=info.get("translation_key"),
        )

    def _start_presence_monitor(self) -> None:
        """Start always-on lightweight radio presence detection after HA startup."""
        if self._presence_started:
            return
        self._presence_started = True

        @callback
        def _remote_alive(event) -> None:
            gateway = str(event.data.get("gateway_id", "unknown")).strip() or "unknown"
            self._remote_ant_last_seen[gateway] = time.monotonic()
            self.set_adapter_presence("antplus", True)
            if self.hub_entry is None and self.hass.state is CoreState.running:
                self.hass.async_create_background_task(
                    self.async_ensure_hub_for_presence(),
                    "fitness ensure Sensors & Adapters hub",
                )

        self._presence_unsubs.extend([
            self.hass.bus.async_listen("antplus_gateway_hello", _remote_alive),
            self.hass.bus.async_listen("antplus_gateway_status", _remote_alive),
        ])

        async def _poll() -> None:
            while True:
                try:
                    await self.async_refresh_adapter_presence()
                    self._expire_stale_sensor_endpoints()
                    # Discovery is sticky after the first fresh RF/BLE observation.
                    # Never abort/recreate discovery flows merely because a wearable
                    # goes quiet; that churn is unnecessary control-plane/UI work.
                    # Discovery is low-rate control-plane work. Retrying here means
                    # an RF device confirmed before profiles loaded, or a discovery
                    # flow that was dismissed/aborted, can become discoverable again
                    # without putting per-packet work back on Home Assistant's loop.
                    if self.profile_entries:
                        for sensor in tuple(self.sensors.values()):
                            if (
                                sensor.capabilities
                                and (
                                    bool(sensor.metadata.get("discovery_confirmed"))
                                    or (sensor.available and self.sensor_recently_observed(sensor.sensor_id))
                                )
                                and not self.sensor_is_accepted(sensor.sensor_id)
                            ):
                                self._schedule_sensor_discovery(sensor.sensor_id)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _LOGGER.debug(
                        "Fitness adapter presence refresh failed", exc_info=True
                    )
                await asyncio.sleep(10)

        @callback
        def _start_poll(_event=None) -> None:
            if self._presence_task is not None:
                return
            self._presence_task = self.hass.async_create_background_task(
                _poll(),
                "fitness adapter presence monitor",
            )

        if self.hass.state is CoreState.running:
            _start_poll()
        else:
            self._presence_unsubs.append(
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED,
                    _start_poll,
                )
            )

    def publish_passive(
        self,
        sensor_id: str,
        values: dict[str, Any],
        *,
        transport: str = "bluetooth",
        metadata: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Publish low-rate physical telemetry such as battery, merged by key."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        if sensor_id not in self.sensors or not values:
            return
        bucket = self.sensor_passive_values.setdefault(sensor_id, {})
        source_bucket = self.sensor_passive_sources.setdefault(sensor_id, {})
        changed_keys: set[str] = set()
        structure_changed = False
        for key, value in values.items():
            if key not in bucket:
                structure_changed = True
            per_source = source_bucket.setdefault(key, {})
            per_source[str(transport)] = value
            # ANT+ is preferred for live transport, but passive identity/health values
            # use the newest available semantic value and retain all source values.
            if bucket.get(key) != value:
                bucket[key] = value
                changed_keys.add(key)
        if metadata:
            meta = self.sensor_passive_meta.setdefault(sensor_id, {})
            for key, item in metadata.items():
                merged = dict(meta.get(key) or {})
                merged.update(dict(item))
                if meta.get(key) != merged:
                    meta[key] = merged
                    changed_keys.add(key)
        if changed_keys and self.sensor_is_accepted(sensor_id):
            if structure_changed:
                self._notify_structure_throttled()
            self._notify_values_throttled(
                {(sensor_id, "passive", key) for key in changed_keys}
            )

    def publish_details(
        self,
        sensor_id: str,
        values: dict[str, Any],
        *,
        transport: str,
        metadata: dict[str, dict[str, Any]] | None = None,
        priority: int = 10,
    ) -> None:
        """Publish non-core protocol/device information as merged HA entities."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        if sensor_id not in self.sensors or not values:
            return
        bucket = self.sensor_detail_values.setdefault(sensor_id, {})
        meta_bucket = self.sensor_detail_meta.setdefault(sensor_id, {})
        sources = self.sensor_detail_sources.setdefault(sensor_id, {})
        chosen = self.sensor_detail_source.setdefault(sensor_id, {})
        changed: set[str] = set()
        structure_changed = False
        for key, value in values.items():
            if value is None:
                continue
            if key not in bucket:
                structure_changed = True
            sources.setdefault(key, {})[str(transport)] = value
            current_meta = meta_bucket.setdefault(key, {})
            incoming_meta = dict((metadata or {}).get(key) or {})
            incoming_meta.setdefault("priority", int(priority))
            current_priority = int(current_meta.get("priority", -1))
            current_source = chosen.get(key)
            if current_source == transport or key not in bucket or int(priority) >= current_priority:
                if bucket.get(key) != value or current_source != transport:
                    bucket[key] = value
                    chosen[key] = str(transport)
                    changed.add(key)
                merged_meta = dict(current_meta)
                merged_meta.update(incoming_meta)
                meta_bucket[key] = merged_meta
            elif incoming_meta:
                # Keep richer presentation metadata even if another transport owns
                # the canonical value. Source values remain visible as attributes.
                merged_meta = dict(current_meta)
                for mk, mv in incoming_meta.items():
                    merged_meta.setdefault(mk, mv)
                meta_bucket[key] = merged_meta
        if self.sensor_is_accepted(sensor_id):
            if structure_changed:
                self._notify_structure_throttled()
            if changed:
                self._notify_values_throttled(
                    {(sensor_id, "detail", key) for key in changed}
                )

    def add_sensor_event_listener(self, sensor_id: str, event_key: str, listener):
        token = (self.resolve_sensor_id(sensor_id), str(event_key))
        listeners = self._sensor_event_listeners.setdefault(token, set())
        listeners.add(listener)
        def _remove() -> None:
            current = self._sensor_event_listeners.get(token)
            if current is None:
                return
            current.discard(listener)
            if not current:
                self._sensor_event_listeners.pop(token, None)
        return _remove

    def emit_sensor_event(self, sensor_id: str, event_key: str, event_type: str, data: dict[str, Any] | None = None) -> None:
        token = (self.resolve_sensor_id(sensor_id), str(event_key))
        for listener in tuple(self._sensor_event_listeners.get(token, ())):
            try:
                listener(str(event_type), dict(data or {}))
            except Exception:
                continue

    def _forget_sensor_memory(self, sensor_id: str) -> tuple[str, ...]:
        """Drop one physical sensor immediately and return affected profiles.

        Device deletion runs inside a Home Assistant websocket request. Keep this
        synchronous phase deliberately tiny: no config-entry updates, no subentry
        mutations, and no profile reloads are allowed here.
        """
        sensor_id = self.resolve_sensor_id(sensor_id)
        self._requires_reassignment.add(sensor_id)
        sensor = self.sensors.pop(sensor_id, None)
        if sensor is not None:
            quarantine_until = time.monotonic() + 5.0
            for endpoint in sensor.endpoints.values():
                self._rediscovery_quarantine_until[endpoint.endpoint_id] = quarantine_until
                if endpoint.transport == "antplus":
                    provider = self.providers.get("antplus")
                    forget = getattr(provider, "forget_device", None) if provider else None
                    if forget is not None:
                        try:
                            device_number = endpoint.metadata.get("device_number")
                            if device_number is None:
                                device_number = endpoint.address
                            forget(int(device_number))
                        except (TypeError, ValueError):
                            pass
                self.endpoint_aliases.pop(endpoint.endpoint_id, None)
        self.sensor_values.pop(sensor_id, None)
        self.sensor_value_transport.pop(sensor_id, None)
        self.sensor_passive_values.pop(sensor_id, None)
        self.sensor_passive_meta.pop(sensor_id, None)
        self.sensor_passive_sources.pop(sensor_id, None)
        self.sensor_detail_values.pop(sensor_id, None)
        self.sensor_detail_meta.pop(sensor_id, None)
        self.sensor_detail_sources.pop(sensor_id, None)
        self.sensor_detail_source.pop(sensor_id, None)
        self._discovery_started.discard(sensor_id)
        task = self._discovery_tasks.pop(sensor_id, None)
        if task is not None and not task.done():
            task.cancel()
        self._sensor_device_ids.pop(sensor_id, None)
        self._sensor_device_signatures.pop(sensor_id, None)
        for provider in tuple(self.providers.values()):
            callback_fn = getattr(provider, "sensor_acceptance_changed", None)
            if callback_fn is not None:
                callback_fn(sensor_id, False)
        # Do not rescan entity platforms while Home Assistant is still inside
        # the device-delete websocket transaction. Background cleanup emits one
        # deferred structure refresh after registry removal has settled.

        affected: list[str] = []
        for entry in tuple(self.profile_entries.values()):
            ids = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
            if any(self.resolve_sensor_id(str(item)) == sensor_id for item in ids):
                affected.append(entry.entry_id)
        return tuple(affected)

    def _schedule_deleted_sensor_cleanup(
        self, sensor_id: str, profile_entry_ids: tuple[str, ...]
    ) -> None:
        """Persist deletion fallout without reloading Fitness config entries.

        A physical-device delete originates from Home Assistant's device-registry
        transaction.  Reloading either the owning profile or the Sensors & Adapters
        hub from that path is disproportionately expensive: it tears down entity
        platforms and radio providers while the device registry is still settling.
        Keep deletion as a bounded control-plane operation instead.
        """

        async def _cleanup() -> None:
            # Let Home Assistant finish the device-registry delete transaction
            # before persisting profile assignment changes.
            await asyncio.sleep(0.75)
            changed_entries: list[str] = []
            for entry_id in profile_entry_ids:
                entry = self.hass.config_entries.async_get_entry(entry_id)
                if entry is None:
                    continue
                ids = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
                kept = [
                    item
                    for item in ids
                    if self.resolve_sensor_id(str(item)) != sensor_id
                ]
                if kept == ids:
                    continue
                options = dict(entry.options)
                options[CONF_LIVE_SENSOR_IDS] = kept

                # The ConfigEntry object is updated in place, so FitnessManager.config
                # and LiveRuntime.selected_sensor_ids() immediately see the new
                # assignment.  Suppress the normal update-listener reload: deleting
                # one radio sensor must never unload/reload a whole profile.
                if getattr(getattr(entry, "state", None), "value", None) == "loaded":
                    self.suppress_entry_reload_once(entry_id)
                self.hass.config_entries.async_update_entry(entry, options=options)
                changed_entries.append(entry_id)

                # Reconcile any live transport ownership asynchronously.  In the
                # common idle case this is a no-op; if the sensor was in use, this
                # releases only the affected transport/session state without a
                # config-entry teardown.
                current = self.profile_entries.get(entry_id)
                if current is not None:
                    try:
                        await self._reconcile_profile_transports(current)
                    except Exception:
                        _LOGGER.debug(
                            "Unable to reconcile profile %s after deleting sensor %s",
                            entry_id,
                            sensor_id,
                            exc_info=True,
                        )

            # Refresh stable Live calculations/controls in place. No profile entity
            # or device is created/removed as a consequence of this routing change.
            for entry_id in changed_entries:
                manager = self.hass.data.get(DOMAIN, {}).get(entry_id)
                if manager is not None:
                    manager._notify_live()

            # The Sensors subentry is stable infrastructure once created.  Do not
            # add/remove config subentries or emit a broad structure refresh from a
            # device-delete path; Home Assistant already removed this device and its
            # entities as part of the user's delete request.

        self.hass.async_create_background_task(
            _cleanup(),
            f"fitness cleanup deleted live sensor {sensor_id}",
            eager_start=False,
        )

    def forget_sensor(self, sensor_id: str) -> None:
        """Forget a sensor and require discovery/assignment before recreation."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        affected = self._forget_sensor_memory(sensor_id)
        self._schedule_save()
        self._schedule_deleted_sensor_cleanup(sensor_id, affected)

    async def async_forget_sensor(self, sensor_id: str) -> None:
        """Revoke immediately, then persist/clean up outside the HA delete request."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        affected = self._forget_sensor_memory(sensor_id)
        # The in-memory tombstone and endpoint quarantine prevent immediate
        # resurrection. Persist only after HA can finish the websocket request.
        self._schedule_save()
        self._schedule_deleted_sensor_cleanup(sensor_id, affected)
        await asyncio.sleep(0)

    def _listen_for_registry_deletions(self) -> None:
        if self._device_registry_unsub is not None:
            return
        try:
            from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
        except ImportError:
            return
        @callback
        def _changed(event) -> None:
            if event.data.get("action") != "remove":
                return
            device_id = str(event.data.get("device_id", ""))
            for sensor_id, known_device_id in tuple(self._sensor_device_ids.items()):
                if known_device_id == device_id:
                    self._sensor_device_ids.pop(sensor_id, None)
                    self._sensor_device_signatures.pop(sensor_id, None)
                    self.forget_sensor(sensor_id)
                    return
            # Logical adapters/receivers are rediscovered by the next actual
            # hardware presence tick / ANT adapter update, not immediately just
            # because the user deleted a registry device.
        self._device_registry_unsub = self.hass.bus.async_listen(
            EVENT_DEVICE_REGISTRY_UPDATED, _changed
        )

    async def async_ensure_hub_entry(self):
        """Return the Local Sensors entry if it already exists.

        Config entries are created only from an explicit setup/options flow.
        Runtime/startup code must never launch a config flow.
        """
        if self.hub_entry is not None:
            return self.hub_entry

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
                self.hub_entry = entry
                return entry

        return None

    async def async_register_hub(self, entry) -> None:
        await self.async_initialize()
        if self._stall_watchdog is None:
            from .stall_watchdog import FitnessEventLoopWatchdog

            self._stall_watchdog = FitnessEventLoopWatchdog(self.hass)
            self._stall_watchdog.start()
        self.hub_entry = entry
        self._start_presence_monitor()
        self._listen_for_registry_deletions()
        self._cleanup_legacy_profile_infrastructure()
        self._cleanup_obsolete_hub_capture_entities()
        self.ensure_transport_subentry("antplus")
        self.ensure_transport_subentry("bluetooth")
        # Sensors is permanent hub infrastructure, not a reflection of the
        # current sensor count.  Create it once during hub setup so radio
        # discovery never has to mutate config-entry structure.
        self.ensure_sensors_subentry()
        self._remove_legacy_grouping_devices()
        self._migrate_adapter_devices_to_transport_subentries()
        self._remove_legacy_adapters_subentry_if_empty()
        self.ensure_ant_receiver_topology()
        for sensor_id in tuple(self.sensors):
            if self.sensor_is_accepted(sensor_id):
                self.ensure_sensor_device(sensor_id)
            else:
                self.remove_unaccepted_sensor_device(sensor_id)

        # Radio/proxy discovery must never delay Home Assistant startup.  The
        # adapter entities can be created immediately from persisted config;
        # provider hardware initialization happens as a background job.
        self.hass.async_create_task(self._async_start_hub_modules())

    def _cleanup_legacy_profile_infrastructure(self) -> None:
        """Remove prototype adapter/sensor registry objects owned by person entries."""
        if self.hub_entry is None:
            return
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        profile_ids = {entry.entry_id for entry in self.profile_entries.values()}
        # Profiles may not be registered yet when the hub loads first. Include all
        # non-hub Fitness config entries so migration works regardless of load order.
        profile_ids.update(
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id != self.hub_entry.entry_id
            and entry.data.get("entry_type") != HUB_ENTRY_TYPE
        )

        for entity in list(entity_registry.entities.values()):
            if entity.platform != DOMAIN or entity.config_entry_id not in profile_ids:
                continue
            uid = str(entity.unique_id or "")
            if (
                uid.startswith("fitness_bluetooth_")
                or uid.startswith("fitness_antplus_")
                or "bluetooth:" in uid and uid.endswith("_available")
                or "antplus:" in uid and uid.endswith("_available")
                or uid.endswith("_bluetooth_start_capture")
                or uid.endswith("_bluetooth_stop_capture")
                or uid.endswith("_bluetooth_capture_active")
                or uid.endswith("_antplus_start_capture")
                or uid.endswith("_antplus_stop_capture")
                or uid.endswith("_antplus_capture_active")
            ):
                entity_registry.async_remove(entity.entity_id)

        for device in list(device_registry.devices.values()):
            if device.config_entry_id not in profile_ids:
                continue
            identifiers = {identifier for domain, identifier in device.identifiers if domain == DOMAIN}
            if any(
                identifier.startswith("live_adapter:")
                or identifier.startswith("live_sensor:")
                for identifier in identifiers
            ):
                device_registry.async_remove_device(device.id)

    def _cleanup_obsolete_hub_capture_entities(self) -> None:
        """Remove retired capture entities from the Sensors & Adapters entry."""
        if self.hub_entry is None:
            return
        from homeassistant.helpers import entity_registry as er

        registry = er.async_get(self.hass)
        suffixes = (
            "_bluetooth_start_capture",
            "_bluetooth_stop_capture",
            "_bluetooth_capture_active",
            "_antplus_start_capture",
            "_antplus_stop_capture",
            "_antplus_capture_active",
            "_gatt_connect",
            "_gatt_disconnect",
        )
        exact = {
            "fitness_bluetooth_capture_active",
            "fitness_antplus_capture_active",
        }
        for entity in list(registry.entities.values()):
            if entity.platform != DOMAIN or entity.config_entry_id != self.hub_entry.entry_id:
                continue
            uid = str(entity.unique_id or "")
            if uid in exact or uid.endswith(suffixes):
                registry.async_remove(entity.entity_id)

    async def _async_start_hub_modules(self) -> None:
        """Start enabled live providers outside config-entry startup."""
        try:
            await self.async_refresh_modules()
            ant_provider = self.providers.get("antplus")
            if ant_provider is not None and self.hub_entry is not None:
                await ant_provider.async_bind_hub(self.hub_entry)
        except Exception:
            _LOGGER.exception("Fitness live provider background startup failed")

    async def async_unregister_hub(self, entry_id: str) -> None:
        if self.hub_entry is not None and self.hub_entry.entry_id == entry_id:
            if self._stall_watchdog is not None:
                self._stall_watchdog.stop()
                self._stall_watchdog = None
            self.hub_entry = None
            self.sensors_subentry_id = None
            self.antplus_subentry_id = None
            self.bluetooth_subentry_id = None

    def ensure_transport_subentry(self, transport: str):
        """Ensure one protocol-specific adapter subentry exists."""
        if self.hub_entry is None:
            return None
        if transport == "antplus":
            subtype = ANTPLUS_SUBENTRY_TYPE
            unique_id = ANTPLUS_SUBENTRY_UNIQUE_ID
            title = "ANT+"
            attr = "antplus_subentry_id"
        elif transport == "bluetooth":
            subtype = BLUETOOTH_SUBENTRY_TYPE
            unique_id = BLUETOOTH_SUBENTRY_UNIQUE_ID
            title = "Bluetooth"
            attr = "bluetooth_subentry_id"
        else:
            raise ValueError(f"Unsupported Fitness transport subentry: {transport}")

        for subentry in self.hub_entry.subentries.values():
            if subentry.subentry_type == subtype or subentry.unique_id == unique_id:
                setattr(self, attr, subentry.subentry_id)
                if subentry.title != title:
                    self.hass.config_entries.async_update_subentry(
                        self.hub_entry, subentry, title=title
                    )
                return subentry

        subentry = ConfigSubentry(
            data=MappingProxyType({}),
            subentry_type=subtype,
            title=title,
            unique_id=unique_id,
        )
        self.hass.config_entries.async_add_subentry(self.hub_entry, subentry)
        setattr(self, attr, subentry.subentry_id)
        return subentry

    def adapter_subentry_id(self, transport: str) -> str | None:
        if transport == "antplus":
            if self.antplus_subentry_id:
                return self.antplus_subentry_id
        elif transport == "bluetooth":
            if self.bluetooth_subentry_id:
                return self.bluetooth_subentry_id
        subentry = self.ensure_transport_subentry(transport)
        return subentry.subentry_id if subentry is not None else None

    def _remove_legacy_adapters_subentry_if_empty(self) -> None:
        """Drop the old shared Adapters group after migrating its devices."""
        if self.hub_entry is None:
            return
        target = None
        for subentry in self.hub_entry.subentries.values():
            if (
                subentry.subentry_type == LEGACY_ADAPTERS_SUBENTRY_TYPE
                or subentry.unique_id == LEGACY_ADAPTERS_SUBENTRY_UNIQUE_ID
            ):
                target = subentry
                break
        if target is None:
            return
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        if any(
            device.config_entry_id == self.hub_entry.entry_id
            and device.config_subentry_id == target.subentry_id
            for device in registry.devices.values()
        ):
            return
        self.hass.config_entries.async_remove_subentry(
            self.hub_entry, target.subentry_id
        )

    def ensure_sensors_subentry(self):
        """Ensure the physical-sensor config subentry exists on the hub entry."""
        if self.hub_entry is None:
            return None

        for subentry in self.hub_entry.subentries.values():
            if (
                subentry.subentry_type == SENSORS_SUBENTRY_TYPE
                or subentry.unique_id == SENSORS_SUBENTRY_UNIQUE_ID
            ):
                self.sensors_subentry_id = subentry.subentry_id
                if subentry.title != "Sensors":
                    self.hass.config_entries.async_update_subentry(
                        self.hub_entry, subentry, title="Sensors"
                    )
                return subentry

        subentry = ConfigSubentry(
            data=MappingProxyType({}),
            subentry_type=SENSORS_SUBENTRY_TYPE,
            title="Sensors",
            unique_id=SENSORS_SUBENTRY_UNIQUE_ID,
        )
        self.hass.config_entries.async_add_subentry(self.hub_entry, subentry)
        self.sensors_subentry_id = subentry.subentry_id
        return subentry

    def _remove_legacy_grouping_devices(self) -> None:
        """Remove obsolete fake grouping devices; config subentries replace them."""
        if self.hub_entry is None:
            return
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        for identifier in (HUB_DEVICE_ID, SENSOR_COLLECTION_DEVICE_ID):
            device = registry.async_get_device_by_identifier(
                (DOMAIN, identifier), self.hub_entry.entry_id
            )
            if device is not None:
                registry.async_remove_device(device.id)

    def _migrate_adapter_devices_to_transport_subentries(self) -> None:
        """Move logical adapters and ANT receivers into protocol groups."""
        if self.hub_entry is None:
            return
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        for transport in TRANSPORTS:
            subentry_id = self.adapter_subentry_id(transport)
            device = registry.async_get_device_by_identifier(
                (DOMAIN, f"live_adapter:{transport}"), self.hub_entry.entry_id
            )
            if device is not None and device.config_subentry_id != subentry_id:
                registry.async_update_device(
                    device.id,
                    new_config_subentry_id=subentry_id,
                    via_device_id=None,
                )

        ant_subentry_id = self.adapter_subentry_id("antplus")
        ant_parent = registry.async_get_device_by_identifier(
            (DOMAIN, "live_adapter:antplus"), self.hub_entry.entry_id
        )
        for device in list(registry.devices.values()):
            if device.config_entry_id != self.hub_entry.entry_id:
                continue
            is_ant_receiver = any(
                domain == DOMAIN and str(identifier).startswith("usb_adapter:")
                for domain, identifier in device.identifiers
            )
            if not is_ant_receiver:
                continue
            kwargs = {}
            if ant_subentry_id is not None and device.config_subentry_id != ant_subentry_id:
                kwargs["new_config_subentry_id"] = ant_subentry_id
            if ant_parent is not None and device.via_device_id != ant_parent.id:
                kwargs["via_device_id"] = ant_parent.id
            if kwargs:
                registry.async_update_device(device.id, **kwargs)

    def _sensor_subentry_id(self) -> str | None:
        if self.sensors_subentry_id:
            return self.sensors_subentry_id
        subentry = self.ensure_sensors_subentry()
        return subentry.subentry_id if subentry is not None else None


    def ensure_ant_receiver_topology(self) -> None:
        """Put every physical ANT receiver under the logical ANT+ Adapter.

        The ANT adapter manager may discover/register USB or remote receivers
        before the logical adapter entity has created its HA device.  Reconcile
        the relationship whenever the parent becomes available so receivers can
        never remain as root-level devices.
        """
        if self.hub_entry is None:
            return
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        parent = registry.async_get_device_by_identifier(
            (DOMAIN, "live_adapter:antplus"), self.hub_entry.entry_id
        )
        if parent is None:
            return
        subentry_id = self.adapter_subentry_id("antplus")
        for device in list(registry.devices.values()):
            if device.config_entry_id != self.hub_entry.entry_id:
                continue
            is_receiver = any(
                domain == DOMAIN and str(identifier).startswith("usb_adapter:")
                for domain, identifier in device.identifiers
            )
            if not is_receiver or device.id == parent.id:
                continue
            kwargs = {}
            if device.via_device_id != parent.id:
                kwargs["via_device_id"] = parent.id
            if subentry_id is not None and device.config_subentry_id != subentry_id:
                kwargs["new_config_subentry_id"] = subentry_id
            if kwargs:
                registry.async_update_device(device.id, **kwargs)

    def ant_receiver_records(self) -> dict[str, Any]:
        provider = self.providers.get("antplus")
        manager = getattr(provider, "adapter_manager", None) if provider else None
        return dict(getattr(manager, "records", {}) or {})

    def ant_receiver_device_info(self, stable_key: str):
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers.device_registry import DeviceInfo
        record = self.ant_receiver_records().get(stable_key)
        parent_id = None
        if self.hub_entry is not None:
            parent = dr.async_get(self.hass).async_get_device_by_identifier(
                (DOMAIN, "live_adapter:antplus"), self.hub_entry.entry_id
            )
            if parent is not None:
                parent_id = parent.id
        common = {"via_device_id": parent_id} if parent_id else {}
        if record is None:
            return DeviceInfo(
                identifiers={(DOMAIN, f"usb_adapter:{stable_key}")},
                name=stable_key,
                manufacturer="ANT+",
                model="ANT+ receiver",
                **common,
            )
        adapter = record.adapter
        return DeviceInfo(
            identifiers={adapter.ha_identifier},
            name=adapter.name,
            manufacturer=adapter.manufacturer or "ANT+",
            model=adapter.product or f"ANT USB {adapter.vid}:{adapter.pid}",
            serial_number=adapter.serial,
            **common,
        )

    def adapter_device_info(self, transport: str):
        from homeassistant.helpers.device_registry import DeviceInfo
        label = "ANT+ Adapter" if transport == "antplus" else "Bluetooth Adapter"
        # Home Assistant 2026.8 classifies DeviceInfo into strict primary/link/
        # secondary shapes. Primary devices may use identifiers + name/model,
        # but must not mix in translation/default_* fields.
        return DeviceInfo(
            identifiers={(DOMAIN, f"live_adapter:{transport}")},
            name=label,
            manufacturer="Fitness",
            model=label,
        )

    def sensor_device_info(self, sensor_id: str):
        """Return one valid HA primary DeviceInfo for the merged physical sensor."""
        from homeassistant.helpers.device_registry import DeviceInfo
        resolved_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(resolved_id)
        if sensor is None:
            return DeviceInfo(
                identifiers={(DOMAIN, f"live_sensor:{resolved_id}")},
                name="Fitness sensor",
            )

        identifiers = {(DOMAIN, f"live_sensor:{sensor.sensor_id}")}
        for endpoint in sensor.endpoints.values():
            identifiers.add((DOMAIN, f"endpoint:{endpoint.endpoint_id}"))

        identity = resolve_identity(sensor)
        info = {
            "identifiers": identifiers,
            # Use a stable primary-device name even before catalog/GATT identity
            # is complete. Numeric protocol IDs remain diagnostics, never names.
            "name": identity.get("name") or sensor.name or "Fitness sensor",
        }
        if identity.get("ready"):
            info.update(
                manufacturer=identity.get("manufacturer"),
                model=identity.get("model"),
                model_id=identity.get("model_id"),
                serial_number=identity.get("serial_number"),
                hw_version=identity.get("hw_version"),
                sw_version=identity.get("sw_version"),
            )
        return DeviceInfo(**{k: v for k, v in info.items() if v not in (None, "")})

    def sensor_identity(self, sensor_id: str) -> dict[str, Any]:
        sensor = self.sensors.get(self.resolve_sensor_id(sensor_id))
        return resolve_identity(sensor) if sensor is not None else {"name": "Fitness sensor", "ready": False}

    def adapter_configured(self, transport: str) -> bool:
        return bool(self._configured.get(transport, False))

    def adapter_enabled(self, transport: str) -> bool:
        return bool(self._enabled.get(transport, False))

    @property
    def configured_transports(self) -> set[str]:
        return {name for name in TRANSPORTS if self.adapter_configured(name)}

    async def async_configure_transport(self, transport: str, *, enabled: bool = False) -> None:
        if transport not in TRANSPORTS:
            raise ValueError(f"Unsupported Fitness live transport: {transport}")
        await self.async_initialize()
        self._configured[transport] = True
        self._enabled[transport] = bool(enabled)
        await self._async_save_adapter_config()
        await self.async_ensure_hub_entry()
        await self.async_refresh_modules()
        self.request_hub_reload()

    def _mark_transport_runtime_inactive(self, transport: str) -> None:
        """Drop volatile runtime state when an adapter module is disabled.

        Device identity/topology is retained, but no stale endpoint is left
        looking live and no profile continues to source metrics from the
        disabled module.
        """
        dirty: set[tuple[str, str, str | None]] = set()
        for sensor in self.sensors.values():
            endpoint = sensor.endpoints.get(transport)
            if endpoint is None:
                continue
            if endpoint.available:
                endpoint.available = False
                dirty.add((sensor.sensor_id, "available", transport))
            for profile_id, sources in self.measurement_sources.items():
                values = self.measurements.setdefault(profile_id, {})
                removed = False
                for metric, source_id in tuple(sources.items()):
                    if (
                        self.resolve_sensor_id(source_id) == sensor.sensor_id
                        and self._profile_sensor_transport.get(profile_id, {}).get(sensor.sensor_id) == transport
                    ):
                        sources.pop(metric, None)
                        values.pop(metric, None)
                        removed = True
                if removed:
                    self.measurement_time.pop(profile_id, None)
                    manager = self._manager_for_profile(profile_id)
                    if manager is not None:
                        self._notify_profile_live_throttled(profile_id, manager)
        for profile_map in self._profile_sensor_transport.values():
            for sensor_id, selected in tuple(profile_map.items()):
                if selected == transport:
                    profile_map.pop(sensor_id, None)
        if dirty:
            self._notify_values_throttled(dirty)

    async def async_set_transport_enabled(self, transport: str, enabled: bool) -> None:
        if not self.adapter_configured(transport):
            if not enabled:
                return
            self._configured[transport] = True
        requested = bool(enabled)
        if self._enabled.get(transport, False) == requested:
            return
        self._enabled[transport] = requested
        await self._async_save_adapter_config()
        if requested:
            await self.async_ensure_hub_entry()
        await self.async_refresh_modules()
        if not requested:
            self._mark_transport_runtime_inactive(transport)
        self._notify()

    async def async_register_profile(self, entry) -> None:
        await self.async_initialize()
        self.profile_entries[entry.entry_id] = entry
        self._start_presence_monitor()
        self._listen_for_registry_deletions()
        self._restore_legacy_profile_selections(entry)
        # A radio device can be confirmed before the first person profile has
        # finished registering. Discovery is assignment-driven, so once a profile
        # exists, surface every currently observed unaccepted physical sensor.
        for sensor in tuple(self.sensors.values()):
            if sensor.capabilities and not self.sensor_is_accepted(sensor.sensor_id):
                self._schedule_sensor_discovery(sensor.sensor_id)
        # Person/profile entries never start radio providers. Live transports
        # are owned exclusively by the Local Sensors hub entry.

    def _restore_legacy_profile_selections(self, entry) -> None:
        """Map prototype transport IDs to physical sensors during first v2 load."""
        raw_ids = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
        for raw_id in raw_ids:
            raw_id = str(raw_id)
            if raw_id in self.sensors or raw_id in self.endpoint_aliases:
                continue
            if raw_id.startswith("bluetooth:"):
                address = raw_id.split(":", 1)[1]
                self.register_transport_sensor(
                    transport="bluetooth",
                    endpoint_id=raw_id,
                    name=address,
                    capabilities=set(),
                    address=address,
                    available=False,
                    metadata={"migrated_selection": True},
                )
            elif raw_id.startswith("antplus:"):
                device_number = raw_id.split(":", 1)[1]
                self.register_transport_sensor(
                    transport="antplus",
                    endpoint_id=raw_id,
                    name=f"ANT+ {device_number}",
                    capabilities=set(),
                    address=device_number,
                    available=False,
                    metadata={"device_number": device_number, "migrated_selection": True},
                )

    async def async_unregister_profile(self, entry_id: str) -> None:
        entry = self.profile_entries.get(entry_id)
        if entry is not None:
            await self.async_finish_session(entry, keep_heart_rate=False)
        self.profile_entries.pop(entry_id, None)
        self.measurements.pop(entry_id, None)
        self.measurement_sources.pop(entry_id, None)
        self.measurement_time.pop(entry_id, None)
        handle = self._profile_live_notify_handles.pop(entry_id, None)
        if handle is not None:
            handle.cancel()
        self._profile_last_live_notify_monotonic.pop(entry_id, None)

    async def async_refresh_modules(self) -> None:
        if not self._initialized:
            return
        wanted = {name: self.adapter_enabled(name) for name in TRANSPORTS}
        if wanted["bluetooth"] and "bluetooth" not in self.providers:
            from .bluetooth import BluetoothFitnessProvider
            provider = BluetoothFitnessProvider(self)
            self.providers["bluetooth"] = provider
            await provider.async_setup()
        if wanted["antplus"]:
            provider = self.providers.get("antplus")
            if provider is None:
                from .antplus import AntPlusFitnessProvider
                provider = AntPlusFitnessProvider(self)
                self.providers["antplus"] = provider
                await provider.async_setup()
            if self.hub_entry is not None:
                await provider.async_bind_hub(self.hub_entry)
        for name in tuple(self.providers):
            if not wanted.get(name, False):
                await self.providers.pop(name).async_shutdown()
                self._transport_claims.pop(name, None)

    async def async_begin_setup_discovery(self) -> None:
        """Prepare discovery without mutating adapter state.

        The adapter Activate switch is the only transport/module control.
        Enabled providers already listen for passive ANT+/BLE discovery.
        """
        await self.async_initialize()

    async def async_end_setup_discovery(self) -> None:
        """Discovery never owns or changes adapter/provider state."""
        return

    @property
    def live_enabled(self) -> bool:
        return any(self.adapter_enabled(name) for name in TRANSPORTS)

    @property
    def live_surface_available(self) -> bool:
        return self.live_available

    def transport_in_use(self, transport: str) -> bool:
        return bool(self._transport_claims.get(transport))

    def add_listener(self, listener):
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def add_sensor_value_listener(
        self,
        sensor_id: str,
        kind: str,
        key: str | None,
        listener,
    ):
        """Listen only for one physical sensor value/status key."""
        token = (self.resolve_sensor_id(sensor_id), str(kind), key)
        listeners = self._sensor_value_listeners.setdefault(token, set())
        listeners.add(listener)

        def _remove() -> None:
            current = self._sensor_value_listeners.get(token)
            if current is None:
                return
            current.discard(listener)
            if not current:
                self._sensor_value_listeners.pop(token, None)

        return _remove

    def add_structure_listener(self, listener):
        """Listen only for sensor/device topology changes, not live measurements."""
        self._structure_listeners.add(listener)
        return lambda: self._structure_listeners.discard(listener)

    def _notify_structure(self) -> None:
        for listener in tuple(self._structure_listeners):
            try:
                listener()
            except Exception:
                continue

    def _notify_structure_throttled(self) -> None:
        """Coalesce radio-driven topology/entity materialization bursts.

        Accepting or enriching one sensor can reveal identity, passive values and
        protocol diagnostics in the same event-loop turn. One deferred structure
        notification prevents every observation from rescanning all entity
        platforms/device registries independently.
        """
        if self._structure_notify_handle is not None:
            self._structure_notify_handle.cancel()

        def _flush() -> None:
            self._structure_notify_handle = None
            self._notify_structure()

        # Entity/platform materialization is delayed until the latest radio
        # schema/identity burst has been quiet for two seconds.
        self._structure_notify_handle = self.hass.loop.call_later(2.0, _flush)

    def suppress_entry_reload_once(self, entry_id: str) -> None:
        self._suppress_entry_reload_once.add(str(entry_id))

    def consume_entry_reload_suppression(self, entry_id: str) -> bool:
        entry_id = str(entry_id)
        if entry_id not in self._suppress_entry_reload_once:
            return False
        self._suppress_entry_reload_once.discard(entry_id)
        return True

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                continue

    def _notify_sensor_value_changes(
        self, changes: set[tuple[str, str, str | None]]
    ) -> None:
        """Notify only entities whose physical sensor value actually changed."""
        callbacks: set[Any] = set()
        for token in changes:
            callbacks.update(self._sensor_value_listeners.get(token, ()))
        for listener in tuple(callbacks):
            try:
                listener()
            except Exception:
                continue

    def _notify_values_throttled(
        self, changes: set[tuple[str, str, str | None]]
    ) -> None:
        """Coalesce changed physical hardware entities to at most 1 Hz.

        Workout-profile live publishing has its own faster path. Physical device
        pages do not need radio-rate state writes.
        Unlike the old implementation this never fans one radio packet out to
        every runtime entity. Only exact dirty sensor/value keys are published.
        """
        if not changes:
            return
        self._pending_sensor_value_changes.update(changes)
        now = self.hass.loop.time()
        elapsed = now - self._last_value_notify_monotonic

        def _flush() -> None:
            self._value_notify_handle = None
            self._last_value_notify_monotonic = self.hass.loop.time()
            pending = set(self._pending_sensor_value_changes)
            self._pending_sensor_value_changes.clear()
            if pending:
                self._notify_sensor_value_changes(pending)

        if elapsed >= 1.0 and self._value_notify_handle is None:
            _flush()
            return
        if self._value_notify_handle is not None:
            return
        delay = max(0.0, 1.0 - elapsed)
        self._value_notify_handle = self.hass.loop.call_later(delay, _flush)

    def _mark_last_seen_change(
        self, sensor_id: str, seen: datetime | None
    ) -> set[tuple[str, str, str | None]]:
        """Return a dirty Last seen key only when its one-minute bucket changes."""
        if seen is None:
            bucket = None
        else:
            # Physical radios can report several packets per second.  Keep the
            # precise timestamp in memory, but expose it to HA at most once per
            # minute so every accepted sensor stays visibly fresh without
            # packet-rate Recorder/state churn.
            bucket = seen.replace(second=0, microsecond=0)
        previous = self._last_seen_notify_bucket.get(sensor_id)
        if previous == bucket:
            return set()
        self._last_seen_notify_bucket[sensor_id] = bucket
        return {(sensor_id, "last_seen", None)}

    def _set_active_transport(
        self, sensor: LiveSensor, transport: str | None
    ) -> None:
        if sensor.active_transport == transport:
            return
        sensor.active_transport = transport
        changes = {
            (sensor.sensor_id, "active_transport", None),
            (sensor.sensor_id, "availability", None),
        }
        self._notify_values_throttled(changes)

    def _notify_profile_live_throttled(self, entry_id: str, manager) -> None:
        """Run one profile live-workout hot path at most twice per second."""
        now = self.hass.loop.time()
        last = self._profile_last_live_notify_monotonic.get(entry_id, 0.0)
        elapsed = now - last

        def _flush() -> None:
            self._profile_live_notify_handles.pop(entry_id, None)
            self._profile_last_live_notify_monotonic[entry_id] = self.hass.loop.time()
            current = self.hass.data.get(DOMAIN, {}).get(entry_id)
            if current is None or (
                not current.session_armed
                and not current.session_active
                and not getattr(current, "recovery_active", False)
            ):
                return
            current._async_live_source_change(None)

        if elapsed >= 0.5 and entry_id not in self._profile_live_notify_handles:
            _flush()
            return
        if entry_id in self._profile_live_notify_handles:
            return
        delay = max(0.0, 0.5 - elapsed)
        self._profile_live_notify_handles[entry_id] = self.hass.loop.call_later(
            delay, _flush
        )

    def notify_changed(self) -> None:
        """Notify adapter/sensor entities after an explicit runtime state change."""
        self._notify()

    def _new_physical_id(self, endpoint_id: str) -> str:
        digest = hashlib.sha1(endpoint_id.encode("utf-8")).hexdigest()[:16]
        return f"sensor:{digest}"

    def resolve_sensor_id(self, sensor_id: str) -> str:
        """Resolve merge aliases transitively and compress stale alias chains."""
        current = str(sensor_id)
        visited: list[str] = []
        seen: set[str] = set()
        while current not in seen:
            seen.add(current)
            target = self.endpoint_aliases.get(current)
            if target is None:
                break
            target = str(target)
            if target == current:
                break
            visited.append(current)
            current = target
        for alias in visited:
            self.endpoint_aliases[alias] = current
        return current

    def _select_merge_primary(self, a: LiveSensor, b: LiveSensor) -> tuple[LiveSensor, LiveSensor]:
        if bool(a.metadata.get("accepted")) != bool(b.metadata.get("accepted")):
            return (a, b) if a.metadata.get("accepted") else (b, a)
        if ("antplus" in a.endpoints) != ("antplus" in b.endpoints):
            return (a, b) if "antplus" in a.endpoints else (b, a)
        return a, b

    def _migrate_workout_state_for_sensor_merge(
        self, primary_id: str, secondary_id: str
    ) -> None:
        """Move exclusive workout/runtime state onto a newly merged sensor ID.

        ANT and BLE identities can become mergeable only after later Device
        Information arrives. If either provisional identity was already locked,
        that lock must survive the merge. In the pathological case where both
        provisional IDs were independently locked to different profiles before
        the identity proof arrived, the older session wins and the losing
        profile is disconnected from this physical sensor on the next reconcile.
        """
        primary_id = self.resolve_sensor_id(primary_id)
        # secondary_id may already alias to primary by the time this helper is
        # called, so read both raw keys before relying on resolve_sensor_id().
        owner_primary = self._sensor_workout_owner.pop(primary_id, None)
        owner_secondary = self._sensor_workout_owner.pop(secondary_id, None)
        owners = {owner for owner in (owner_primary, owner_secondary) if owner}
        winner = None
        if owners:
            winner = min(
                owners,
                key=lambda entry_id: (
                    self._profile_session_order.get(entry_id, 10**12),
                    entry_id,
                ),
            )
            self._sensor_workout_owner[primary_id] = winner

        affected_profiles: set[str] = set()
        for entry_id, claimed in self._profile_claimed_sensors.items():
            if primary_id in claimed or secondary_id in claimed:
                affected_profiles.add(entry_id)
            claimed.discard(primary_id)
            claimed.discard(secondary_id)
        if winner is not None:
            self._profile_claimed_sensors.setdefault(winner, set()).add(primary_id)
            affected_profiles.update(owners)

        # Preserve enough stale transport state for a losing profile's reconcile
        # to actively disconnect GATT/capture ownership instead of silently
        # forgetting it. The winning profile gets the canonical key.
        for entry_id, chosen in self._profile_sensor_transport.items():
            primary_transport = chosen.pop(primary_id, None)
            secondary_transport = chosen.pop(secondary_id, None)
            transport = primary_transport or secondary_transport
            if transport is None:
                continue
            affected_profiles.add(entry_id)
            chosen[primary_id] = transport

        # Historical/current live provenance must also follow the canonical ID.
        for sources in self.measurement_sources.values():
            for metric, source_id in tuple(sources.items()):
                if source_id in {primary_id, secondary_id}:
                    sources[metric] = primary_id

        if secondary_id in self._sensor_claim_reconcile_last_attempt:
            previous = self._sensor_claim_reconcile_last_attempt.pop(secondary_id)
            self._sensor_claim_reconcile_last_attempt[primary_id] = max(
                previous, self._sensor_claim_reconcile_last_attempt.get(primary_id, 0.0)
            )
        self._sensor_claim_reconcile_pending.discard(secondary_id)

        if not affected_profiles and winner is None:
            return

        async def _reconcile_affected_profiles() -> None:
            await asyncio.sleep(0)
            for entry_id in sorted(affected_profiles):
                entry = self.profile_entries.get(entry_id)
                if entry is not None:
                    await self._reconcile_profile_transports(entry)
            if winner is not None:
                self._schedule_sensor_claim_reconcile(primary_id)

        self.hass.async_create_background_task(
            _reconcile_affected_profiles(),
            f"fitness reconcile merged workout sensor {secondary_id}",
            eager_start=False,
        )

    def _merge_physical_sensors(self, a: LiveSensor, b: LiveSensor) -> LiveSensor:
        """Merge two transport identities without doing registry work on the radio path."""
        if a.sensor_id == b.sensor_id:
            return a

        # Snapshot state before aliases are changed. A deletion tombstone always
        # wins over stale accepted metadata/profile selections.
        a_id = a.sensor_id
        b_id = b.sensor_id
        requires_reassignment = (
            a_id in self._requires_reassignment
            or b_id in self._requires_reassignment
        )
        primary, secondary = self._select_merge_primary(a, b)
        # Registry cleanup is needed only when the side being discarded actually
        # had an accepted HA device. Merging an accepted BLE sensor with an
        # unaccepted provisional ANT endpoint must not scan/remove registries.
        secondary_had_accepted_device = self.sensor_is_accepted(secondary.sensor_id)
        for transport, endpoint in secondary.endpoints.items():
            if transport not in primary.endpoints:
                primary.endpoints[transport] = endpoint
            self.endpoint_aliases[endpoint.endpoint_id] = primary.sensor_id
        self.endpoint_aliases[secondary.sensor_id] = primary.sensor_id
        primary.capabilities.update(secondary.capabilities)
        primary.metadata.update(
            {k: v for k, v in secondary.metadata.items() if v not in (None, "", {}, [])}
        )

        self._migrate_workout_state_for_sensor_merge(
            primary.sensor_id, secondary.sensor_id
        )


        self._requires_reassignment.discard(a_id)
        self._requires_reassignment.discard(b_id)
        if requires_reassignment:
            self._requires_reassignment.add(primary.sensor_id)
            primary.metadata.pop("accepted", None)
        elif secondary.metadata.get("accepted"):
            primary.metadata["accepted"] = True

        # ANT device IDs are preferred as the stable canonical sensor ID, but ANT
        # profile names (for example "Heart Rate Sensor") are intentionally
        # generic.  When the discarded side is Bluetooth, preserve its meaningful
        # advertised/GATT product name so a merged dual-protocol wearable does not regress
        # to the generic ANT profile label.
        secondary_bt = secondary.endpoints.get("bluetooth")
        secondary_bt_name = None
        if secondary_bt is not None:
            secondary_bt_name = str(
                secondary_bt.metadata.get("model")
                or secondary_bt.metadata.get("advertised_name")
                or secondary.name
                or ""
            ).strip()
            if (
                not secondary_bt_name
                or re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", secondary_bt_name)
                or secondary_bt_name.isdigit()
            ):
                secondary_bt_name = None
        if secondary_bt_name:
            primary.name = _normalize_name(secondary_bt_name)
        elif primary.name == "Fitness sensor" or catalog_product_id(secondary.name, secondary.endpoints):
            primary.name = _normalize_name(secondary.name)
        if secondary.sensor_id in self.sensor_values:
            primary_values = self.sensor_values.setdefault(primary.sensor_id, {})
            primary_values.update(self.sensor_values.pop(secondary.sensor_id))
        if secondary.sensor_id in self.sensor_value_transport:
            primary_sources = self.sensor_value_transport.setdefault(primary.sensor_id, {})
            primary_sources.update(self.sensor_value_transport.pop(secondary.sensor_id))
        for attr in (
            "sensor_passive_values", "sensor_passive_meta", "sensor_passive_sources",
            "sensor_detail_values", "sensor_detail_meta", "sensor_detail_sources",
            "sensor_detail_source",
        ):
            store = getattr(self, attr)
            if secondary.sensor_id in store:
                target = store.setdefault(primary.sensor_id, {})
                for key, value in store.pop(secondary.sensor_id).items():
                    if isinstance(value, dict) and isinstance(target.get(key), dict):
                        target[key].update(value)
                    else:
                        target[key] = value
        self.sensors.pop(secondary.sensor_id, None)
        self._sensor_device_signatures.pop(secondary.sensor_id, None)
        self._sensor_device_signatures.pop(primary.sensor_id, None)
        pending_refresh = self._sensor_device_refresh_handles.pop(secondary.sensor_id, None)
        if pending_refresh is not None:
            pending_refresh.cancel()
            if (
                self.sensor_is_accepted(primary.sensor_id)
                and primary.sensor_id not in self._sensor_materialization_pending
            ):
                self._schedule_sensor_device_refresh(primary.sensor_id)
        if secondary.sensor_id in self._sensor_materialization_pending:
            self._sensor_materialization_pending.discard(secondary.sensor_id)
            self._sensor_materialization_pending.add(primary.sensor_id)

        # Discovery state follows the canonical physical ID. An Add flow may
        # already be open for the provisional ANT or BLE identity. Preserve that
        # flow across the merge instead of cancelling it and creating a duplicate
        # discovery for the canonical sensor.
        secondary_started = secondary.sensor_id in self._discovery_started
        self._discovery_started.discard(secondary.sensor_id)
        if secondary_started or self._discovery_flow_active(secondary.sensor_id):
            self._discovery_started.add(primary.sensor_id)
        secondary_task = self._discovery_tasks.pop(secondary.sensor_id, None)
        if secondary_task is not None and not secondary_task.done():
            self._discovery_tasks.setdefault(primary.sensor_id, secondary_task)

        # Unaccepted sensors have no registry objects, so scanning/removing the HA
        # registries and reloading the hub here is pure overhead. For an accepted
        # merge, defer that structural cleanup off the current radio callback.
        if secondary_had_accepted_device and not requires_reassignment:
            self._schedule_merged_registry_cleanup(secondary.sensor_id)

        self._schedule_save()
        return primary

    def _schedule_merged_registry_cleanup(self, old_sensor_id: str) -> None:
        """Defer registry cleanup/reload caused by a physical-identity merge."""
        async def _cleanup() -> None:
            # Let the identity/common-page burst and current config-flow response
            # finish before touching HA registries.
            await asyncio.sleep(1.0)
            self._cleanup_merged_registry_sensor(old_sensor_id)
            self._notify_structure_throttled()

        self.hass.async_create_background_task(
            _cleanup(),
            f"fitness cleanup merged live sensor {old_sensor_id}",
            eager_start=False,
        )

    def _cleanup_merged_registry_sensor(self, old_sensor_id: str) -> None:
        if self.hub_entry is None:
            return
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        entity_registry = er.async_get(self.hass)
        for entity in list(entity_registry.entities.values()):
            if entity.config_entry_id != self.hub_entry.entry_id or entity.platform != DOMAIN:
                continue
            if old_sensor_id in str(entity.unique_id or ""):
                entity_registry.async_remove(entity.entity_id)
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"live_sensor:{old_sensor_id}"),
            self.hub_entry.entry_id,
        )
        if device is not None:
            device_registry.async_remove_device(device.id)

    @staticmethod
    def _endpoints_recently_coobserved(
        a: LiveSensor, b: LiveSensor, max_age_seconds: float
    ) -> bool:
        """Require both catalog-correlation candidates to be recently observed."""
        a_ep = next(iter(a.endpoints.values()), None)
        b_ep = next(iter(b.endpoints.values()), None)
        if a_ep is None or b_ep is None or a_ep.last_seen is None or b_ep.last_seen is None:
            return False
        now = datetime.now(timezone.utc)
        try:
            a_age = (now - a_ep.last_seen).total_seconds()
            b_age = (now - b_ep.last_seen).total_seconds()
        except (TypeError, ValueError):
            return False
        return (
            0.0 <= a_age <= max_age_seconds
            and 0.0 <= b_age <= max_age_seconds
        )

    def _maybe_merge_correlated_dual_transport(self, sensor: LiveSensor) -> LiveSensor:
        """Apply one unambiguous data-driven cross-transport correlation rule.

        Exact serial/product matching in ``_match_sensor`` always has priority.
        Catalog correlation exists only for protocol combinations that cannot
        expose a shared strong identifier. Both sides must already be accepted,
        match complementary roles of the same rule, be recently observed, and be
        globally unique for that rule. Ambiguous candidates remain separate.
        """
        sensor_id = self.resolve_sensor_id(sensor.sensor_id)
        sensor = self.sensors.get(sensor_id, sensor)
        if not self.sensor_is_accepted(sensor.sensor_id):
            return sensor
        match = catalog_transport_correlation(sensor)
        if not match:
            return sensor

        rule_id = str(match["rule_id"])
        role = str(match["role"])
        max_age = float(match["max_age_seconds"])
        matching: list[tuple[LiveSensor, dict[str, Any]]] = []
        for candidate in self.sensors.values():
            if candidate.sensor_id == sensor.sensor_id or not self.sensor_is_accepted(candidate.sensor_id):
                continue
            candidate_match = catalog_transport_correlation(candidate)
            if not candidate_match or candidate_match.get("rule_id") != rule_id:
                continue
            if str(candidate_match.get("role")) == role:
                continue
            candidate_age = min(max_age, float(candidate_match.get("max_age_seconds", max_age)))
            if not self._endpoints_recently_coobserved(sensor, candidate, candidate_age):
                continue
            matching.append((candidate, candidate_match))

        # The fallback must be globally one-to-one. If two sensors can occupy
        # either side of the same rule, physical identity is ambiguous and no
        # automatic merge is permitted.
        by_role: dict[str, list[LiveSensor]] = {}
        for item in self.sensors.values():
            if not self.sensor_is_accepted(item.sensor_id):
                continue
            item_match = catalog_transport_correlation(item)
            if not item_match or item_match.get("rule_id") != rule_id:
                continue
            if not self._endpoints_recently_coobserved(sensor, item, min(max_age, float(item_match.get("max_age_seconds", max_age)))):
                continue
            by_role.setdefault(str(item_match.get("role")), []).append(item)

        if len(matching) != 1 or any(len(items) != 1 for items in by_role.values()) or len(by_role) != 2:
            return sensor

        merged = self._merge_physical_sensors(sensor, matching[0][0])
        merged.metadata["merge_evidence"] = rule_id
        return merged

    def _match_sensor(self, endpoint: TransportEndpoint, name: str) -> LiveSensor | None:
        current = None
        if endpoint.endpoint_id in self.endpoint_aliases:
            current = self.sensors.get(self.resolve_sensor_id(self.endpoint_aliases[endpoint.endpoint_id]))

        cross_ids = catalog_cross_transport_ids(
            name, endpoint.transport, endpoint.metadata, endpoint.capabilities
        )
        if cross_ids:
            candidates = []
            for sensor in self.sensors.values():
                if sensor is current or endpoint.transport in sensor.endpoints:
                    continue
                if not (sensor.capabilities & endpoint.capabilities):
                    continue
                sensor_ids: set[tuple[str, str, str]] = set()
                for other_endpoint in sensor.endpoints.values():
                    sensor_ids.update(catalog_cross_transport_ids(
                        sensor.name,
                        other_endpoint.transport,
                        other_endpoint.metadata,
                        other_endpoint.capabilities,
                    ))
                if cross_ids & sensor_ids:
                    candidates.append(sensor)
            if len(candidates) == 1:
                matched = candidates[0]
                matched.metadata["merge_evidence"] = "exact_cross_transport_id"
                return self._merge_physical_sensors(current, matched) if current else matched

        serial = _serial(endpoint.metadata)
        if serial:
            candidates = [
                sensor for sensor in self.sensors.values()
                if sensor is not current
                and any(_serial(ep.metadata) == serial for ep in sensor.endpoints.values())
            ]
            if len(candidates) == 1:
                return self._merge_physical_sensors(current, candidates[0]) if current else candidates[0]

        family = catalog_product_id(name, {endpoint.transport: endpoint})
        if family:
            candidates = [
                sensor for sensor in self.sensors.values()
                if sensor is not current
                and catalog_product_id(sensor.name, sensor.endpoints) == family
                and endpoint.transport not in sensor.endpoints
                and bool(sensor.capabilities & endpoint.capabilities)
            ]
            if len(candidates) == 1:
                return self._merge_physical_sensors(current, candidates[0]) if current else candidates[0]

        # Do not merge arbitrary same-name devices. Two people may own identical
        # HR straps/power meters, and a model/local name is not a physical identity.
        # Cross-transport merging requires a strong serial identity or a product-family
        # rule from the external device catalog. Unknown devices remain separate until
        # stronger identity data is learned (for example through Bluetooth DIS).
        return current

    @staticmethod
    def _stable_endpoint_metadata(
        transport: str, metadata: dict[str, Any], existing: TransportEndpoint | None
    ) -> dict[str, Any]:
        """Return metadata safe for identity/topology equality and persistence.

        BLE manufacturer/service payload bytes, RSSI, last-seen and route/source
        are volatile and intentionally excluded. Repeated BLE advertisements may
        expose partial UUID/company-ID sets, so those observations accumulate
        monotonically rather than oscillating the device topology.
        """
        clean = {
            k: v for k, v in dict(metadata or {}).items()
            if k not in {"manufacturer_data", "service_data", "rssi", "last_seen", "source"}
        }
        if transport != "bluetooth":
            return clean
        old = dict(existing.metadata) if existing is not None else {}
        for key in ("service_uuids", "manufacturer_data_ids"):
            merged = set(old.get(key) or []) | set(clean.get(key) or [])
            if merged:
                clean[key] = sorted(merged)
        if old.get("connectable"):
            clean["connectable"] = True
        old_name = str(old.get("advertised_name") or "").strip()
        if old_name and not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", old_name):
            clean["advertised_name"] = old_name
        return clean

    def refresh_transport_endpoint(
        self,
        sensor_id: str,
        transport: str,
        *,
        last_seen: datetime | None,
        rssi: int | None,
        source: str | None,
        available: bool,
    ) -> bool:
        """Refresh volatile endpoint state without structural/registry work."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get(transport) if sensor is not None else None
        if sensor is None or endpoint is None:
            return False

        previous_available = sensor.available
        endpoint.last_seen = last_seen
        endpoint.rssi = rssi
        endpoint.source = source
        endpoint.available = bool(available)
        if self.sensor_is_accepted(sensor_id):
            dirty = self._mark_last_seen_change(sensor_id, endpoint.last_seen)
            if previous_available != sensor.available:
                dirty.add((sensor_id, "availability", None))
            if dirty:
                self._notify_values_throttled(dirty)
        if available and self._global_workout_epoch_active():
            self._schedule_sensor_claim_reconcile(sensor_id)
        return True

    def register_transport_sensor(
        self,
        *,
        transport: str,
        endpoint_id: str,
        name: str,
        capabilities: set[str],
        address: str | None = None,
        source: str | None = None,
        last_seen: datetime | None = None,
        rssi: int | None = None,
        available: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> LiveSensor:
        """Register/update one transport endpoint and merge it physically."""
        metadata = dict(metadata or {})

        # Fast path for recurring advertisements from an already-known endpoint.
        # RSSI/last_seen can change several times per second; when the structural
        # identity is unchanged, update only those volatile fields and return
        # without rebuilding/matching the physical sensor or notifying globals.
        known_sensor_id = self.endpoint_aliases.get(endpoint_id)
        known_sensor = self.sensors.get(known_sensor_id) if known_sensor_id else None
        known_endpoint = (
            known_sensor.endpoints.get(transport) if known_sensor is not None else None
        )
        metadata = self._stable_endpoint_metadata(transport, metadata, known_endpoint)
        normalized_name = _normalize_name(name)
        current_name = str(known_sensor.name if known_sensor is not None else "")
        current_name_is_generic = (
            current_name in {"", "Fitness sensor"}
            or bool(re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", current_name))
        )
        # Advertisement/local names may alternate between aliases (for example a
        # vendor short name and product-family name). Once Fitness has a semantic
        # canonical name, those aliases must not force the slow structural path.
        name_would_change = bool(
            known_sensor is not None
            and current_name_is_generic
            and known_sensor.name != normalized_name
        )
        if (
            known_sensor is not None
            and known_endpoint is not None
            and not name_would_change
            and known_endpoint.address == address
            and (
                known_endpoint.capabilities == set(capabilities)
                or transport == "bluetooth"
                and set(capabilities).issubset(known_endpoint.capabilities)
            )
            and known_endpoint.metadata == metadata
        ):
            self.refresh_transport_endpoint(
                known_sensor.sensor_id,
                transport,
                last_seen=last_seen,
                rssi=rssi,
                source=source,
                available=available,
            )
            return known_sensor

        endpoint_capabilities = set(capabilities)
        if transport == "bluetooth" and known_endpoint is not None:
            endpoint_capabilities.update(known_endpoint.capabilities)
        endpoint = TransportEndpoint(
            transport=transport,
            endpoint_id=endpoint_id,
            address=address,
            capabilities=endpoint_capabilities,
            source=source,
            last_seen=last_seen,
            rssi=rssi,
            available=available,
            metadata=metadata,
        )
        sensor = self._match_sensor(endpoint, name)
        is_new = sensor is None
        old_caps: set[str] = set()
        if sensor is None:
            sensor = LiveSensor(
                sensor_id=self._new_physical_id(endpoint_id),
                name=_normalize_name(name),
            )
            self.sensors[sensor.sensor_id] = sensor
        else:
            old_caps = set(sensor.capabilities)

        previous_endpoint = sensor.endpoints.get(transport)
        previous_name = sensor.name
        previous_metadata = dict(sensor.metadata)
        previous_caps = set(sensor.capabilities)
        previous_available = sensor.available

        sensor.endpoints[transport] = endpoint
        sensor.capabilities.update(capabilities)
        self.endpoint_aliases[endpoint_id] = sensor.sensor_id

        # Merge only semantic identity fields into the canonical physical sensor.
        # Raw protocol numbers remain in endpoint/diagnostic metadata and can never
        # replace a meaningful user-facing product name/model.
        for key, value in canonical_identity_fields(metadata).items():
            if value not in (None, ""):
                sensor.metadata[key] = value
        sensor.metadata.setdefault("transport_details", {})[transport] = {
            "endpoint_id": endpoint_id,
            "address": address,
            **metadata,
        }
        identity = resolve_identity(sensor)
        if identity.get("name") and identity["name"] != "Fitness sensor":
            sensor.name = str(identity["name"])

        # Resolved identity facts are also retained as merged, disabled diagnostic
        # entities. Source-specific ANT/GATT observations can enrich the same keys.
        identity_values = {
            key: identity.get(key)
            for key in ("manufacturer", "model", "model_id", "serial_number", "hw_version", "sw_version", "firmware_version")
            if identity.get(key) not in (None, "")
        }
        if identity_values:
            identity_meta = {
                key: {
                    "name": key.replace("_", " ").title(),
                    "icon": "mdi:information-outline",
                    "entity_category": "diagnostic",
                    "enabled_default": False,
                }
                for key in identity_values
            }
            self.publish_details(
                sensor.sensor_id, identity_values, transport="resolved_identity",
                metadata=identity_meta, priority=90,
            )

        structural_change = (
            is_new
            or previous_endpoint is None
            or previous_endpoint.address != endpoint.address
            or previous_endpoint.capabilities != endpoint.capabilities
            or previous_endpoint.metadata != endpoint.metadata
            or sensor.name != previous_name
            or sensor.metadata != previous_metadata
            or sensor.capabilities != previous_caps
        )

        if structural_change and self.sensor_is_accepted(sensor.sensor_id):
            sensor = self._maybe_merge_correlated_dual_transport(sensor)
            endpoint = sensor.endpoints.get(transport, endpoint)

        # RSSI and last_seen are intentionally volatile. Passive advertisements can
        # arrive several times per second, so they must not cause storage writes,
        # entity-registry creation, hub reloads, or state updates on every packet.
        if structural_change:
            self._schedule_save()
        # Device Registry work is control-plane only. A normal advertisement for
        # an accepted sensor must never even resolve DeviceInfo unless stable
        # identity/topology actually changed; the config-flow finalizer creates
        # the initial device after acceptance.
        if (
            structural_change
            and self.hub_entry is not None
            and self.sensor_is_accepted(sensor.sensor_id)
            and sensor.sensor_id not in self._sensor_materialization_pending
        ):
            self._schedule_sensor_device_refresh(sensor.sensor_id)
        # Discovery is assignment-driven, not object-creation-driven.
        #
        # A physical sensor may already be known because another transport was
        # merged into it or because the user deleted its HA device and the radio
        # endpoint has now been rediscovered. `is_new` therefore must not gate
        # discovery.
        #
        # _schedule_sensor_discovery() performs its own de-duplication and
        # assignment checks, including the explicit reassignment tombstone.
        if self.profile_entries and not self.sensor_is_accepted(sensor.sensor_id):
            self._schedule_sensor_discovery(sensor.sensor_id)
        accepted = self.sensor_is_accepted(sensor.sensor_id)
        if (
            structural_change
            and accepted
            and sensor.sensor_id not in self._sensor_materialization_pending
        ):
            self._notify_structure_throttled()
        if accepted:
            dirty = self._mark_last_seen_change(sensor.sensor_id, endpoint.last_seen)
            if previous_available != sensor.available:
                dirty.add((sensor.sensor_id, "availability", None))
            if dirty:
                self._notify_values_throttled(dirty)
        if is_new:
            # Adapter-level "known sensor count" changes only when a new physical
            # object appears. Identity/capability enrichment is handled by the
            # dedicated structure/value listeners and must not fan out globally.
            self._notify()
        if available and accepted and self._global_workout_epoch_active():
            self._schedule_sensor_claim_reconcile(sensor.sensor_id)
        return sensor

    # Compatibility for older provider code/tests while transitioning.
    def register_sensor(self, sensor) -> None:
        if isinstance(sensor, LiveSensor) and sensor.endpoints:
            for endpoint in sensor.endpoints.values():
                self.register_transport_sensor(
                    transport=endpoint.transport,
                    endpoint_id=endpoint.endpoint_id,
                    name=sensor.name,
                    capabilities=endpoint.capabilities or sensor.capabilities,
                    address=endpoint.address,
                    source=endpoint.source,
                    last_seen=endpoint.last_seen,
                    rssi=endpoint.rssi,
                    available=endpoint.available,
                    metadata=endpoint.metadata,
                )
            return
        raise TypeError("Fitness providers must register transport endpoints")

    def _expire_stale_sensor_endpoints(self) -> None:
        """Mark silent radio endpoints unavailable without changing topology.

        Availability is runtime presence, not identity. A remembered BLE/ANT
        endpoint may remain in the physical device indefinitely, but its HA
        Available entity must not stay on forever after broadcasts stop. Active
        GATT connections remain available even when their measurement stream is
        temporarily quiet.
        """
        now = datetime.now(timezone.utc)
        dirty: set[tuple[str, str, str | None]] = set()
        bt_provider = self.providers.get("bluetooth")
        for sensor in self.sensors.values():
            before = sensor.available
            for transport, endpoint in sensor.endpoints.items():
                if not endpoint.available or endpoint.last_seen is None:
                    continue
                if (now - endpoint.last_seen).total_seconds() <= DISCOVERY_RECENT_SECONDS:
                    continue
                if transport == "bluetooth" and bt_provider is not None:
                    connected = getattr(bt_provider, "sensor_connected", None)
                    if connected is not None and bool(connected(sensor.sensor_id)):
                        continue
                endpoint.available = False
            if before != sensor.available and self.sensor_is_accepted(sensor.sensor_id):
                dirty.add((sensor.sensor_id, "availability", None))
        if dirty:
            self._notify_values_throttled(dirty)

    def _prune_stale_sensor_discovery_flows(self) -> None:
        """Compatibility no-op: discovery cards are intentionally sticky.

        Once a physical sensor has been freshly observed, Fitness keeps the
        discovery flow until setup/rejection. Radio silence changes runtime
        availability only; it must never abort and later recreate HA config
        flows.
        """
        return

    def sensor_recently_observed(
        self, sensor_id: str, *, max_age: float = DISCOVERY_RECENT_SECONDS
    ) -> bool:
        """Return whether the physical sensor has transmitted recently.

        Restored sensors retain their last_seen timestamp so identity/merge state can
        survive restarts, but stale stored endpoints must never become discovery cards.
        Only a fresh RF/BLE observation may initiate or retry discovery.
        """
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None:
            return False
        seen = sensor.last_seen
        if seen is None:
            return False
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - seen.astimezone(timezone.utc)).total_seconds()
        return -1.0 <= age <= max_age

    def _discovery_flow_matches_sensor(self, flow: dict[str, Any], sensor_id: str) -> bool:
        """Return whether an in-progress discovery flow represents this physical sensor.

        Config flows may have started before ANT+/BLE identities merged. Resolve
        the flow's provisional unique ID through endpoint aliases so one physical
        sensor can never have two concurrent discovery flows after a merge.
        """
        canonical = self.resolve_sensor_id(sensor_id)
        context = flow.get("context") or {}
        unique_id = str(context.get("unique_id") or "")
        if not unique_id.startswith("live_sensor:"):
            return False
        provisional = unique_id.split(":", 1)[1]
        return self.resolve_sensor_id(provisional) == canonical

    def _discovery_flow_active(self, sensor_id: str) -> bool:
        canonical = self.resolve_sensor_id(sensor_id)
        return any(
            self._discovery_flow_matches_sensor(flow, canonical)
            for flow in self.hass.config_entries.flow.async_progress()
        )

    def _sensor_discovery_ready(self, sensor_id: str) -> bool:
        """Return whether a physical sensor has enough stable identity to offer.

        Bluetooth devices may be offered from a meaningful advertised/catalog
        identity because their address remains tied to the same endpoint.

        ANT+ semantic endpoints become offerable after their receiver-side RF
        confirmation. Background manufacturer/serial pages are enrichment and
        cross-transport merge evidence, not a prerequisite for basic discovery.
        """
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None:
            return False

        # A catalog product-family match is strong enough for both discovery and
        # cross-transport merging.
        if catalog_product_id(sensor.name, sensor.endpoints):
            return True

        serials = {
            value
            for endpoint in sensor.endpoints.values()
            if (value := _serial(endpoint.metadata))
        }
        if serials:
            return True

        bluetooth = sensor.endpoints.get("bluetooth")
        if bluetooth is not None:
            advertised = str(
                bluetooth.metadata.get("advertised_name") or sensor.name or ""
            ).strip()
            if (
                advertised
                and advertised != "Fitness sensor"
                and not re.fullmatch(
                    r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", advertised
                )
            ):
                return True

        ant = sensor.endpoints.get("antplus")
        if ant is None:
            return False

        # A supported ANT fitness profile is already protected by the receiver's
        # profile-aware multi-packet RF confirmation before the endpoint reaches
        # runtime. Do not make basic discovery wait for slow optional background
        # identity pages. Manufacturer/serial/model data can arrive later and will
        # still enrich or cross-transport-merge the physical sensor.
        if ant.metadata.get("rf_identity_confirmed") and sensor.capabilities:
            return True

        # Raw/legacy ANT endpoints that did not come through that confirmed
        # semantic path keep the conservative identity requirement.
        manufacturer_id = ant.metadata.get("manufacturer_id")
        model_no = ant.metadata.get("model_no")
        manufacturer = str(ant.metadata.get("manufacturer") or "").strip()
        model = str(ant.metadata.get("model") or "").strip()
        return bool(
            manufacturer_id not in (None, "")
            and (
                model_no not in (None, "")
                or (manufacturer and model and not model.isdigit())
            )
        )

    def _schedule_sensor_discovery(self, sensor_id: str) -> None:
        """Start one discovery flow for an observed, unaccepted physical sensor."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None or self.sensor_is_accepted(sensor_id):
            return
        now_mono = time.monotonic()
        quarantined = False
        for endpoint in sensor.endpoints.values():
            until = self._rediscovery_quarantine_until.get(endpoint.endpoint_id, 0.0)
            if until > now_mono:
                quarantined = True
                break
            if until:
                self._rediscovery_quarantine_until.pop(endpoint.endpoint_id, None)
        if quarantined:
            return
        if not self._sensor_discovery_ready(sensor_id):
            return

        fresh = self.sensor_recently_observed(sensor_id)
        confirmed = bool(sensor.metadata.get("discovery_confirmed"))
        if not fresh and not confirmed:
            return
        if fresh and not confirmed:
            # Persist only the transition from never-observed to confirmed.
            # This gives discovery restart durability without packet-rate saves.
            sensor.metadata["discovery_confirmed"] = True
            self._schedule_save()

        unique_id = f"live_sensor:{sensor_id}"

        # A scheduled async_init call is not visible in FlowManager progress yet.
        task = self._discovery_tasks.get(sensor_id)
        if task is not None and not task.done():
            return
        if task is not None:
            self._discovery_tasks.pop(sensor_id, None)

        # `_discovery_started` is only a fast local guard. A user can dismiss a
        # discovery flow without calling back into Fitness, so verify it against
        # Home Assistant's actual in-progress flows before suppressing rediscovery.
        if sensor_id in self._discovery_started:
            if self._discovery_flow_active(sensor_id):
                return
            self._discovery_started.discard(sensor_id)

        # A flow may have started under the other transport's provisional physical
        # ID and then been merged into this canonical sensor. Never start a second
        # flow for the canonical ID while that original flow is still alive.
        if self._discovery_flow_active(sensor_id):
            self._discovery_started.add(sensor_id)
            return

        if (
            sensor_id not in self._requires_reassignment
            and any(
                sensor_id in set(self.selected_sensor_ids(entry))
                for entry in tuple(self.profile_entries.values())
            )
        ):
            return

        from homeassistant.helpers import device_registry as dr

        if self.hub_entry is not None:
            registry = dr.async_get(self.hass)
            if registry.async_get_device_by_identifier(
                (DOMAIN, f"live_sensor:{sensor_id}"),
                self.hub_entry.entry_id,
            ) is not None and sensor.metadata.get("accepted"):
                return

        self._discovery_started.add(sensor_id)

        async def _start_discovery() -> None:
            try:
                await self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "integration_discovery"},
                    data={"sensor_id": sensor_id},
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                # Do not permanently poison rediscovery after a transient flow
                # failure/import/reload race. The next observation may try again.
                self._discovery_started.discard(sensor_id)
                _LOGGER.debug(
                    "Unable to start Fitness discovery for %s",
                    sensor_id,
                    exc_info=True,
                )
            finally:
                self._discovery_tasks.pop(sensor_id, None)

        self._discovery_tasks[sensor_id] = self.hass.async_create_background_task(
            _start_discovery(),
            f"fitness discover live sensor {sensor_id}",
            eager_start=False,
        )

    def sensor_is_accepted(self, sensor_id: str) -> bool:
        """Return whether a discovered physical sensor belongs in HA's device registry."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None:
            return False
        if sensor_id in self._requires_reassignment:
            return False
        if bool(sensor.metadata.get("accepted")):
            return True
        return any(
            sensor_id in set(self.selected_sensor_ids(entry))
            for entry in self.profile_entries.values()
        )

    def mark_sensor_accepted(self, sensor_id: str) -> None:
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor:
            self._requires_reassignment.discard(sensor_id)
            self._discovery_started.discard(sensor_id)
            sensor.metadata["accepted"] = True
            sensor.metadata.pop("discovery_confirmed", None)

            # Acceptance can be the first moment both sides of a catalog-defined
            # dual-transport pair are eligible for the conservative correlation
            # fallback. Merge before materialization so HA never needs to build a
            # second set of entities only to delete it a moment later.
            sensor = self._maybe_merge_correlated_dual_transport(sensor)
            sensor_id = sensor.sensor_id

            # Acceptance blocks duplicate discovery immediately, but entity/device
            # materialization waits until the config-flow response has returned.
            self._sensor_materialization_pending.add(sensor_id)
            for provider in tuple(self.providers.values()):
                callback_fn = getattr(provider, "sensor_acceptance_changed", None)
                if callback_fn is not None:
                    callback_fn(sensor_id, True)
            # Keep the config-flow request path lightweight. Persist acceptance and
            # notify topology listeners; device/entity materialization is handled
            # dynamically without reloading the hub or profile config entries.
            self._schedule_save()

    def remove_unaccepted_sensor_device(self, sensor_id: str) -> None:
        """Remove devices/entities created by pre-acceptance prototype builds."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        if self.hub_entry is None or self.sensor_is_accepted(sensor_id):
            return
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"live_sensor:{sensor_id}"), self.hub_entry.entry_id
        )
        if device is None:
            return
        for entity in list(entity_registry.entities.values()):
            if entity.platform == DOMAIN and entity.device_id == device.id:
                entity_registry.async_remove(entity.entity_id)
        device_registry.async_remove_device(device.id)

    def finalize_sensor_acceptance(self, sensor_id: str) -> None:
        """Materialize one accepted sensor from its latest canonical snapshot."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        try:
            self.ensure_sensor_device(sensor_id)
        except Exception:
            # Acceptance itself is already committed. A registry problem must not
            # turn a successful Add into an unhandled config-flow/background task.
            _LOGGER.exception(
                "Unable to materialize accepted Fitness sensor %s", sensor_id
            )
        finally:
            self._sensor_materialization_pending.discard(sensor_id)
        self._notify_structure_throttled()

    def _schedule_sensor_device_refresh(self, sensor_id: str) -> None:
        """Debounce Device Registry enrichment away from radio callbacks.

        ANT common pages and BLE identity facts can arrive in a short burst. The
        radio path records the newest stable snapshot in memory, then one control-
        plane callback materializes the final DeviceInfo after the burst.
        """
        sensor_id = self.resolve_sensor_id(sensor_id)
        existing = self._sensor_device_refresh_handles.get(sensor_id)
        if existing is not None:
            existing.cancel()

        def _refresh() -> None:
            self._sensor_device_refresh_handles.pop(sensor_id, None)
            canonical = self.resolve_sensor_id(sensor_id)
            try:
                self.ensure_sensor_device(canonical)
            except Exception:
                _LOGGER.exception(
                    "Unable to refresh Fitness sensor DeviceInfo for %s", canonical
                )

        # Device registry enrichment is control-plane work. Wait for three
        # seconds of identity quiet instead of refreshing repeatedly while ANT
        # common pages are rotating.
        self._sensor_device_refresh_handles[sensor_id] = self.hass.loop.call_later(
            3.0, _refresh
        )

    def ensure_sensor_device(self, sensor_id: str) -> None:
        """Create or migrate one physical sensor into the Sensors subentry."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None or self.hub_entry is None or not self.sensor_is_accepted(sensor_id):
            return
        subentry_id = self._sensor_subentry_id()
        if subentry_id is None:
            return
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        info = self.sensor_device_info(sensor_id)
        signature = (
            subentry_id,
            tuple(sorted(info["identifiers"])),
            info.get("name"), info.get("manufacturer"),
            info.get("model"), info.get("model_id"), info.get("serial_number"),
            info.get("hw_version"), info.get("sw_version"),
        )
        if (
            self._sensor_device_signatures.get(sensor_id) == signature
            and sensor_id in self._sensor_device_ids
        ):
            return

        # Migrate v2 physical devices which were owned by the parent hub entry.
        # Do this before entity platforms are forwarded: Home Assistant may prune
        # registry entities from the old subentry when a device moves, and the
        # platform setup below will recreate them directly in the Sensors subentry.
        existing = registry.async_get_device_by_identifier(
            (DOMAIN, f"live_sensor:{sensor_id}"), self.hub_entry.entry_id
        )
        if existing is not None and existing.config_subentry_id != subentry_id:
            registry.async_update_device(
                existing.id, new_config_subentry_id=subentry_id
            )

        kwargs = {
            "config_entry_id": self.hub_entry.entry_id,
            "config_subentry_id": subentry_id,
            "identifiers": set(info["identifiers"]),
            "name": info.get("name") or "Fitness sensor",
        }
        for key in ("manufacturer", "model", "model_id", "serial_number", "hw_version", "sw_version"):
            value = info.get(key)
            if value not in (None, ""):
                kwargs[key] = value
        device = registry.async_get_or_create(**kwargs)
        self._sensor_device_ids[sensor_id] = device.id
        self._sensor_device_signatures[sensor_id] = signature

    def request_hub_reload(self) -> None:
        if self.hub_entry is None or self._hub_reload_pending:
            return
        self._hub_reload_pending = True
        entry_id = self.hub_entry.entry_id

        async def _reload():
            await asyncio.sleep(0.75)
            self._hub_reload_pending = False
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is not None and entry.state.value == "loaded":
                await self.hass.config_entries.async_reload(entry_id)

        self.hass.async_create_background_task(
            _reload(),
            "fitness reload live sensor hub",
            eager_start=False,
        )

    def _manager_for_profile(self, entry_id: str):
        return self.hass.data.get(DOMAIN, {}).get(str(entry_id))

    def _profile_is_live_session(self, entry_id: str) -> bool:
        manager = self._manager_for_profile(entry_id)
        return bool(
            manager is not None
            and (manager.session_armed or manager.session_active)
        )

    def _profile_is_using_live_runtime(self, entry_id: str) -> bool:
        manager = self._manager_for_profile(entry_id)
        return bool(
            manager is not None
            and (
                manager.session_armed
                or manager.session_active
                or getattr(manager, "recovery_active", False)
            )
        )

    def _global_workout_epoch_active(self) -> bool:
        return any(
            self._profile_is_using_live_runtime(entry_id)
            for entry_id in tuple(self.profile_entries)
        )

    def sensor_live_telemetry_needed(self, sensor_id: str) -> bool:
        """Return whether any live profile currently needs this physical sensor."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        if not self.sensor_is_accepted(sensor_id):
            return False
        owner = self.sensor_workout_owner(sensor_id)
        for entry_id, entry in tuple(self.profile_entries.items()):
            if not self._profile_is_using_live_runtime(entry_id):
                continue
            if owner not in (None, entry_id):
                continue
            if any(
                self.resolve_sensor_id(sensor.sensor_id) == sensor_id
                for sensor in self.sensors_for_profile(entry)
            ):
                return True
        return False

    def _refresh_live_provider_gates(self) -> None:
        """Refresh provider high-rate gates after session/assignment state changes."""
        provider = self.providers.get("antplus")
        refresh = getattr(provider, "refresh_telemetry_gates", None) if provider else None
        if refresh is not None:
            refresh()

    def sensor_workout_owner(self, sensor_id: str) -> str | None:
        """Return the exclusive Fitness-profile owner of one physical sensor."""
        return self._sensor_workout_owner.get(self.resolve_sensor_id(sensor_id))

    def profile_claimed_sensor_ids(self, entry_id: str) -> set[str]:
        return set(self._profile_claimed_sensors.get(str(entry_id), set()))

    def _claim_sensor_for_workout(self, sensor_id: str) -> str | None:
        """Claim a free physical sensor for the oldest eligible live session.

        Assignment is many-to-many configuration; workout ownership is strictly
        one-to-one. Once claimed, a sensor remains reserved to that owner until
        the *entire overlapping workout epoch* is idle, even if the owner stops
        earlier than another profile. This prevents a still-worn sensor from
        suddenly feeding somebody else's ongoing workout.
        """
        sensor_id = self.resolve_sensor_id(sensor_id)
        if not self.sensor_is_accepted(sensor_id):
            return None
        owner = self._sensor_workout_owner.get(sensor_id)
        if owner is not None:
            return owner

        candidates: list[tuple[int, str]] = []
        for entry in tuple(self.profile_entries.values()):
            entry_id = entry.entry_id
            if not self._profile_is_live_session(entry_id):
                continue
            if sensor_id not in self.selected_sensor_ids(entry):
                continue
            order = self._profile_session_order.get(entry_id)
            if order is None:
                # Defensive fallback for an already-running manager registered
                # before this runtime state existed. Normal starts set an order
                # in async_prepare_session().
                self._session_order_counter += 1
                order = self._session_order_counter
                self._profile_session_order[entry_id] = order
            candidates.append((order, entry_id))

        if not candidates:
            return None
        _, owner = min(candidates, key=lambda item: (item[0], item[1]))
        self._sensor_workout_owner[sensor_id] = owner
        self._profile_claimed_sensors.setdefault(owner, set()).add(sensor_id)
        self._notify_values_throttled({(sensor_id, "workout_owner", None)})
        return owner

    def _clear_workout_sensor_locks_if_idle(self) -> bool:
        """Clear the whole exclusive-lock epoch only when every session is idle."""
        if self._global_workout_epoch_active():
            return False
        if not self._sensor_workout_owner and not self._profile_claimed_sensors:
            self._profile_session_order.clear()
            return False
        sensor_ids = set(self._sensor_workout_owner)
        self._sensor_workout_owner.clear()
        self._profile_claimed_sensors.clear()
        self._profile_session_order.clear()
        if sensor_ids:
            self._notify_values_throttled(
                {(sensor_id, "workout_owner", None) for sensor_id in sensor_ids}
            )
        return True

    def _schedule_sensor_claim_reconcile(self, sensor_id: str) -> None:
        """Claim/reconcile only while a live session actually exists."""
        if not self._global_workout_epoch_active():
            return
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None or not self.sensor_is_accepted(sensor_id):
            return
        previous_owner = self.sensor_workout_owner(sensor_id)
        owner = self._claim_sensor_for_workout(sensor_id)
        if owner is None or sensor_id in self._sensor_claim_reconcile_pending:
            return
        entry = self.profile_entries.get(owner)
        if entry is None:
            return

        desired = self.choose_transport(sensor)
        current = self._profile_sensor_transport.get(owner, {}).get(sensor_id)
        if previous_owner is not None and desired == current:
            return

        # A failed BLE connection must not be retried at advertisement frequency.
        # The dual-transport handover monitor retries once per second; BLE-only
        # devices use the same minimum retry interval here. New claims bypass the
        # cooldown so their first connection attempt is immediate.
        now = self.hass.loop.time()
        last_attempt = self._sensor_claim_reconcile_last_attempt.get(sensor_id, 0.0)
        if previous_owner is not None and now - last_attempt < 1.0:
            return
        self._sensor_claim_reconcile_last_attempt[sensor_id] = now
        self._sensor_claim_reconcile_pending.add(sensor_id)

        async def _reconcile() -> None:
            try:
                # Re-check ownership after yielding. A global epoch reset or
                # profile teardown must never connect GATT for a stale owner.
                if self.sensor_workout_owner(sensor_id) != owner:
                    return
                await self._reconcile_profile_transports(entry)
                self._start_profile_handover_monitor(entry)
            finally:
                self._sensor_claim_reconcile_pending.discard(sensor_id)

        self.hass.async_create_background_task(
            _reconcile(),
            f"fitness claim live sensor {sensor_id}",
            eager_start=False,
        )

    def _profile_can_receive_transferred_sensor(self, entry_id: str, sensor_id: str) -> bool:
        manager = self._manager_for_profile(entry_id)
        entry = self.profile_entries.get(entry_id)
        if manager is None or entry is None:
            return False
        if sensor_id not in self.selected_sensor_ids(entry):
            return False
        return bool(manager.session_armed or manager.session_active)

    async def async_transfer_workout_sensor_owner(
        self, sensor_id: str, target_entry_id: str
    ) -> None:
        """Transfer a physical sensor during an overlapping workout, explicitly.

        To prevent one person's measurements leaking into another profile, the
        current owner must be paused and the target must be armed or paused.
        The sensor remains globally locked; only its exclusive owner changes.
        """
        sensor_id = self.resolve_sensor_id(sensor_id)
        current = self.sensor_workout_owner(sensor_id)
        target_entry_id = str(target_entry_id)
        if current is None:
            raise RuntimeError("Sensor is not currently workout-locked")
        if current == target_entry_id:
            return
        current_manager = self._manager_for_profile(current)
        if current_manager is None or not getattr(current_manager, "session_paused", False):
            raise RuntimeError("Pause the current sensor owner before transferring it")
        if not self._profile_can_receive_transferred_sensor(target_entry_id, sensor_id):
            raise RuntimeError("Target profile must be armed or paused and have this sensor assigned")

        # Disconnect/remove the sensor from the old profile before changing the
        # lock. This ordering guarantees no packet can be routed to both users.
        bt_provider = self.providers.get("bluetooth")
        old_transport = self._profile_sensor_transport.get(current, {}).pop(sensor_id, None)
        if old_transport == "bluetooth" and bt_provider is not None:
            disconnect_one = getattr(bt_provider, "async_disconnect_sensor", None)
            if disconnect_one is not None:
                await disconnect_one(current, sensor_id)
        self._profile_claimed_sensors.setdefault(current, set()).discard(sensor_id)
        self._sensor_workout_owner[sensor_id] = target_entry_id
        self._profile_claimed_sensors.setdefault(target_entry_id, set()).add(sensor_id)

        # Remove stale live values from both profiles. The next packet after the
        # transfer is the first value allowed to populate the new owner.
        for entry_id in {current, target_entry_id}:
            sources = self.measurement_sources.setdefault(entry_id, {})
            values = self.measurements.setdefault(entry_id, {})
            for metric, source_id in tuple(sources.items()):
                if self.resolve_sensor_id(source_id) == sensor_id:
                    sources.pop(metric, None)
                    values.pop(metric, None)
            self.measurement_time.pop(entry_id, None)
            manager = self._manager_for_profile(entry_id)
            if manager is not None:
                self._notify_profile_live_throttled(entry_id, manager)

        self._notify_values_throttled({(sensor_id, "workout_owner", None)})
        target_entry = self.profile_entries[target_entry_id]
        await self._reconcile_profile_transports(target_entry)
        self._start_profile_handover_monitor(target_entry)

    def schedule_profile_assignment_refresh(self, entry_ids) -> None:
        """Apply physical-sensor routing changes without reloading profiles.

        Profile Live devices/entities are stable infrastructure. Assignment only
        changes which physical sensors may feed a profile, so reconcile transport
        ownership in the background and notify the live surface in place.
        """
        entry_ids = tuple(dict.fromkeys(str(entry_id) for entry_id in entry_ids if entry_id))
        if not entry_ids:
            return

        async def _refresh() -> None:
            await asyncio.sleep(0)
            self._refresh_live_provider_gates()
            for entry_id in entry_ids:
                entry = self.profile_entries.get(entry_id)
                if entry is not None:
                    try:
                        await self._reconcile_profile_transports(entry)
                    except Exception:
                        _LOGGER.debug(
                            "Unable to reconcile Fitness sensor assignment for profile %s",
                            entry_id,
                            exc_info=True,
                        )
                manager = self.hass.data.get(DOMAIN, {}).get(entry_id)
                if manager is not None:
                    manager._notify_live()

        self.hass.async_create_background_task(
            _refresh(),
            "fitness refresh physical sensor assignments",
            eager_start=False,
        )

    def sensor_assigned_profile_ids(self, sensor_id: str) -> list[str]:
        """Return profiles which are configured to use one physical sensor."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        return [
            entry.entry_id
            for entry in self.profile_entries.values()
            if sensor_id in self.selected_sensor_ids(entry)
        ]

    def sensor_live_assigned_profile_ids(self, sensor_id: str) -> list[str]:
        """Return assigned profiles which currently have a live workout session."""
        return [
            entry_id
            for entry_id in self.sensor_assigned_profile_ids(sensor_id)
            if self._profile_is_live_session(entry_id)
        ]

    def sensor_owner_transfer_available(self, sensor_id: str) -> bool:
        """Return whether an ownership handoff is currently meaningful."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        return bool(
            len(self.sensor_assigned_profile_ids(sensor_id)) > 1
            and len(self.sensor_live_assigned_profile_ids(sensor_id)) >= 2
            and self.sensor_workout_owner(sensor_id) is not None
        )

    def profile_has_assigned_live_sensor(self, entry) -> bool:
        """Return whether this profile has at least one accepted physical sensor."""
        for sensor_id in self.selected_sensor_ids(entry):
            sensor_id = self.resolve_sensor_id(sensor_id)
            if sensor_id in self.sensors and self.sensor_is_accepted(sensor_id):
                return True
        return False

    def selected_sensor_ids(self, entry) -> list[str]:
        raw = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
        result = []
        for sensor_id in raw:
            resolved = self.resolve_sensor_id(str(sensor_id))
            if resolved not in result:
                result.append(resolved)
        return result

    def sensors_for_profile(self, entry) -> list[LiveSensor]:
        return [self.sensors[x] for x in self.selected_sensor_ids(entry) if x in self.sensors]

    def ant_data_fresh(self, sensor: LiveSensor, *, now: datetime | None = None) -> bool:
        endpoint = sensor.endpoints.get("antplus")
        if (
            endpoint is None
            or endpoint.last_seen is None
            or not self.adapter_enabled("antplus")
            or not self.adapter_enabled("antplus")
        ):
            return False
        now = now or datetime.now(timezone.utc)
        try:
            age = (now - endpoint.last_seen).total_seconds()
        except Exception:
            return False
        return 0.0 <= age <= ANT_DATA_FRESH_SECONDS

    def bluetooth_gatt_supported(self, sensor: LiveSensor) -> bool:
        """Return cached GATT capability without querying HA Bluetooth.

        Entity properties and device-page rendering call this method frequently.
        It must remain O(1) and side-effect free. The real BLE-device/proxy
        resolution is performed only when a connection is actually requested.
        """
        endpoint = sensor.endpoints.get("bluetooth")
        return bool(
            endpoint is not None
            and endpoint.address
            and self.adapter_enabled("bluetooth")
            and self.providers.get("bluetooth") is not None
            and endpoint.metadata.get("connectable", False)
        )

    def bluetooth_gatt_capable(self, sensor: LiveSensor) -> bool:
        return self.bluetooth_gatt_supported(sensor)

    def bluetooth_gatt_connected(self, sensor_id: str) -> bool:
        provider = self.providers.get("bluetooth")
        checker = getattr(provider, "sensor_connected", None) if provider else None
        return bool(checker(self.resolve_sensor_id(sensor_id))) if checker is not None else False

    def choose_transport(self, sensor: LiveSensor) -> str | None:
        """Prefer fresh ANT+; use Bluetooth GATT only when ANT+ is unavailable."""
        ant_endpoint = sensor.endpoints.get("antplus")
        ant_provider = self.providers.get("antplus")
        ant_usable = bool(
            ant_endpoint is not None
            and ant_provider is not None
            and self.adapter_enabled("antplus")
        )
        if ant_usable and self.ant_data_fresh(sensor):
            return "antplus"

        if (
            "bluetooth" in sensor.endpoints
            and self.adapter_enabled("bluetooth")
            and self.bluetooth_gatt_supported(sensor)
        ):
            return "bluetooth"

        if ant_usable and (
            ant_endpoint.available or bool(getattr(ant_provider, "available", False))
        ):
            return "antplus"
        return None

    async def _claim_transport(self, entry_id: str, transport: str) -> None:
        """Record workout use of an already-enabled transport.

        Providers are started/stopped only by the adapter Activate switch.
        """
        if not self.adapter_enabled(transport) or transport not in self.providers:
            return
        self._transport_claims.setdefault(transport, set()).add(entry_id)
        self._profile_claims.setdefault(entry_id, set()).add(transport)

    async def _release_transport(self, entry_id: str, transport: str) -> None:
        """Release workout bookkeeping without changing provider state."""
        claims = self._transport_claims.get(transport)
        if claims is not None:
            claims.discard(entry_id)
            if not claims:
                self._transport_claims.pop(transport, None)
        profile_claims = self._profile_claims.get(entry_id)
        if profile_claims is not None:
            profile_claims.discard(transport)
            if not profile_claims:
                self._profile_claims.pop(entry_id, None)

    async def _reconcile_profile_transports(self, entry) -> None:
        """Move each selected physical sensor between ANT+ and BLE safely."""
        chosen = self._profile_sensor_transport.setdefault(entry.entry_id, {})
        bt_provider = self.providers.get("bluetooth")
        owned_ids = self.profile_claimed_sensor_ids(entry.entry_id)
        manager = self._manager_for_profile(entry.entry_id)
        if (
            manager is not None
            and getattr(manager, "recovery_active", False)
            and not manager.session_active
            and not manager.session_armed
        ):
            # Post-workout HR recovery must never reconnect unrelated claimed
            # sensors merely because their physical lock is intentionally held
            # until the overlapping workout epoch ends.
            hr_sensor = self.measurement_sources.get(entry.entry_id, {}).get(
                METRIC_HEART_RATE
            )
            owned_ids = {hr_sensor} if hr_sensor in owned_ids else set()

        # Remove stale transport selections first. The physical workout lock may
        # intentionally survive this profile's stop until all overlapping
        # sessions finish, but a stopped profile must not keep GATT open.
        for sensor_id in tuple(chosen):
            if sensor_id not in owned_ids or not self._profile_is_using_live_runtime(entry.entry_id):
                current = chosen.pop(sensor_id, None)
                if current == "bluetooth" and bt_provider is not None:
                    disconnect_one = getattr(bt_provider, "async_disconnect_sensor", None)
                    if disconnect_one is not None:
                        await disconnect_one(entry.entry_id, sensor_id)
                sensor = self.sensors.get(sensor_id)
                if sensor is not None:
                    self._set_active_transport(sensor, None)

        if not self._profile_is_using_live_runtime(entry.entry_id):
            return

        for sensor_id in sorted(owned_ids):
            sensor = self.sensors.get(sensor_id)
            if sensor is None:
                continue
            desired = self.choose_transport(sensor)
            current = chosen.get(sensor.sensor_id)
            if desired == current:
                continue
            if desired == "bluetooth":
                try:
                    await self._claim_transport(entry.entry_id, "bluetooth")
                    if bt_provider is not None:
                        await bt_provider.async_connect_profile(entry.entry_id, [sensor])
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # Connection failure is recoverable: release this profile's
                    # transport claim and leave the exclusive physical lock in
                    # place. The handover monitor may retry without leaking a
                    # phantom GATT owner.
                    await self._release_transport(entry.entry_id, "bluetooth")
                    chosen.pop(sensor.sensor_id, None)
                    self._set_active_transport(sensor, None)
                    _LOGGER.debug(
                        "Unable to connect Fitness BLE GATT sensor %s for %s",
                        sensor.sensor_id, entry.entry_id, exc_info=True,
                    )
                    continue
                chosen[sensor.sensor_id] = "bluetooth"
                self._set_active_transport(sensor, "bluetooth")
            elif desired == "antplus":
                await self._claim_transport(entry.entry_id, "antplus")
                if current == "bluetooth" and bt_provider is not None:
                    disconnect_one = getattr(bt_provider, "async_disconnect_sensor", None)
                    if disconnect_one is not None:
                        await disconnect_one(entry.entry_id, sensor.sensor_id)
                chosen[sensor.sensor_id] = "antplus"
                self._set_active_transport(sensor, "antplus")
            elif current == "bluetooth" and bt_provider is not None:
                disconnect_one = getattr(bt_provider, "async_disconnect_sensor", None)
                if disconnect_one is not None:
                    await disconnect_one(entry.entry_id, sensor.sensor_id)
                chosen.pop(sensor.sensor_id, None)
                self._set_active_transport(sensor, None)

        # A profile keeps Bluetooth GATT only while at least one owned sensor needs it.
        # Shared physical locks remain independent of the connection lifetime.
        if "bluetooth" in self._profile_claims.get(entry.entry_id, set()):
            if not any(value == "bluetooth" for value in chosen.values()):
                await self._release_transport(entry.entry_id, "bluetooth")

    def _start_profile_handover_monitor(self, entry) -> None:
        existing = self._profile_handover_tasks.pop(entry.entry_id, None)
        if existing is not None and not existing.done():
            existing.cancel()
        candidates = set(self.selected_sensor_ids(entry)) | self.profile_claimed_sensor_ids(entry.entry_id)
        if not any(
            sensor_id in self.sensors
            and "antplus" in self.sensors[sensor_id].endpoints
            and "bluetooth" in self.sensors[sensor_id].endpoints
            for sensor_id in candidates
        ):
            return
        async def _monitor() -> None:
            try:
                while True:
                    await asyncio.sleep(TRANSPORT_HANDOVER_INTERVAL_SECONDS)
                    if entry.entry_id not in self.profile_entries:
                        return
                    await self._reconcile_profile_transports(entry)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.debug("Fitness live transport handover monitor failed", exc_info=True)
        task = self.hass.async_create_background_task(
            _monitor(), f"fitness live handover {entry.entry_id}", eager_start=False
        )
        self._profile_handover_tasks[entry.entry_id] = task

    async def async_prepare_session(self, entry) -> str:
        self.measurements.pop(entry.entry_id, None)
        self.measurement_sources.pop(entry.entry_id, None)
        self.measurement_time.pop(entry.entry_id, None)

        # Establish deterministic claim priority at Start/arm time. Earlier armed
        # sessions win a free sensor when several profiles are allowed to use it.
        self._session_order_counter += 1
        self._profile_session_order[entry.entry_id] = self._session_order_counter
        self._refresh_live_provider_gates()

        sensors = self.sensors_for_profile(entry)
        if sensors:
            # Low-frequency session-state refresh for conditional ownership
            # selectors. This is deliberately not tied to radio packets.
            self._notify_values_throttled(
                {(sensor.sensor_id, "workout_owner", None) for sensor in sensors}
            )
        # ANT reception is continuously available while the ANT+ adapter is enabled.
        # A profile waiting only on sensors locked to somebody else does not claim
        # those sensors; Bluetooth GATT is connected only after exclusive ownership
        # exists and fresh ANT+ is unavailable.
        ant_candidates = [
            sensor
            for sensor in sensors
            if "antplus" in sensor.endpoints
            and self.adapter_enabled("antplus")
            and self.sensor_workout_owner(sensor.sensor_id) in {None, entry.entry_id}
        ]
        if ant_candidates and self.adapter_enabled("antplus"):
            await self._claim_transport(entry.entry_id, "antplus")
        self._profile_sensor_transport[entry.entry_id] = {}

        # Do not pre-lock every recently seen assigned sensor. The session order
        # above establishes deterministic priority, while the next post-start
        # radio observation/measurement performs the actual physical claim. This
        # prevents an unused nearby shared sensor from being reserved merely
        # because it happened to advertise before Start was pressed.
        await self._reconcile_profile_transports(entry)
        self._start_profile_handover_monitor(entry)
        chosen = self._profile_sensor_transport.get(entry.entry_id, {})
        return ",".join(f"{sensor_id}:{transport}" for sensor_id, transport in sorted(chosen.items())) or "waiting_for_free_sensor"

    async def async_finish_session(self, entry, *, keep_heart_rate: bool = False) -> str:
        if not keep_heart_rate:
            task = self._profile_handover_tasks.pop(entry.entry_id, None)
            if task is not None and not task.done():
                task.cancel()
        claimed = set(self._profile_claims.get(entry.entry_id, set()))
        keep = self._heart_rate_transports(entry.entry_id) if keep_heart_rate else set()
        states: list[str] = []
        for transport in claimed:
            provider = self.providers.get(transport)
            if provider is None:
                continue
            keep_this = transport in keep
            await provider.async_disconnect_profile(entry.entry_id, keep_heart_rate=keep_this)
            if keep_this:
                states.append(f"{transport}:recovery")
                continue
            await self._release_transport(entry.entry_id, transport)
            states.append(f"{transport}:released")
        if not keep_heart_rate:
            for sensor_id in self._profile_sensor_transport.pop(entry.entry_id, {}):
                sensor = self.sensors.get(sensor_id)
                if sensor:
                    self._set_active_transport(sensor, None)
            self._profile_claims.pop(entry.entry_id, None)

        # Do NOT release physical sensor workout ownership here merely because
        # this profile stopped. A still-running overlapping profile must never
        # inherit a sensor which may still be worn by the original user. Locks
        # are released only when every armed/active/recovery session is idle.
        if not keep_heart_rate:
            self._clear_workout_sensor_locks_if_idle()
        assigned = self.sensors_for_profile(entry)
        if assigned:
            self._notify_values_throttled(
                {(sensor.sensor_id, "workout_owner", None) for sensor in assigned}
            )
        self._refresh_live_provider_gates()
        return ",".join(states) if states else "no_live_transport"

    async def async_finish_recovery(self, entry) -> str:
        return await self.async_finish_session(entry, keep_heart_rate=False)

    def publish(self, sensor_id: str, values: dict[str, float], *, transport: str | None = None) -> None:
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None:
            return
        transport = transport or sensor.transport
        transport_enabled = self.adapter_enabled(transport)

        previous_available = sensor.available
        endpoint = sensor.endpoints.get(transport)
        seen = datetime.now(timezone.utc)
        if endpoint is not None:
            endpoint.last_seen = seen
            endpoint.available = True

        # Physical sensor entities are the canonical raw measurements and remain
        # useful even when no profile has started a workout. Providers already
        # bound idle radio work (ANT samples accepted profiles; BLE passive updates
        # are deduplicated), while HA entity writes are coalesced below to 1 Hz.
        # Profile/session calculations stay completely gated later in this method.
        value_bucket = self.sensor_values.setdefault(sensor_id, {})
        transport_bucket = self.sensor_value_transport.setdefault(sensor_id, {})
        physical_dirty: set[tuple[str, str, str | None]] = set()
        packet_values: dict[str, float] = {}
        for key, raw in values.items():
            if not transport_enabled or key not in LIVE_METRICS or raw is None:
                continue
            value = float(raw)
            packet_values[key] = value
            if value_bucket.get(key) != value or transport_bucket.get(key) != transport:
                value_bucket[key] = value
                transport_bucket[key] = transport
                physical_dirty.add((sensor_id, "metric", key))

        if transport == "antplus" and self.bluetooth_gatt_connected(sensor_id):
            self._schedule_sensor_claim_reconcile(sensor_id)
        physical_dirty.update(self._mark_last_seen_change(sensor_id, seen))
        if previous_available != sensor.available:
            physical_dirty.add((sensor_id, "availability", None))
        if physical_dirty and self.sensor_is_accepted(sensor_id):
            self._notify_values_throttled(physical_dirty)

        # Stop here while idle: raw values above belong to the physical device,
        # whereas profile Live Workout calculations only run inside an actual
        # armed/active/recovery epoch. Assignment alone must never activate them.
        if not self._global_workout_epoch_active():
            return

        if not transport_enabled or not packet_values:
            return

        now = seen
        owner = self._claim_sensor_for_workout(sensor_id)
        if owner is None:
            return
        entry = self.profile_entries.get(owner)
        manager = self._manager_for_profile(owner)
        if entry is None or manager is None:
            return
        # A stopped original owner remains the lock owner while another profile's
        # overlapping workout is still running. In that state measurements are
        # intentionally discarded rather than handed over mid-session. Recovery
        # remains allowed for the original owner.
        if not (
            manager.session_armed
            or manager.session_active
            or getattr(manager, "recovery_active", False)
        ):
            return

        desired = self.choose_transport(sensor)
        chosen_map = self._profile_sensor_transport.setdefault(owner, {})
        chosen = chosen_map.get(sensor_id)
        if desired is not None and desired != chosen:
            # Accept a packet from the newly preferred transport immediately,
            # but do NOT overwrite the old chosen transport yet. The async
            # reconciler needs to see current=bluetooth, desired=antplus so it can
            # explicitly disconnect GATT before committing the handover.
            self._schedule_sensor_claim_reconcile(sensor_id)
            if transport != desired:
                return
        elif chosen is not None and transport != chosen:
            return
        if desired is not None and transport != desired:
            return

        bucket = self.measurements.setdefault(owner, {})
        source_bucket = self.measurement_sources.setdefault(owner, {})
        for key, value in packet_values.items():
            bucket[key] = value
            source_bucket[key] = sensor_id
        self.measurement_time[owner] = now
        if manager.session_armed or manager.session_active:
            self._notify_profile_live_throttled(owner, manager)

    def live_values(self, entry_id: str) -> dict[str, float | None]:
        values = self.measurements.get(entry_id, {})
        return {key: values.get(key) for key in LIVE_METRICS}

    def sensor_transport_details(self, sensor_id: str) -> dict[str, Any]:
        sensor = self.sensors.get(self.resolve_sensor_id(sensor_id))
        if sensor is None:
            return {}
        return {
            transport: {
                "address": endpoint.address,
                "endpoint_id": endpoint.endpoint_id,
                "available": endpoint.available,
                "rssi": endpoint.rssi,
                "source": endpoint.source,
                "last_seen": endpoint.last_seen.isoformat() if endpoint.last_seen else None,
                "capabilities": sorted(endpoint.capabilities),
                **endpoint.metadata,
            }
            for transport, endpoint in sensor.endpoints.items()
        }

    async def async_shutdown(self) -> None:
        for provider in list(self.providers.values()):
            await provider.async_shutdown()
        self.providers.clear()
        self._transport_claims.clear()
        self._profile_claims.clear()
        self._profile_sensor_transport.clear()
        self._sensor_workout_owner.clear()
        self._profile_claimed_sensors.clear()
        self._profile_session_order.clear()
        self._sensor_claim_reconcile_pending.clear()
        self._sensor_claim_reconcile_last_attempt.clear()
        for task in self._profile_handover_tasks.values():
            task.cancel()
        self._profile_handover_tasks.clear()
        for handle in self._profile_live_notify_handles.values():
            handle.cancel()
        self._profile_live_notify_handles.clear()
        self._profile_last_live_notify_monotonic.clear()
        if self._value_notify_handle is not None:
            self._value_notify_handle.cancel()
            self._value_notify_handle = None
        if self._save_handle is not None:
            self._save_handle.cancel()
            self._save_handle = None
            self._save_pending = False
        if self._structure_notify_handle is not None:
            self._structure_notify_handle.cancel()
            self._structure_notify_handle = None
        self._pending_sensor_value_changes.clear()


def get_live_runtime(hass: HomeAssistant) -> LiveRuntime:
    domain_data = hass.data.setdefault(DOMAIN, {})
    runtime = domain_data.get("_live_runtime")
    if runtime is None:
        runtime = LiveRuntime(hass)
        domain_data["_live_runtime"] = runtime
    return runtime
