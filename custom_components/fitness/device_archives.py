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
        self._adapters = {adapter.adapter_id: adapter for adapter in ARCHIVE_ADAPTERS}
        self._coordinators = {
            adapter_id: adapter.coordinator_factory(provider)
            for adapter_id, adapter in self._adapters.items()
        }

    async def async_setup(self) -> None:
        for coordinator in self._coordinators.values():
            await coordinator.async_setup()

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

    def advertise(self, sensor_id: str, advertisement: ArchiveAdvertisement) -> None:
        coordinator = self._coordinators.get(advertisement.adapter_id)
        if coordinator is not None:
            coordinator.advertise(sensor_id, advertisement.metadata)

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

    def coordinator(self, adapter_id: str):
        return self._coordinators.get(adapter_id)
