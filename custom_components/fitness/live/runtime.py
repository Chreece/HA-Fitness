"""Global live-workout transport runtime for Fitness."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import (
    CONF_ANTPLUS_ENABLED,
    CONF_BLUETOOTH_ENABLED,
    CONF_LIVE_SENSOR_IDS,
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


@dataclass(slots=True)
class LiveSensor:
    sensor_id: str
    transport: str
    name: str
    capabilities: set[str] = field(default_factory=set)
    address: str | None = None
    source: str | None = None
    last_seen: datetime | None = None
    rssi: int | None = None
    available: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        metrics = ", ".join(sorted(self.capabilities)) or "fitness sensor"
        return f"{self.name} — {self.transport.upper()} · {metrics}"


class LiveRuntime:
    """One global transport runtime shared by every Fitness profile."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.sensors: dict[str, LiveSensor] = {}
        self.providers: dict[str, Any] = {}
        self.profile_entries: dict[str, Any] = {}
        self.measurements: dict[str, dict[str, float]] = {}
        self.measurement_sources: dict[str, dict[str, str]] = {}
        self.measurement_time: dict[str, datetime] = {}
        self._transport_claims: dict[str, set[str]] = {}
        self._transport_baseline: dict[str, bool] = {}
        self._profile_claims: dict[str, set[str]] = {}
        self._store = Store[dict[str, Any]](
            hass, LIVE_ADAPTER_STORE_VERSION, LIVE_ADAPTER_STORE_KEY, private=True
        )
        self._configured = {name: False for name in TRANSPORTS}
        self._enabled = {name: False for name in TRANSPORTS}
        self._initialized = False
        self._discovery_started: set[str] = set()
        self._setup_discovery_baseline: dict[str, bool] = {}

    async def async_initialize(self) -> None:
        if self._initialized:
            return
        stored = await self._store.async_load() or {}
        configured = stored.get("configured") or {}
        enabled = stored.get("enabled") or {}
        for name in TRANSPORTS:
            self._configured[name] = bool(configured.get(name, False))
            self._enabled[name] = bool(enabled.get(name, False))
        self._initialized = True
        await self.async_refresh_modules()

    async def _async_save_adapter_config(self) -> None:
        await self._store.async_save(
            {
                "configured": dict(self._configured),
                "enabled": dict(self._enabled),
            }
        )

    def adapter_configured(self, transport: str) -> bool:
        return bool(self._configured.get(transport, False))

    def adapter_enabled(self, transport: str) -> bool:
        return bool(self._enabled.get(transport, False))

    @property
    def configured_transports(self) -> set[str]:
        return {name for name in TRANSPORTS if self.adapter_configured(name)}

    async def async_configure_transport(
        self, transport: str, *, enabled: bool = True
    ) -> None:
        if transport not in TRANSPORTS:
            raise ValueError(f"Unsupported Fitness live transport: {transport}")
        await self.async_initialize()
        self._configured[transport] = True
        self._enabled[transport] = bool(enabled)
        await self._async_save_adapter_config()
        await self.async_refresh_modules()

    async def async_set_transport_enabled(
        self, transport: str, enabled: bool
    ) -> None:
        if not self.adapter_configured(transport):
            if not enabled:
                return
            self._configured[transport] = True
        self._enabled[transport] = bool(enabled)
        await self._async_save_adapter_config()
        await self.async_refresh_modules()

    async def async_register_profile(self, entry) -> None:
        await self.async_initialize()
        self.profile_entries[entry.entry_id] = entry

        # One-time migration from the prototype/profile flags into the global
        # adapter store. New entries never need these values again.
        merged = {**entry.data, **entry.options}
        migrated = False
        for transport, key in (
            ("bluetooth", CONF_BLUETOOTH_ENABLED),
            ("antplus", CONF_ANTPLUS_ENABLED),
        ):
            if merged.get(key) and not self.adapter_configured(transport):
                self._configured[transport] = True
                self._enabled[transport] = True
                migrated = True
        if migrated:
            await self._async_save_adapter_config()

        await self.async_refresh_modules()
        ant_provider = self.providers.get("antplus")
        if ant_provider is not None:
            await ant_provider.async_bind_profile(entry)
        for sensor_id in self.selected_sensor_ids(entry):
            self.ensure_sensor_device(entry.entry_id, sensor_id)

    async def async_unregister_profile(self, entry_id: str) -> None:
        entry = self.profile_entries.get(entry_id)
        if entry is not None:
            await self.async_finish_session(entry, keep_heart_rate=False)
        self.profile_entries.pop(entry_id, None)
        self.measurements.pop(entry_id, None)
        self.measurement_sources.pop(entry_id, None)
        self.measurement_time.pop(entry_id, None)
        # Global adapters deliberately survive profile removal.

    async def async_refresh_modules(self) -> None:
        if not self._initialized:
            return
        wanted = {name: self.adapter_enabled(name) for name in TRANSPORTS}

        if wanted["bluetooth"]:
            provider = self.providers.get("bluetooth")
            if provider is None:
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
            elif provider.adapter_manager is None and self.profile_entries:
                # ANT+ can be selected before the first profile ConfigEntry
                # exists. Retry setup as soon as that host entry is available.
                await provider.async_setup()

        for name in tuple(self.providers):
            if not wanted.get(name, False):
                await self.providers.pop(name).async_shutdown()
                self._transport_claims.pop(name, None)
                self._transport_baseline.pop(name, None)
        
    async def async_begin_setup_discovery(self) -> None:
        """Temporarily capture while a config flow populates sensor choices."""
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
        """Restore adapter capture state after config-flow discovery."""
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

    def transport_in_use(self, transport: str) -> bool:
        return bool(self._transport_claims.get(transport))

    def register_sensor(self, sensor: LiveSensor) -> None:
        is_new = sensor.sensor_id not in self.sensors
        existing = self.sensors.get(sensor.sensor_id)
        if existing is not None:
            existing.name = sensor.name or existing.name
            existing.capabilities.update(sensor.capabilities)
            existing.address = sensor.address or existing.address
            existing.source = sensor.source or existing.source
            existing.last_seen = sensor.last_seen or existing.last_seen
            existing.rssi = (
                sensor.rssi if sensor.rssi is not None else existing.rssi
            )
            existing.available = sensor.available
            existing.metadata.update(sensor.metadata)
        else:
            self.sensors[sensor.sensor_id] = sensor

        if is_new and self.profile_entries:
            self._schedule_sensor_discovery(sensor.sensor_id)

    def _schedule_sensor_discovery(self, sensor_id: str) -> None:
        if sensor_id in self._discovery_started:
            return
        # A sensor already assigned to any user is configured, not new.
        if any(
            sensor_id in set(self.selected_sensor_ids(entry))
            for entry in self.profile_entries.values()
        ):
            return
        # An accepted physical sensor has a persistent Fitness device-registry
        # identity, so do not rediscover it on every HA restart.
        from homeassistant.helpers import device_registry as dr
        registry = dr.async_get(self.hass)
        if registry.async_get_device(identifiers={("fitness", f"live_sensor:{sensor_id}")}) is not None:
            return
        self._discovery_started.add(sensor_id)
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_init(
                "fitness",
                context={"source": "integration_discovery"},
                data={"sensor_id": sensor_id},
            )
        )

    def ensure_sensor_device(self, entry_id: str, sensor_id: str) -> None:
        sensor = self.sensors.get(sensor_id)
        if sensor is None:
            return
        from homeassistant.helpers import device_registry as dr
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=entry_id,
            identifiers={("fitness", f"live_sensor:{sensor_id}")},
            name=sensor.name,
            manufacturer=(
                str(sensor.metadata.get("manufacturer"))
                if sensor.metadata.get("manufacturer")
                else ("Bluetooth SIG" if sensor.transport == "bluetooth" else "ANT+")
            ),
            model=(
                str(sensor.metadata.get("model"))
                if sensor.metadata.get("model")
                else f"{sensor.transport.upper()} fitness sensor"
            ),
        )

    @staticmethod
    def _transport_from_sensor_id(sensor_id: str) -> str | None:
        prefix = str(sensor_id).split(":", 1)[0].lower()
        return prefix if prefix in TRANSPORTS else None

    def selected_sensor_ids(self, entry) -> list[str]:
        return list(
            ({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or [])
        )

    def sensors_for_profile(self, entry) -> list[LiveSensor]:
        result: list[LiveSensor] = []
        for sensor_id in self.selected_sensor_ids(entry):
            sensor = self.sensors.get(sensor_id)
            if sensor is not None:
                result.append(sensor)
                continue
            transport = self._transport_from_sensor_id(sensor_id)
            if transport == "bluetooth":
                address = sensor_id.split(":", 1)[1]
                result.append(
                    LiveSensor(
                        sensor_id=sensor_id,
                        transport=transport,
                        name=address,
                        address=address,
                    )
                )
            elif transport == "antplus":
                device_id = sensor_id.split(":", 1)[1]
                result.append(
                    LiveSensor(
                        sensor_id=sensor_id,
                        transport=transport,
                        name=f"ANT+ {device_id}",
                        address=device_id,
                    )
                )
        return result

    def _required_transports(self, entry) -> set[str]:
        result: set[str] = set()
        for sensor_id in self.selected_sensor_ids(entry):
            transport = self._transport_from_sensor_id(sensor_id)
            if transport and transport in self.providers:
                result.add(transport)
        return result

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
        """Claim and connect only transports assigned to this Fitness profile."""
        self.measurements.pop(entry.entry_id, None)
        self.measurement_sources.pop(entry.entry_id, None)
        self.measurement_time.pop(entry.entry_id, None)

        sensors = self.sensors_for_profile(entry)
        required = self._required_transports(entry)
        states: list[str] = []
        for transport in required:
            provider = self.providers.get(transport)
            if provider is None:
                continue
            await self._claim_transport(entry.entry_id, transport)
            await provider.async_connect_profile(entry.entry_id, sensors)
            states.append(
                f"{transport}:{'active' if provider.capture_active else 'waiting'}"
            )
        return ",".join(states) if states else "no_live_transport"

    def _heart_rate_transports(self, entry_id: str) -> set[str]:
        source = self.measurement_sources.get(entry_id, {}).get(METRIC_HEART_RATE)
        if source:
            transport = self._transport_from_sensor_id(source)
            if transport:
                return {transport}
        return set()

    async def async_finish_session(
        self, entry, *, keep_heart_rate: bool = False
    ) -> str:
        claimed = set(self._profile_claims.get(entry.entry_id, set()))
        keep = (
            self._heart_rate_transports(entry.entry_id)
            if keep_heart_rate
            else set()
        )
        states: list[str] = []
        for transport in claimed:
            provider = self.providers.get(transport)
            if provider is None:
                continue
            keep_this = transport in keep
            await provider.async_disconnect_profile(
                entry.entry_id, keep_heart_rate=keep_this
            )
            if keep_this:
                states.append(f"{transport}:recovery")
                continue
            await self._release_transport(entry.entry_id, transport)
            states.append(
                f"{transport}:{'active' if provider.capture_active else 'idle'}"
            )
        if not keep_heart_rate:
            self._profile_claims.pop(entry.entry_id, None)
        return ",".join(states) if states else "no_live_transport"

    async def async_finish_recovery(self, entry) -> str:
        return await self.async_finish_session(entry, keep_heart_rate=False)

    def publish(self, sensor_id: str, values: dict[str, float]) -> None:
        now = datetime.now(timezone.utc)
        for entry in self.profile_entries.values():
            if sensor_id not in set(self.selected_sensor_ids(entry)):
                continue
            bucket = self.measurements.setdefault(entry.entry_id, {})
            source_bucket = self.measurement_sources.setdefault(
                entry.entry_id, {}
            )
            changed = False
            for key in LIVE_METRICS:
                if values.get(key) is not None:
                    bucket[key] = float(values[key])
                    source_bucket[key] = sensor_id
                    changed = True
            if not changed:
                continue
            self.measurement_time[entry.entry_id] = now
            manager = self.hass.data.get("fitness", {}).get(entry.entry_id)
            if manager is not None:
                manager._async_live_source_change(None)

    def live_values(self, entry_id: str) -> dict[str, float | None]:
        values = self.measurements.get(entry_id, {})
        return {key: values.get(key) for key in LIVE_METRICS}

    async def async_shutdown(self) -> None:
        for provider in list(self.providers.values()):
            await provider.async_shutdown()
        self.providers.clear()
        self._transport_claims.clear()
        self._transport_baseline.clear()
        self._profile_claims.clear()
        self._setup_discovery_baseline.clear()


def get_live_runtime(hass: HomeAssistant) -> LiveRuntime:
    domain_data = hass.data.setdefault("fitness", {})
    runtime = domain_data.get("_live_runtime")
    if runtime is None:
        runtime = LiveRuntime(hass)
        domain_data["_live_runtime"] = runtime
    return runtime
