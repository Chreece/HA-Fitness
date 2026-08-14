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
        self._discovery_tasks: dict[str, asyncio.Task] = {}
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
        # Sensor IDs explicitly deleted by the user must be rediscovered and
        # reassigned before they may become HA devices again. Persist this set
        # so a restart cannot resurrect an accepted sensor from stale profile/store state.
        self._requires_reassignment: set[str] = set()

    async def async_initialize(self) -> None:
        if self._initialized:
            return
        stored = await self._store.async_load() or {}
        enabled = stored.get("enabled") or {}
        adapter_model = int(stored.get("adapter_device_model") or 0)
        self._requires_reassignment = {
            str(item) for item in (stored.get("requires_reassignment") or []) if str(item)
        }

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
                "requires_reassignment": sorted(self._requires_reassignment),
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

        self.hass.async_create_background_task(
            _save(),
            "fitness persist live sensor topology",
            eager_start=False,
        )

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
        """Update physical radio presence and auto-load a newly detected backend.

        Presence detection itself is always active.  A false->true transition
        automatically enables the corresponding Fitness backend so the detected
        hardware/proxy/gateway can immediately discover receivers and sensors.
        A user may still disable the backend while the hardware remains present;
        it is auto-enabled again only after a genuine disappear/reappear cycle.
        """
        if transport not in TRANSPORTS:
            return
        present = bool(present)
        old_live = self.live_available
        old = self._adapter_presence.get(transport, False)
        if old == present:
            return
        self._adapter_presence[transport] = present

        if present and not self.adapter_enabled(transport):
            async def _enable_detected_backend() -> None:
                try:
                    await self.async_set_transport_enabled(transport, True)
                except Exception:
                    _LOGGER.exception(
                        "Unable to auto-enable detected Fitness %s backend",
                        transport,
                    )

            if self.hass.state is CoreState.running:
                self.hass.async_create_background_task(
                    _enable_detected_backend(),
                    f"fitness auto-enable {transport} backend",
                )

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
        self.hass.async_create_background_task(
            _reload(),
            "fitness reload live profiles",
            eager_start=False,
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
                    self.ensure_ant_receiver_topology()
                    self._prune_stale_sensor_discovery_flows()
                    # Discovery is low-rate control-plane work. Retrying here means
                    # an RF device confirmed before profiles loaded, or a discovery
                    # flow that was dismissed/aborted, can become discoverable again
                    # without putting per-packet work back on Home Assistant's loop.
                    if self.profile_entries:
                        for sensor in tuple(self.sensors.values()):
                            if (
                                sensor.available
                                and sensor.capabilities
                                and self.sensor_recently_observed(sensor.sensor_id)
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
        """Publish low-rate connectionless telemetry such as BLE battery."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        if sensor_id not in self.sensors or not values:
            return
        bucket = self.sensor_passive_values.setdefault(sensor_id, {})
        changed_keys: set[str] = set()
        structure_changed = False
        for key, value in values.items():
            if key not in bucket:
                structure_changed = True
            if bucket.get(key) != value:
                bucket[key] = value
                changed_keys.add(key)
        if metadata:
            meta = self.sensor_passive_meta.setdefault(sensor_id, {})
            for key, item in metadata.items():
                if meta.get(key) != item:
                    meta[key] = dict(item)
                    changed_keys.add(key)
        if changed_keys and self.sensor_is_accepted(sensor_id):
            if structure_changed:
                self._notify_structure()
            self._notify_values_throttled(
                {(sensor_id, "passive", key) for key in changed_keys}
            )

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
            for endpoint in sensor.endpoints.values():
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
        self._discovery_started.discard(sensor_id)
        task = self._discovery_tasks.pop(sensor_id, None)
        if task is not None and not task.done():
            task.cancel()
        self._sensor_device_ids.pop(sensor_id, None)
        for provider in tuple(self.providers.values()):
            callback_fn = getattr(provider, "sensor_acceptance_changed", None)
            if callback_fn is not None:
                callback_fn(sensor_id, False)
        self._notify_structure()

        affected: list[str] = []
        for entry in tuple(self.profile_entries.values()):
            ids = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
            if any(self.resolve_sensor_id(str(item)) == sensor_id for item in ids):
                affected.append(entry.entry_id)
        return tuple(affected)

    def _schedule_deleted_sensor_cleanup(
        self, sensor_id: str, profile_entry_ids: tuple[str, ...]
    ) -> None:
        """Finish profile/subentry cleanup after the HA delete request returns."""

        async def _cleanup() -> None:
            await asyncio.sleep(0)
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
                # This invokes the normal update listener, which performs exactly
                # one profile reload. Do not schedule an additional reload here.
                self.suppress_entry_reload_once(entry.entry_id)
                self.hass.config_entries.async_update_entry(entry, options=options)

            self.remove_sensors_subentry_if_empty()

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
        """Persist revocation, then defer expensive cleanup off the UI path."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        affected = self._forget_sensor_memory(sensor_id)
        # The reassignment tombstone must be durable before HA completes device
        # deletion; otherwise a racing ANT+/BLE packet could resurrect the device.
        self._save_pending = False
        await self._async_save_adapter_config()
        self._schedule_deleted_sensor_cleanup(sensor_id, affected)

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
        self.ensure_transport_subentry("antplus")
        self.ensure_transport_subentry("bluetooth")
        self._remove_legacy_grouping_devices()
        self._migrate_adapter_devices_to_transport_subentries()
        self._remove_legacy_adapters_subentry_if_empty()
        self.ensure_ant_receiver_topology()
        for sensor_id in tuple(self.sensors):
            if self.sensor_is_accepted(sensor_id):
                self.ensure_sensor_device(sensor_id)
            else:
                self.remove_unaccepted_sensor_device(sensor_id)
        self.remove_sensors_subentry_if_empty()

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

    def remove_sensors_subentry_if_empty(self) -> None:
        """Remove the Sensors subentry when it has no accepted physical sensors."""
        if self.hub_entry is None:
            self.sensors_subentry_id = None
            return
        if any(self.sensor_is_accepted(sensor_id) for sensor_id in self.sensors):
            return
        target = None
        for subentry in self.hub_entry.subentries.values():
            if (
                subentry.subentry_type == SENSORS_SUBENTRY_TYPE
                or subentry.unique_id == SENSORS_SUBENTRY_UNIQUE_ID
            ):
                target = subentry
                break
        if target is None:
            self.sensors_subentry_id = None
            return
        self.hass.config_entries.async_remove_subentry(
            self.hub_entry, target.subentry_id
        )
        self.sensors_subentry_id = None

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
            manufacturer=adapter.manufacturer or "Dynastream / Garmin",
            model=adapter.product or f"ANT USB {adapter.vid}:{adapter.pid}",
            serial_number=adapter.serial,
            **common,
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
        """Coalesce changed physical values to at most 2 Hz.

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

        if elapsed >= 0.5 and self._value_notify_handle is None:
            _flush()
            return
        if self._value_notify_handle is not None:
            return
        delay = max(0.0, 0.5 - elapsed)
        self._value_notify_handle = self.hass.loop.call_later(delay, _flush)

    def _mark_last_seen_change(
        self, sensor_id: str, seen: datetime | None
    ) -> set[tuple[str, str, str | None]]:
        """Return a dirty Last seen key only when its 5-minute bucket changes."""
        if seen is None:
            bucket = None
        else:
            bucket = seen.replace(
                minute=(seen.minute // 5) * 5, second=0, microsecond=0
            )
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
                not current.session_armed and not current.session_active
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
        return self.endpoint_aliases.get(str(sensor_id), str(sensor_id))

    def _select_merge_primary(self, a: LiveSensor, b: LiveSensor) -> tuple[LiveSensor, LiveSensor]:
        if bool(a.metadata.get("accepted")) != bool(b.metadata.get("accepted")):
            return (a, b) if a.metadata.get("accepted") else (b, a)
        if ("antplus" in a.endpoints) != ("antplus" in b.endpoints):
            return (a, b) if "antplus" in a.endpoints else (b, a)
        return a, b

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
        had_accepted_device = (
            self.sensor_is_accepted(a_id) or self.sensor_is_accepted(b_id)
        )

        primary, secondary = self._select_merge_primary(a, b)
        for transport, endpoint in secondary.endpoints.items():
            if transport not in primary.endpoints:
                primary.endpoints[transport] = endpoint
            self.endpoint_aliases[endpoint.endpoint_id] = primary.sensor_id
        self.endpoint_aliases[secondary.sensor_id] = primary.sensor_id
        primary.capabilities.update(secondary.capabilities)
        primary.metadata.update(
            {k: v for k, v in secondary.metadata.items() if v not in (None, "", {}, [])}
        )

        self._requires_reassignment.discard(a_id)
        self._requires_reassignment.discard(b_id)
        if requires_reassignment:
            self._requires_reassignment.add(primary.sensor_id)
            primary.metadata.pop("accepted", None)
        elif secondary.metadata.get("accepted"):
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

        # Discovery state follows the canonical physical ID. Do not let a stale
        # secondary discovery marker suppress a newly merged sensor.
        self._discovery_started.discard(secondary.sensor_id)
        secondary_task = self._discovery_tasks.pop(secondary.sensor_id, None)
        if secondary_task is not None and not secondary_task.done():
            secondary_task.cancel()

        # Unaccepted sensors have no registry objects, so scanning/removing the HA
        # registries and reloading the hub here is pure overhead. For an accepted
        # merge, defer that structural cleanup off the current radio callback.
        if had_accepted_device and not requires_reassignment:
            self._schedule_merged_registry_cleanup(secondary.sensor_id)

        self._schedule_save()
        return primary

    def _schedule_merged_registry_cleanup(self, old_sensor_id: str) -> None:
        """Defer registry cleanup/reload caused by a physical-identity merge."""
        async def _cleanup() -> None:
            await asyncio.sleep(0)
            self._cleanup_merged_registry_sensor(old_sensor_id)
            self._notify_structure()

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

        # Fast path for recurring advertisements from an already-known endpoint.
        # RSSI/last_seen can change several times per second; when the structural
        # identity is unchanged, update only those volatile fields and return
        # without rebuilding/matching the physical sensor or notifying globals.
        known_sensor_id = self.endpoint_aliases.get(endpoint_id)
        known_sensor = self.sensors.get(known_sensor_id) if known_sensor_id else None
        known_endpoint = (
            known_sensor.endpoints.get(transport) if known_sensor is not None else None
        )
        normalized_name = _normalize_name(name)
        name_would_change = bool(
            known_sensor is not None
            and (known_sensor.name == "Fitness sensor" or _family(normalized_name, metadata))
            and known_sensor.name != normalized_name
        )
        if (
            known_sensor is not None
            and known_endpoint is not None
            and not name_would_change
            and known_endpoint.address == address
            and known_endpoint.capabilities == set(capabilities)
            and known_endpoint.source == source
            and known_endpoint.metadata == metadata
        ):
            previous_available = known_sensor.available
            known_endpoint.last_seen = last_seen
            known_endpoint.rssi = rssi
            known_endpoint.available = available
            if self.sensor_is_accepted(known_sensor.sensor_id):
                dirty = self._mark_last_seen_change(
                    known_sensor.sensor_id, known_endpoint.last_seen
                )
                if previous_available != known_sensor.available:
                    dirty.add((known_sensor.sensor_id, "availability", None))
                if dirty:
                    self._notify_values_throttled(dirty)
            return known_sensor

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
        previous_available = sensor.available

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
        if structural_change and accepted:
            self._notify_structure()
        if accepted:
            dirty = self._mark_last_seen_change(sensor.sensor_id, endpoint.last_seen)
            if previous_available != sensor.available:
                dirty.add((sensor.sensor_id, "availability", None))
            if dirty:
                self._notify_values_throttled(dirty)
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

    def _prune_stale_sensor_discovery_flows(self) -> None:
        """Remove discovery cards once the underlying sensor stops transmitting."""
        for flow in tuple(self.hass.config_entries.flow.async_progress()):
            context = flow.get("context") or {}
            if (
                str(flow.get("handler") or "") != DOMAIN
                or str(context.get("source") or "") != "integration_discovery"
            ):
                continue
            unique_id = str(context.get("unique_id") or "")
            if not unique_id.startswith("live_sensor:"):
                continue
            sensor_id = self.resolve_sensor_id(unique_id.split(":", 1)[1])
            if self.sensor_recently_observed(sensor_id):
                continue
            flow_id = str(flow.get("flow_id") or "")
            if flow_id:
                try:
                    self.hass.config_entries.flow.async_abort(flow_id)
                except Exception:
                    pass
            self._discovery_started.discard(sensor_id)

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

    def _schedule_sensor_discovery(self, sensor_id: str) -> None:
        """Start one discovery flow for an observed, unaccepted physical sensor."""
        sensor_id = self.resolve_sensor_id(sensor_id)
        sensor = self.sensors.get(sensor_id)
        if (
            sensor is None
            or self.sensor_is_accepted(sensor_id)
            or not self.sensor_recently_observed(sensor_id)
        ):
            return

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
            active = any(
                str((flow.get("context") or {}).get("unique_id") or "") == unique_id
                for flow in self.hass.config_entries.flow.async_progress()
            )
            if active:
                return
            self._discovery_started.discard(sensor_id)

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
            for provider in tuple(self.providers.values()):
                callback_fn = getattr(provider, "sensor_acceptance_changed", None)
                if callback_fn is not None:
                    callback_fn(sensor_id, True)
            # Keep the config-flow request path lightweight. Persist acceptance and
            # notify topology listeners; device/entity materialization is handled
            # dynamically without reloading the hub or profile config entries.
            self._schedule_save()
            self._notify_structure()

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

        self.hass.async_create_background_task(
            _reload(),
            "fitness reload live sensor hub",
            eager_start=False,
        )

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
            self._set_active_transport(sensor, transport)
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
                    self._set_active_transport(sensor, None)
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

        # Physical HA entities are dirtied only when their value or provenance
        # actually changes. Repeated identical radio packets no longer create HA
        # state writes merely because a packet arrived.
        value_bucket = self.sensor_values.setdefault(sensor_id, {})
        transport_bucket = self.sensor_value_transport.setdefault(sensor_id, {})
        physical_dirty: set[tuple[str, str, str | None]] = set()
        packet_values: dict[str, float] = {}
        for key, raw in values.items():
            if key not in LIVE_METRICS or raw is None:
                continue
            value = float(raw)
            packet_values[key] = value
            if value_bucket.get(key) != value or transport_bucket.get(key) != transport:
                value_bucket[key] = value
                transport_bucket[key] = transport
                physical_dirty.add((sensor_id, "metric", key))

        previous_available = sensor.available
        endpoint = sensor.endpoints.get(transport)
        seen = datetime.now(timezone.utc)
        if endpoint:
            endpoint.last_seen = seen
            endpoint.available = True
        physical_dirty.update(self._mark_last_seen_change(sensor_id, seen))
        if previous_available != sensor.available:
            physical_dirty.add((sensor_id, "availability", None))
        if physical_dirty and self.sensor_is_accepted(sensor_id):
            self._notify_values_throttled(physical_dirty)

        if not packet_values:
            return

        now = seen
        for entry in tuple(self.profile_entries.values()):
            manager = self.hass.data.get(DOMAIN, {}).get(entry.entry_id)
            # Idle profiles do not consume live measurements. Keep physical sensor
            # entities updated, but avoid profile/session work for every radio packet.
            if manager is None or (not manager.session_armed and not manager.session_active):
                continue
            selected = self.selected_sensor_ids(entry)
            if sensor_id not in selected:
                continue
            chosen = self._profile_sensor_transport.get(entry.entry_id, {}).get(sensor_id)
            # Strict transport ownership: when ANT+ wins for this physical device,
            # BLE advertisements/GATT notifications cannot leak into the workout.
            if chosen is not None and transport != chosen:
                continue

            bucket = self.measurements.setdefault(entry.entry_id, {})
            source_bucket = self.measurement_sources.setdefault(entry.entry_id, {})
            # Always refresh the canonical packet values for an active session.
            # Even an unchanged HR/power value is meaningful over time for the 1 Hz
            # workout sample stream, but manager processing is coalesced below.
            for key, value in packet_values.items():
                bucket[key] = value
                source_bucket[key] = sensor_id
            self.measurement_time[entry.entry_id] = now
            self._notify_profile_live_throttled(entry.entry_id, manager)

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
        for handle in self._profile_live_notify_handles.values():
            handle.cancel()
        self._profile_live_notify_handles.clear()
        self._profile_last_live_notify_monotonic.clear()
        if self._value_notify_handle is not None:
            self._value_notify_handle.cancel()
            self._value_notify_handle = None
        self._pending_sensor_value_changes.clear()
        self._setup_discovery_baseline.clear()


def get_live_runtime(hass: HomeAssistant) -> LiveRuntime:
    domain_data = hass.data.setdefault(DOMAIN, {})
    runtime = domain_data.get("_live_runtime")
    if runtime is None:
        runtime = LiveRuntime(hass)
        domain_data["_live_runtime"] = runtime
    return runtime
