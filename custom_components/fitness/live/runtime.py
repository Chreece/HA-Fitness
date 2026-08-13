"""Global live-workout transport runtime for Fitness."""
from __future__ import annotations

import asyncio
import hashlib
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
TRANSPORT_PRIORITY = ("antplus", "bluetooth")
HUB_ENTRY_TYPE = "live_hub"
HUB_UNIQUE_ID = "local_sensors"
HUB_DEVICE_ID = "sensors_adapters"
SENSOR_COLLECTION_DEVICE_ID = "sensors"  # legacy v2 device identifier; removed by migration
SENSORS_SUBENTRY_TYPE = "sensors"
SENSORS_SUBENTRY_UNIQUE_ID = "fitness_sensors"
ADAPTERS_SUBENTRY_TYPE = "adapters"
ADAPTERS_SUBENTRY_UNIQUE_ID = "fitness_adapters"
ADAPTER_DEVICE_MODEL_VERSION = 1


def _clean(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _normalize_name(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return "Fitness sensor"
    # Stryd uses StrydX as its BLE advertised name; that is a transport-facing
    # advertisement label, not the physical product name users should see.
    if _clean(text).startswith("stryd"):
        return "Stryd"
    return text


def _serial(metadata: dict[str, Any]) -> str | None:
    for key in ("serial_number", "serial_no", "serial", "device_serial"):
        value = metadata.get(key)
        if value not in (None, "", 0, "0"):
            return _clean(value)
    return None


def _family(name: str, metadata: dict[str, Any]) -> str | None:
    haystack = " ".join(
        str(x or "")
        for x in (name, metadata.get("manufacturer"), metadata.get("model"))
    ).lower()
    if "stryd" in haystack:
        return "stryd"
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
        self.adapters_subentry_id: str | None = None
        self.measurements: dict[str, dict[str, float]] = {}
        self.measurement_sources: dict[str, dict[str, str]] = {}
        self.measurement_time: dict[str, datetime] = {}
        self.sensor_values: dict[str, dict[str, float]] = {}
        self.sensor_value_transport: dict[str, dict[str, str]] = {}
        self._listeners: set[Any] = set()
        self._transport_claims: dict[str, set[str]] = {}
        self._transport_baseline: dict[str, bool] = {}
        self._profile_claims: dict[str, set[str]] = {}
        self._profile_sensor_transport: dict[str, dict[str, str]] = {}
        self._store = Store[dict[str, Any]](
            hass, LIVE_ADAPTER_STORE_VERSION, LIVE_ADAPTER_STORE_KEY, private=True
        )
        self._configured = {name: False for name in TRANSPORTS}
        self._enabled = {name: False for name in TRANSPORTS}
        self._initialized = False
        self._discovery_started: set[str] = set()
        self._setup_discovery_baseline: dict[str, bool] = {}
        self._save_pending = False
        self._hub_reload_pending = False
        # Lightweight radio presence tracking. This layer deliberately does not
        # import/load the Fitness Bluetooth or ANT+ provider modules.
        self._adapter_presence = {name: False for name in TRANSPORTS}
        self._remote_ant_last_seen: dict[str, float] = {}
        self._presence_task = None
        self._presence_unsubs: list[Any] = []
        self._presence_started = False
        self._profile_reload_pending = False
        self.sensor_passive_values: dict[str, dict[str, Any]] = {}
        self.sensor_passive_meta: dict[str, dict[str, dict[str, Any]]] = {}
        self._device_registry_unsub = None
        self._sensor_device_ids: dict[str, str] = {}

    async def async_initialize(self) -> None:
        if self._initialized:
            return
        stored = await self._store.async_load() or {}
        enabled = stored.get("enabled") or {}
        adapter_model = int(stored.get("adapter_device_model") or 0)

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
                    endpoint = TransportEndpoint(
                        transport=transport,
                        endpoint_id=str(raw["endpoint_id"]),
                        address=raw.get("address"),
                        capabilities=set(raw.get("capabilities") or []),
                        source=raw.get("source"),
                        rssi=raw.get("rssi"),
                        available=False,
                        metadata=dict(raw.get("metadata") or {}),
                    )
                    sensor.endpoints[transport] = endpoint
                    self.endpoint_aliases[endpoint.endpoint_id] = sensor.sensor_id
                self.sensors[sensor.sensor_id] = sensor
            except Exception:
                continue

        self._initialized = True
        if adapter_model < ADAPTER_DEVICE_MODEL_VERSION:
            # Persist the new disabled-by-default adapter model outside the
            # profile setup critical path.
            self._schedule_save()

    def _serialize_sensors(self) -> list[dict[str, Any]]:
        result = []
        for sensor in self.sensors.values():
            result.append(
                {
                    "sensor_id": sensor.sensor_id,
                    "name": sensor.name,
                    "capabilities": sorted(sensor.capabilities),
                    "metadata": dict(sensor.metadata),
                    "endpoints": {
                        transport: {
                            "endpoint_id": endpoint.endpoint_id,
                            "address": endpoint.address,
                            "capabilities": sorted(endpoint.capabilities),
                            "source": endpoint.source,
                            "rssi": endpoint.rssi,
                            "metadata": dict(endpoint.metadata),
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
            }
        )

    def _schedule_save(self) -> None:
        if self._save_pending:
            return
        self._save_pending = True

        async def _save():
            await asyncio.sleep(0)
            self._save_pending = False
            await self._async_save_adapter_config()

        self.hass.async_create_task(_save())

    def adapter_present(self, transport: str) -> bool:
        """Return hardware/gateway presence independent of module enabled state."""
        return bool(self._adapter_presence.get(transport, False))

    @property
    def present_transports(self) -> set[str]:
        return {name for name in TRANSPORTS if self.adapter_present(name)}

    @property
    def adapter_entity_transports(self) -> set[str]:
        # Keep an already-enabled module controllable if its hardware disappears,
        # but do not create never-seen adapter devices without real HA hardware.
        return self.present_transports | {
            name for name in TRANSPORTS if self.adapter_enabled(name)
        }

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
        if transport not in TRANSPORTS:
            return
        present = bool(present)
        old_live = self.live_available
        old = self._adapter_presence.get(transport, False)
        if old == present:
            return
        self._adapter_presence[transport] = present
        self._notify()
        if self.hub_entry is not None:
            self.request_hub_reload()
        if old_live != self.live_available:
            self._schedule_profile_reloads()

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
                return bool(counter(self.hass))
            except TypeError:
                return bool(counter(self.hass, connectable=False))
        except Exception:
            return False

    async def async_refresh_adapter_presence(self) -> None:
        """Refresh cheap adapter presence without loading Fitness transport modules."""
        bt = self._bluetooth_scanner_present()
        local_ant = await self._async_scan_local_ant_usb()
        now = time.monotonic()
        self._remote_ant_last_seen = {
            gateway: seen
            for gateway, seen in self._remote_ant_last_seen.items()
            if now - seen <= 45.0
        }
        ant = local_ant or bool(self._remote_ant_last_seen)
        self.set_adapter_presence("bluetooth", bt)
        self.set_adapter_presence("antplus", ant)
        if self.live_available and self.hub_entry is None:
            await self.async_ensure_hub_for_presence()
        elif self.hub_entry is not None:
            self._rediscover_missing_present_adapters()

    def _rediscover_missing_present_adapters(self) -> None:
        if self.hub_entry is None:
            return
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        for transport in self.present_transports:
            device = registry.async_get_device_by_identifier(
                (DOMAIN, f"live_adapter:{transport}"), self.hub_entry.entry_id
            )
            if device is None:
                self.request_hub_reload()
                return

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

    def cleanup_profile_live_registry(self, entry) -> None:
        """Remove the per-user Live Workout surface when no adapter is present."""
        if self.live_surface_available:
            return
        from homeassistant.helpers import device_registry as dr
        from homeassistant.helpers import entity_registry as er
        devices = dr.async_get(self.hass)
        entities = er.async_get(self.hass)
        device = devices.async_get_device_by_identifier(
            (DOMAIN, f"{entry.entry_id}_live"), entry.entry_id
        )
        if device is None:
            return
        for entity in list(entities.entities.values()):
            if entity.platform == DOMAIN and entity.device_id == device.id:
                entities.async_remove(entity.entity_id)
        devices.async_remove_device(device.id)

    def _schedule_profile_reloads(self) -> None:
        if self._profile_reload_pending:
            return
        self._profile_reload_pending = True
        async def _reload() -> None:
            try:
                for entry in tuple(self.profile_entries.values()):
                    await self.hass.config_entries.async_reload(entry.entry_id)
            finally:
                self._profile_reload_pending = False
        self.hass.async_create_task(_reload())

    def _start_presence_monitor(self) -> None:
        """Start lightweight adapter presence monitoring after HA startup."""
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
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _LOGGER.debug(
                        "Fitness adapter presence refresh failed",
                        exc_info=True,
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
        """Publish low-rate connectionless telemetry such as BLE battery."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        if sensor_id not in self.sensors or not values:
            return
        bucket = self.sensor_passive_values.setdefault(sensor_id, {})
        changed = False
        for key, value in values.items():
            if bucket.get(key) != value:
                bucket[key] = value
                changed = True
        if metadata:
            meta = self.sensor_passive_meta.setdefault(sensor_id, {})
            for key, item in metadata.items():
                if meta.get(key) != item:
                    meta[key] = dict(item)
                    changed = True
        if changed and self.sensor_is_accepted(sensor_id):
            self._notify()
            self.request_hub_reload()

    def forget_sensor(self, sensor_id: str) -> None:
        """Forget an accepted physical sensor so a future transmission rediscovers it."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.pop(sensor_id, None)
        if sensor is None:
            return
        for endpoint in sensor.endpoints.values():
            self.endpoint_aliases.pop(endpoint.endpoint_id, None)
        self.sensor_values.pop(sensor_id, None)
        self.sensor_value_transport.pop(sensor_id, None)
        self.sensor_passive_values.pop(sensor_id, None)
        self.sensor_passive_meta.pop(sensor_id, None)
        self._discovery_started.discard(sensor_id)
        for entry in tuple(self.profile_entries.values()):
            ids = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
            if sensor_id in ids:
                ids = [item for item in ids if item != sensor_id]
                options = dict(entry.options)
                options[CONF_LIVE_SENSOR_IDS] = ids
                self.hass.config_entries.async_update_entry(entry, options=options)
        self._schedule_save()
        self._schedule_profile_reloads()

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
        self.hub_entry = entry
        self._start_presence_monitor()
        self._listen_for_registry_deletions()
        self._cleanup_legacy_profile_infrastructure()
        self.ensure_adapters_subentry()
        self.ensure_sensors_subentry()
        self._remove_legacy_grouping_devices()
        self._migrate_adapter_devices_to_subentry()
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
            self.hub_entry = None
            self.sensors_subentry_id = None
            self.adapters_subentry_id = None

    def ensure_adapters_subentry(self):
        """Ensure the adapter config subentry exists on the hub entry."""
        if self.hub_entry is None:
            return None
        for subentry in self.hub_entry.subentries.values():
            if (
                subentry.subentry_type == ADAPTERS_SUBENTRY_TYPE
                or subentry.unique_id == ADAPTERS_SUBENTRY_UNIQUE_ID
            ):
                self.adapters_subentry_id = subentry.subentry_id
                if subentry.title != "Adapters":
                    self.hass.config_entries.async_update_subentry(
                        self.hub_entry, subentry, title="Adapters"
                    )
                return subentry
        subentry = ConfigSubentry(
            data=MappingProxyType({}),
            subentry_type=ADAPTERS_SUBENTRY_TYPE,
            title="Adapters",
            unique_id=ADAPTERS_SUBENTRY_UNIQUE_ID,
        )
        self.hass.config_entries.async_add_subentry(self.hub_entry, subentry)
        self.adapters_subentry_id = subentry.subentry_id
        return subentry

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

    def _adapters_subentry_id(self) -> str | None:
        if self.adapters_subentry_id:
            return self.adapters_subentry_id
        subentry = self.ensure_adapters_subentry()
        return subentry.subentry_id if subentry is not None else None

    def _migrate_adapter_devices_to_subentry(self) -> None:
        """Move existing adapter devices from the parent entry into Adapters."""
        if self.hub_entry is None:
            return
        subentry_id = self._adapters_subentry_id()
        if subentry_id is None:
            return
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        for transport in TRANSPORTS:
            device = registry.async_get_device_by_identifier(
                (DOMAIN, f"live_adapter:{transport}"), self.hub_entry.entry_id
            )
            if device is not None and device.config_subentry_id != subentry_id:
                registry.async_update_device(
                    device.id,
                    new_config_subentry_id=subentry_id,
                    via_device_id=None,
                )

    def _sensor_subentry_id(self) -> str | None:
        if self.sensors_subentry_id:
            return self.sensors_subentry_id
        subentry = self.ensure_sensors_subentry()
        return subentry.subentry_id if subentry is not None else None


    def ant_receiver_records(self) -> dict[str, Any]:
        provider = self.providers.get("antplus")
        manager = getattr(provider, "adapter_manager", None) if provider else None
        return dict(getattr(manager, "records", {}) or {})

    def ant_receiver_device_info(self, stable_key: str):
        from homeassistant.helpers.device_registry import DeviceInfo
        record = self.ant_receiver_records().get(stable_key)
        if record is None:
            return DeviceInfo(
                identifiers={(DOMAIN, f"usb_adapter:{stable_key}")},
                name=stable_key,
                manufacturer="ANT+",
                model="ANT+ receiver",
            )
        adapter = record.adapter
        return DeviceInfo(
            identifiers={adapter.ha_identifier},
            name=adapter.name,
            manufacturer=adapter.manufacturer or "Dynastream / Garmin",
            model=adapter.product or f"ANT USB {adapter.vid}:{adapter.pid}",
            serial_number=adapter.serial,
        )

    def adapter_device_info(self, transport: str):
        from homeassistant.helpers.device_registry import DeviceInfo
        label = "ANT+ Adapter" if transport == "antplus" else "Bluetooth Adapter"
        translation_key = "antplus_adapter" if transport == "antplus" else "bluetooth_adapter"
        return DeviceInfo(
            identifiers={(DOMAIN, f"live_adapter:{transport}")},
            translation_key=translation_key,
            name=label,
            manufacturer="Fitness",
            model=label,
        )

    def sensor_device_info(self, sensor_id: str):
        from homeassistant.helpers.device_registry import DeviceInfo
        sensor = self.sensors.get(self.resolve_sensor_id(sensor_id))
        if sensor is None:
            return DeviceInfo(
                identifiers={(DOMAIN, f"live_sensor:{sensor_id}")},
                name=str(sensor_id),
                manufacturer="Fitness",
                model="Local fitness sensor",
            )
        identifiers = {(DOMAIN, f"live_sensor:{sensor.sensor_id}")}
        for endpoint in sensor.endpoints.values():
            identifiers.add((DOMAIN, f"endpoint:{endpoint.endpoint_id}"))
        manufacturer = sensor.metadata.get("manufacturer") or "Fitness sensor"
        model = sensor.metadata.get("model") or sensor.name
        serial = sensor.metadata.get("serial_number") or sensor.metadata.get("serial_no")
        return DeviceInfo(
            identifiers=identifiers,
            name=sensor.name,
            manufacturer=str(manufacturer),
            model=str(model),
            serial_number=str(serial) if serial not in (None, "") else None,
        )

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

    async def async_set_transport_enabled(self, transport: str, enabled: bool) -> None:
        if not self.adapter_configured(transport):
            if not enabled:
                return
            self._configured[transport] = True
        self._enabled[transport] = bool(enabled)
        await self._async_save_adapter_config()
        if enabled:
            await self.async_ensure_hub_entry()
        await self.async_refresh_modules()
        self._notify()

    async def async_register_profile(self, entry) -> None:
        await self.async_initialize()
        self.profile_entries[entry.entry_id] = entry
        self._start_presence_monitor()
        self._listen_for_registry_deletions()
        self._restore_legacy_profile_selections(entry)
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
                self._transport_baseline.pop(name, None)

    async def async_begin_setup_discovery(self) -> None:
        await self.async_initialize()
        if self._setup_discovery_baseline:
            return
        for transport in TRANSPORTS:
            provider = self.providers.get(transport)
            if provider is None:
                continue
            self._setup_discovery_baseline[transport] = bool(provider.capture_active)
            if not provider.capture_active:
                await provider.async_start_capture()

    async def async_end_setup_discovery(self) -> None:
        baseline = dict(self._setup_discovery_baseline)
        self._setup_discovery_baseline.clear()
        for transport, was_active in baseline.items():
            provider = self.providers.get(transport)
            if provider is None or self.transport_in_use(transport):
                continue
            if was_active and not provider.capture_active:
                await provider.async_start_capture()
            elif not was_active and provider.capture_active:
                await provider.async_stop_capture()

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

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                continue

    def notify_changed(self) -> None:
        """Notify adapter/sensor entities after an explicit runtime state change."""
        self._notify()

    def _new_physical_id(self, endpoint_id: str) -> str:
        digest = hashlib.sha1(endpoint_id.encode("utf-8")).hexdigest()[:16]
        return f"sensor:{digest}"

    def resolve_sensor_id(self, sensor_id: str) -> str:
        return self.endpoint_aliases.get(str(sensor_id), str(sensor_id))

    def _select_merge_primary(self, a: LiveSensor, b: LiveSensor) -> tuple[LiveSensor, LiveSensor]:
        if bool(a.metadata.get("accepted")) != bool(b.metadata.get("accepted")):
            return (a, b) if a.metadata.get("accepted") else (b, a)
        if ("antplus" in a.endpoints) != ("antplus" in b.endpoints):
            return (a, b) if "antplus" in a.endpoints else (b, a)
        return a, b

    def _merge_physical_sensors(self, a: LiveSensor, b: LiveSensor) -> LiveSensor:
        if a.sensor_id == b.sensor_id:
            return a
        primary, secondary = self._select_merge_primary(a, b)
        for transport, endpoint in secondary.endpoints.items():
            if transport not in primary.endpoints:
                primary.endpoints[transport] = endpoint
            self.endpoint_aliases[endpoint.endpoint_id] = primary.sensor_id
        self.endpoint_aliases[secondary.sensor_id] = primary.sensor_id
        primary.capabilities.update(secondary.capabilities)
        primary.metadata.update({k: v for k, v in secondary.metadata.items() if v not in (None, "", {}, [])})
        if secondary.metadata.get("accepted"):
            primary.metadata["accepted"] = True
        if primary.name == "Fitness sensor" or _family(secondary.name, secondary.metadata):
            primary.name = _normalize_name(secondary.name)
        if secondary.sensor_id in self.sensor_values:
            primary_values = self.sensor_values.setdefault(primary.sensor_id, {})
            primary_values.update(self.sensor_values.pop(secondary.sensor_id))
        if secondary.sensor_id in self.sensor_value_transport:
            primary_sources = self.sensor_value_transport.setdefault(primary.sensor_id, {})
            primary_sources.update(self.sensor_value_transport.pop(secondary.sensor_id))
        self.sensors.pop(secondary.sensor_id, None)
        self._cleanup_merged_registry_sensor(secondary.sensor_id)
        self._schedule_save()
        self.request_hub_reload()
        return primary

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

    def _match_sensor(self, endpoint: TransportEndpoint, name: str) -> LiveSensor | None:
        current = None
        if endpoint.endpoint_id in self.endpoint_aliases:
            current = self.sensors.get(self.resolve_sensor_id(self.endpoint_aliases[endpoint.endpoint_id]))

        serial = _serial(endpoint.metadata)
        if serial:
            candidates = [
                sensor for sensor in self.sensors.values()
                if sensor is not current
                and any(_serial(ep.metadata) == serial for ep in sensor.endpoints.values())
            ]
            if len(candidates) == 1:
                return self._merge_physical_sensors(current, candidates[0]) if current else candidates[0]

        fam = _family(name, endpoint.metadata)
        if fam:
            candidates = [
                sensor for sensor in self.sensors.values()
                if sensor is not current
                and _family(sensor.name, sensor.metadata) == fam
                and endpoint.transport not in sensor.endpoints
                and bool(sensor.capabilities & endpoint.capabilities)
            ]
            if len(candidates) == 1:
                return self._merge_physical_sensors(current, candidates[0]) if current else candidates[0]

        # Do not merge arbitrary same-name devices. Two people may own identical
        # HR straps/power meters, and a model/local name is not a physical identity.
        # Generic cross-transport merging therefore requires a strong serial identity.
        # Known families with a stable protocol relationship (currently Stryd) are
        # handled above. Unknown devices remain separate until a stronger identity is
        # learned (for example through Bluetooth Device Information) or the user merges
        # them explicitly in a future flow.
        return current

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
        endpoint = TransportEndpoint(
            transport=transport,
            endpoint_id=endpoint_id,
            address=address,
            capabilities=set(capabilities),
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

        sensor.endpoints[transport] = endpoint
        sensor.capabilities.update(capabilities)
        self.endpoint_aliases[endpoint_id] = sensor.sensor_id

        # Prefer actual product metadata over advertisement labels.
        manufacturer = metadata.get("manufacturer")
        model = metadata.get("model")
        serial_no = metadata.get("serial_number") or metadata.get("serial_no")
        if manufacturer:
            sensor.metadata["manufacturer"] = manufacturer
        if model:
            sensor.metadata["model"] = model
        if serial_no not in (None, ""):
            sensor.metadata["serial_number"] = serial_no
        sensor.metadata.setdefault("transport_details", {})[transport] = {
            "endpoint_id": endpoint_id,
            "address": address,
            **metadata,
        }
        display = _normalize_name(name)
        if sensor.name == "Fitness sensor" or _family(display, metadata):
            sensor.name = display

        structural_change = (
            is_new
            or previous_endpoint is None
            or previous_endpoint.address != endpoint.address
            or previous_endpoint.capabilities != endpoint.capabilities
            or previous_endpoint.source != endpoint.source
            or previous_endpoint.available != endpoint.available
            or previous_endpoint.metadata != endpoint.metadata
            or sensor.name != previous_name
            or sensor.metadata != previous_metadata
            or sensor.capabilities != previous_caps
        )

        # RSSI and last_seen are intentionally volatile. Passive advertisements can
        # arrive several times per second, so they must not cause storage writes,
        # entity-registry creation, hub reloads, or state updates on every packet.
        if structural_change:
            self._schedule_save()
        if self.hub_entry is not None and self.sensor_is_accepted(sensor.sensor_id):
            self.ensure_sensor_device(sensor.sensor_id)
        if is_new and self.profile_entries:
            self._schedule_sensor_discovery(sensor.sensor_id)
        if structural_change and self.sensor_is_accepted(sensor.sensor_id):
            self.request_hub_reload()
        if structural_change:
            self._notify()
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

    def _schedule_sensor_discovery(self, sensor_id: str) -> None:
        sensor_id = self.resolve_sensor_id(sensor_id)
        if sensor_id in self._discovery_started:
            return
        if any(sensor_id in set(self.selected_sensor_ids(entry)) for entry in self.profile_entries.values()):
            return
        from homeassistant.helpers import device_registry as dr
        if self.hub_entry is not None:
            registry = dr.async_get(self.hass)
            if registry.async_get_device_by_identifier(
                (DOMAIN, f"live_sensor:{sensor_id}"),
                self.hub_entry.entry_id,
            ) is not None:
                # Device existence alone is not assignment, but an accepted sensor
                # is marked below in metadata to suppress repetitive discovery.
                if self.sensors[sensor_id].metadata.get("accepted"):
                    return
        self._discovery_started.add(sensor_id)
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "integration_discovery"},
                data={"sensor_id": sensor_id},
            )
        )

    def sensor_is_accepted(self, sensor_id: str) -> bool:
        """Return whether a discovered physical sensor belongs in HA's device registry."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None:
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
            sensor.metadata["accepted"] = True
            self._schedule_save()
            self.ensure_sensor_device(sensor_id)
            self.request_hub_reload()

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

        device = registry.async_get_or_create(
            config_entry_id=self.hub_entry.entry_id,
            config_subentry_id=subentry_id,
            identifiers=set(info["identifiers"]),
            name=info.get("name"),
            manufacturer=info.get("manufacturer"),
            model=info.get("model"),
            serial_number=info.get("serial_number"),
        )
        self._sensor_device_ids[sensor_id] = device.id

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

        self.hass.async_create_task(_reload())

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

    def choose_transport(self, sensor: LiveSensor) -> str | None:
        ant_endpoint = sensor.endpoints.get("antplus")
        ant_provider = self.providers.get("antplus")
        if (
            ant_endpoint is not None
            and ant_provider is not None
            and self.adapter_enabled("antplus")
            and (ant_endpoint.available or bool(getattr(ant_provider, "available", False)))
        ):
            return "antplus"
        bt_endpoint = sensor.endpoints.get("bluetooth")
        bt_provider = self.providers.get("bluetooth")
        if bt_endpoint is not None and bt_provider is not None and self.adapter_enabled("bluetooth"):
            return "bluetooth"
        return None

    def _session_plan(self, entry) -> dict[str, list[LiveSensor]]:
        plan: dict[str, list[LiveSensor]] = {}
        chosen: dict[str, str] = {}
        for sensor in self.sensors_for_profile(entry):
            transport = self.choose_transport(sensor)
            if transport is None:
                continue
            chosen[sensor.sensor_id] = transport
            sensor.active_transport = transport
            plan.setdefault(transport, []).append(sensor)
        self._profile_sensor_transport[entry.entry_id] = chosen
        return plan

    async def _claim_transport(self, entry_id: str, transport: str) -> None:
        provider = self.providers.get(transport)
        if provider is None:
            return
        claims = self._transport_claims.setdefault(transport, set())
        if not claims:
            self._transport_baseline[transport] = bool(provider.capture_active)
        claims.add(entry_id)
        self._profile_claims.setdefault(entry_id, set()).add(transport)
        if not provider.capture_active:
            await provider.async_start_capture()

    async def _release_transport(self, entry_id: str, transport: str) -> None:
        provider = self.providers.get(transport)
        claims = self._transport_claims.setdefault(transport, set())
        claims.discard(entry_id)
        self._profile_claims.setdefault(entry_id, set()).discard(transport)
        if claims or provider is None:
            return
        baseline = self._transport_baseline.pop(transport, False)
        if baseline and not provider.capture_active:
            await provider.async_start_capture()
        elif not baseline and provider.capture_active:
            await provider.async_stop_capture()
        self._transport_claims.pop(transport, None)

    async def async_prepare_session(self, entry) -> str:
        self.measurements.pop(entry.entry_id, None)
        self.measurement_sources.pop(entry.entry_id, None)
        self.measurement_time.pop(entry.entry_id, None)
        plan = self._session_plan(entry)
        states: list[str] = []
        for transport, sensors in plan.items():
            provider = self.providers.get(transport)
            if provider is None:
                continue
            await self._claim_transport(entry.entry_id, transport)
            await provider.async_connect_profile(entry.entry_id, sensors)
            states.append(f"{transport}:{'active' if provider.capture_active else 'waiting'}")
        return ",".join(states) if states else "no_live_transport"

    def _heart_rate_transports(self, entry_id: str) -> set[str]:
        source = self.measurement_sources.get(entry_id, {}).get(METRIC_HEART_RATE)
        if not source:
            return set()
        return {self._profile_sensor_transport.get(entry_id, {}).get(source)} - {None}

    async def async_finish_session(self, entry, *, keep_heart_rate: bool = False) -> str:
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
            states.append(f"{transport}:{'active' if provider.capture_active else 'idle'}")
        if not keep_heart_rate:
            for sensor_id in self._profile_sensor_transport.pop(entry.entry_id, {}):
                sensor = self.sensors.get(sensor_id)
                if sensor:
                    sensor.active_transport = None
            self._profile_claims.pop(entry.entry_id, None)
        return ",".join(states) if states else "no_live_transport"

    async def async_finish_recovery(self, entry) -> str:
        return await self.async_finish_session(entry, keep_heart_rate=False)

    def publish(self, sensor_id: str, values: dict[str, float], *, transport: str | None = None) -> None:
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if sensor is None:
            return
        transport = transport or sensor.transport
        self.sensor_values.setdefault(sensor_id, {}).update(
            {key: float(value) for key, value in values.items() if key in LIVE_METRICS and value is not None}
        )
        for key, value in values.items():
            if key in LIVE_METRICS and value is not None:
                self.sensor_value_transport.setdefault(sensor_id, {})[key] = transport
        endpoint = sensor.endpoints.get(transport)
        if endpoint:
            endpoint.last_seen = datetime.now(timezone.utc)
            endpoint.available = True

        now = datetime.now(timezone.utc)
        for entry in self.profile_entries.values():
            if sensor_id not in set(self.selected_sensor_ids(entry)):
                continue
            chosen = self._profile_sensor_transport.get(entry.entry_id, {}).get(sensor_id)
            # Strict transport ownership: when ANT+ wins for this physical device,
            # BLE advertisements/GATT notifications cannot leak into the workout.
            if chosen is not None and transport != chosen:
                continue
            bucket = self.measurements.setdefault(entry.entry_id, {})
            source_bucket = self.measurement_sources.setdefault(entry.entry_id, {})
            changed = False
            for key in LIVE_METRICS:
                if values.get(key) is not None:
                    bucket[key] = float(values[key])
                    source_bucket[key] = sensor_id
                    changed = True
            if changed:
                self.measurement_time[entry.entry_id] = now
                manager = self.hass.data.get(DOMAIN, {}).get(entry.entry_id)
                if manager is not None:
                    manager._async_live_source_change(None)
        self._notify()

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
        self._transport_baseline.clear()
        self._profile_claims.clear()
        self._profile_sensor_transport.clear()
        self._setup_discovery_baseline.clear()


def get_live_runtime(hass: HomeAssistant) -> LiveRuntime:
    domain_data = hass.data.setdefault(DOMAIN, {})
    runtime = domain_data.get("_live_runtime")
    if runtime is None:
        runtime = LiveRuntime(hass)
        domain_data["_live_runtime"] = runtime
    return runtime
