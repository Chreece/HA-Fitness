"""Registry for direct physical-device workout archives.

Live radio transports call this registry through a vendor-neutral contract. The
registry only orchestrates self-contained adapters; physical protocol matching,
identity enrichment and lifecycle details live under ``device_adapters``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from .device_adapters.registry import ARCHIVE_ADAPTERS


@dataclass(slots=True, frozen=True)
class ArchiveAdvertisement:
    """One recognized archive device advertisement."""

    adapter_id: str
    metadata: dict[str, Any]
    capabilities: frozenset[str]


@dataclass(slots=True, frozen=True)
class ArchiveSyncAction:
    """Adapter-owned metadata for one generic manual archive retry action."""

    adapter_id: str
    unique_suffix: str
    translation_key: str
    icon: str
    capabilities: frozenset[str] = frozenset()


class DeviceArchiveRegistry:
    """Own direct-device archive adapters behind a generic live-transport API."""

    def __init__(self, provider) -> None:
        self.provider = provider
        self._last_archive_advertisement: dict[str, float] = {}
        self._last_availability_retry: dict[str, float] = {}
        self._availability_retry_after = 0.0
        self._adapters = {adapter.adapter_id: adapter for adapter in ARCHIVE_ADAPTERS}
        self._coordinators = {
            adapter_id: adapter.coordinator_factory(provider)
            for adapter_id, adapter in self._adapters.items()
        }

    async def async_setup(self) -> None:
        for coordinator in self._coordinators.values():
            await coordinator.async_setup()
        # Cached Bluetooth replay marks restored endpoints available immediately.
        # Do not let that first replay bypass the intentional HA/Bluetooth startup
        # cooldown. A dedicated background sync below owns the first retry.
        self._availability_retry_after = self.provider.hass.loop.time() + 45.0
        # Do not make Home Assistant startup wait for archive radios. Once HA and
        # Bluetooth have had time to settle, every accepted/assigned direct
        # archive device gets one coalesced forced sync attempt.
        self.schedule_archive_sync(delay=45.0, force=True, reason="home_assistant_startup")

    async def async_shutdown(self) -> None:
        for coordinator in self._coordinators.values():
            await coordinator.async_shutdown()

    def bluetooth_matchers(self) -> tuple[BluetoothCallbackMatcher, ...]:
        """Return the union of low-cost matchers declared by all adapters."""
        return tuple(
            matcher
            for adapter in self._adapters.values()
            for matcher in adapter.bluetooth_matchers()
        )

    def match_bluetooth(
        self,
        name: str | None,
        service_uuids,
        manufacturer_data: dict[int, bytes] | None,
    ) -> ArchiveAdvertisement | None:
        for adapter in self._adapters.values():
            metadata = adapter.match_bluetooth(
                name, service_uuids, manufacturer_data
            )
            if metadata is None:
                continue
            return ArchiveAdvertisement(
                adapter_id=adapter.adapter_id,
                metadata=metadata,
                capabilities=adapter.advertisement_capabilities,
            )
        return None

    def advertise(
        self,
        sensor_id: str,
        advertisement: ArchiveAdvertisement,
        *,
        became_available: bool = False,
    ) -> None:
        coordinator = self._coordinators.get(advertisement.adapter_id)
        if coordinator is None:
            return
        canonical = self.provider.runtime.resolve_sensor_id(sensor_id)
        now = self.provider.hass.loop.time()
        previous = self._last_archive_advertisement.get(canonical)
        self._last_archive_advertisement[canonical] = now
        coordinator.advertise(canonical, advertisement.metadata)

        # Availability is already tracked by the shared physical-device runtime.
        # Use its real unavailable -> available transition rather than guessing
        # from a five-minute advertisement gap. This is important for watches
        # that stop advertising while a phone owns the usable GATT connection:
        # once the phone releases them, Fitness gets one immediate opportunity to
        # retry instead of remaining trapped behind an old connection backoff.
        returned = bool(became_available)
        # Keep the old long-gap check only as a fallback for platforms where an
        # endpoint-expiry tick did not run while HA was busy/asleep.
        if previous is not None and now - previous >= 300.0:
            returned = True
        if not returned or now < self._availability_retry_after:
            return
        last_retry = self._last_availability_retry.get(canonical, -120.0)
        if now - last_retry < 60.0:
            return
        self._last_availability_retry[canonical] = now
        self.schedule_archive_sync(
            sensor_id=canonical,
            delay=3.0,
            force=True,
            reason="device_available_again",
        )

    def schedule_archive_sync(
        self,
        *,
        profile_id: str | None = None,
        sensor_id: str | None = None,
        delay: float = 0.0,
        force: bool = True,
        reason: str = "automatic",
    ) -> int:
        """Non-blockingly schedule eligible direct-device archive synchronization."""
        runtime = self.provider.runtime
        scheduled = 0
        for candidate_id, sensor in tuple(runtime.sensors.items()):
            canonical = runtime.resolve_sensor_id(candidate_id)
            if sensor_id is not None and canonical != runtime.resolve_sensor_id(sensor_id):
                continue
            sensor = runtime.sensors.get(canonical)
            if sensor is None or not runtime.sensor_is_accepted(canonical):
                continue
            owners = runtime.sensor_archive_profile_ids(canonical)
            if not owners or (profile_id is not None and profile_id not in owners):
                continue
            endpoint = sensor.endpoints.get("bluetooth")
            metadata = dict(endpoint.metadata) if endpoint is not None else dict(getattr(sensor, "metadata", {}) or {})
            coordinator = self.coordinator_for_metadata(metadata)
            schedule = getattr(coordinator, "schedule", None) if coordinator is not None else None
            if not callable(schedule):
                continue
            schedule(canonical, delay=max(0.0, float(delay)), force=force)
            scheduled += 1
        if scheduled:
            import logging
            logging.getLogger(__name__).debug(
                "Scheduled %s Fitness archive sync(s): %s", scheduled, reason
            )
        return scheduled

    def enrich_connected_metadata(
        self, metadata: dict[str, Any], service_uuids
    ) -> dict[str, Any]:
        """Delegate connected-GATT identity interpretation to its adapter."""
        result = dict(metadata)
        adapter_id = str(result.get("archive_adapter") or "")
        adapter = self._adapters.get(adapter_id)
        if adapter is None or adapter.enrich_connected_metadata is None:
            return result
        return adapter.enrich_connected_metadata(result, service_uuids)

    def coordinator_for_metadata(self, metadata: dict[str, Any] | None):
        adapter_id = str((metadata or {}).get("archive_adapter") or "")
        return self._coordinators.get(adapter_id)

    def generic_identity_probe_allowed(
        self, metadata: dict[str, Any] | None
    ) -> bool:
        """Return whether the transport may run its generic connected identity probe."""
        adapter_id = str((metadata or {}).get("archive_adapter") or "")
        adapter = self._adapters.get(adapter_id)
        return adapter is None or adapter.generic_identity_probe

    def sync_action_for_metadata(
        self, metadata: dict[str, Any] | None
    ) -> ArchiveSyncAction | None:
        """Return adapter-owned UI metadata without leaking products into platforms."""
        coordinator = self.coordinator_for_metadata(metadata)
        if coordinator is None:
            return None
        values = (
            getattr(coordinator, "adapter_id", None),
            getattr(coordinator, "sync_unique_suffix", None),
            getattr(coordinator, "sync_translation_key", None),
            getattr(coordinator, "sync_icon", None),
        )
        if not all(isinstance(value, str) and value for value in values):
            return None
        adapter_id = str(values[0])
        adapter = self._adapters.get(adapter_id)
        capabilities = adapter.sync_capabilities if adapter is not None else frozenset()
        return ArchiveSyncAction(*values, capabilities)

    def acceptance_changed(
        self, sensor_id: str, accepted: bool, metadata: dict[str, Any] | None
    ) -> bool:
        coordinator = self.coordinator_for_metadata(metadata)
        if coordinator is None:
            return False
        coordinator.acceptance_changed(sensor_id, accepted)
        return True

    def assignment_changed(
        self, sensor_id: str, metadata: dict[str, Any] | None
    ) -> bool:
        coordinator = self.coordinator_for_metadata(metadata)
        if coordinator is None:
            return False
        coordinator.assignment_changed(sensor_id)
        return True

    def forget_sensor(self, sensor_id: str) -> None:
        for coordinator in self._coordinators.values():
            coordinator.forget_sensor(sensor_id)

    def identity_conflict_repaired(self, sensor_id: str) -> None:
        """Clear all adapter state, then let adapters remove owned diagnostics."""
        self.forget_sensor(sensor_id)
        for coordinator in self._coordinators.values():
            repair = getattr(coordinator, "identity_conflict_repaired", None)
            if callable(repair):
                repair(sensor_id)

    async def async_clear_fit_cache(self, retain_count: int = 30, *, profile_id: str | None = None, ownership: str = "profile") -> int:
        """Prune Fitness-owned FIT checkpoint metadata across archive adapters."""
        total = 0
        seen: set[int] = set()
        for coordinator in self._coordinators.values():
            if id(coordinator) in seen:
                continue
            seen.add(id(coordinator))
            clear = getattr(coordinator, "async_clear_fit_cache", None)
            if callable(clear):
                total += int(await clear(retain_count, profile_id=profile_id, ownership=ownership))
        return total


    def workout_export_targets(self, profile_id: str) -> list[dict[str, Any]]:
        """Return accepted profile-owned devices with a real workout writer."""
        runtime = self.provider.runtime
        targets: list[dict[str, Any]] = []
        for sensor_id, sensor in runtime.sensors.items():
            if not runtime.sensor_is_accepted(sensor_id):
                continue
            if profile_id not in runtime.sensor_archive_profile_ids(sensor_id):
                continue
            metadata = dict(getattr(sensor, "metadata", {}) or {})
            coordinator = self.coordinator_for_metadata(metadata)
            writer = getattr(coordinator, "async_write_workout", None) if coordinator is not None else None
            if not callable(writer):
                continue
            targets.append({
                "sensor_id": sensor_id,
                "name": sensor.label(),
                "adapter_id": str(metadata.get("archive_adapter") or ""),
            })
        return targets[:64]

    async def async_export_workout(self, profile_id: str, sensor_id: str, prescription: dict[str, Any]) -> Any:
        """Send a canonical prescription only through an adapter that implements writing."""
        runtime = self.provider.runtime
        sensor_id = runtime.resolve_sensor_id(sensor_id)
        sensor = runtime.sensors.get(sensor_id)
        if sensor is None or not runtime.sensor_is_accepted(sensor_id):
            raise ValueError("Fitness device is unavailable")
        if profile_id not in runtime.sensor_archive_profile_ids(sensor_id):
            raise ValueError("Fitness device is not assigned to this profile")
        coordinator = self.coordinator_for_metadata(dict(getattr(sensor, "metadata", {}) or {}))
        writer = getattr(coordinator, "async_write_workout", None) if coordinator is not None else None
        if not callable(writer):
            raise ValueError("This device adapter does not support workout writing")
        return await writer(sensor_id, prescription)

    def coordinator(self, adapter_id: str):
        return self._coordinators.get(adapter_id)
