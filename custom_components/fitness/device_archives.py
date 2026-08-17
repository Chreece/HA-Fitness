"""Registry for direct physical-device workout archives.

Live radio transports call this registry through a vendor-neutral contract. This
keeps Bluetooth/ANT hot paths product-agnostic while direct archive backends own
their verified device protocol and lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from .const import CAPABILITY_WORKOUT_HISTORY
from .device_adapters.garmin import (
    GARMIN_ADVERTISEMENT_SERVICE_UUID,
    GARMIN_COMPANY_ID,
    GARMIN_GFDI_V0_SERVICE_UUID,
    GARMIN_GFDI_V1_SERVICE_UUID,
    GARMIN_GFDI_V2_SERVICE_UUID,
    GarminLocalCoordinator,
    garmin_advertisement_identity,
)


@dataclass(slots=True, frozen=True)
class ArchiveAdvertisement:
    """One recognized archive device advertisement."""

    adapter_id: str
    metadata: dict[str, Any]
    capabilities: frozenset[str]


class DeviceArchiveRegistry:
    """Own direct-device archive adapters behind a generic live-transport API."""

    def __init__(self, provider) -> None:
        self.provider = provider
        self._coordinators = {
            "garmin_local": GarminLocalCoordinator(provider),
        }

    async def async_setup(self) -> None:
        for coordinator in self._coordinators.values():
            await coordinator.async_setup()

    async def async_shutdown(self) -> None:
        for coordinator in self._coordinators.values():
            await coordinator.async_shutdown()

    def bluetooth_matchers(self) -> tuple[BluetoothCallbackMatcher, ...]:
        """Return low-cost HA Bluetooth matchers for direct archive protocols."""
        service_uuids = (
            GARMIN_ADVERTISEMENT_SERVICE_UUID,
            GARMIN_GFDI_V2_SERVICE_UUID,
            GARMIN_GFDI_V1_SERVICE_UUID,
            GARMIN_GFDI_V0_SERVICE_UUID,
        )
        return (
            BluetoothCallbackMatcher(manufacturer_id=GARMIN_COMPANY_ID, connectable=False),
            *(
                BluetoothCallbackMatcher(service_uuid=service_uuid, connectable=False)
                for service_uuid in service_uuids
            ),
        )

    def match_bluetooth(
        self,
        name: str | None,
        service_uuids,
        manufacturer_data: dict[int, bytes] | None,
    ) -> ArchiveAdvertisement | None:
        metadata = garmin_advertisement_identity(name, service_uuids, manufacturer_data)
        if metadata is None:
            return None
        return ArchiveAdvertisement(
            adapter_id="garmin_local",
            metadata=metadata,
            capabilities=frozenset({CAPABILITY_WORKOUT_HISTORY}),
        )

    def advertise(self, sensor_id: str, advertisement: ArchiveAdvertisement) -> None:
        coordinator = self._coordinators.get(advertisement.adapter_id)
        if coordinator is not None:
            coordinator.advertise(sensor_id, advertisement.metadata)

    def coordinator_for_metadata(self, metadata: dict[str, Any] | None):
        adapter_id = str((metadata or {}).get("archive_adapter") or "")
        return self._coordinators.get(adapter_id)

    def acceptance_changed(self, sensor_id: str, accepted: bool, metadata: dict[str, Any] | None) -> bool:
        coordinator = self.coordinator_for_metadata(metadata)
        if coordinator is None:
            return False
        coordinator.acceptance_changed(sensor_id, accepted)
        return True

    def assignment_changed(self, sensor_id: str, metadata: dict[str, Any] | None) -> bool:
        coordinator = self.coordinator_for_metadata(metadata)
        if coordinator is None:
            return False
        coordinator.assignment_changed(sensor_id)
        return True

    def forget_sensor(self, sensor_id: str) -> None:
        for coordinator in self._coordinators.values():
            coordinator.forget_sensor(sensor_id)

    def coordinator(self, adapter_id: str):
        return self._coordinators.get(adapter_id)
