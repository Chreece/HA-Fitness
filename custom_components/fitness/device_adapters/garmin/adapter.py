"""Self-contained Garmin Bluetooth archive adapter registration."""
from __future__ import annotations

from typing import Any, Iterable

from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..base import BluetoothArchiveAdapterSpec
from .coordinator import GarminLocalCoordinator
from .protocol import (
    GARMIN_ADVERTISEMENT_SERVICE_UUID,
    GARMIN_COMPANY_ID,
    GARMIN_GFDI_V0_SERVICE_UUID,
    GARMIN_GFDI_V1_SERVICE_UUID,
    GARMIN_GFDI_V2_SERVICE_UUID,
    garmin_advertisement_identity,
)


def _bluetooth_matchers() -> tuple[BluetoothCallbackMatcher, ...]:
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


def _match_bluetooth(
    name: str | None,
    service_uuids: Iterable[str],
    manufacturer_data: dict[int, bytes] | None,
) -> dict[str, Any] | None:
    return garmin_advertisement_identity(name, service_uuids, manufacturer_data)


ARCHIVE_ADAPTER = BluetoothArchiveAdapterSpec(
    adapter_id="garmin_local",
    coordinator_factory=GarminLocalCoordinator,
    bluetooth_matchers=_bluetooth_matchers,
    match_bluetooth=_match_bluetooth,
    # Vendor advertisement evidence is only a candidate. The connected GFDI
    # handshake grants workout_history after V2/V1/V0 capability verification.
    advertisement_capabilities=frozenset(),
    sync_capabilities=frozenset({"workout_history", "gps_tracks", "health_history", "sleep_history", "device_state"}),
    # Garmin pairing/bond state belongs to one Bluetooth central.  Let the
    # adapter own the first connected session instead of running the generic
    # short-lived DIS identity probe before pairing.
    generic_identity_probe=False,
    # Garmin watches can hand their single useful Bluetooth connection back to
    # Garmin Connect within seconds of waking/returning to range.  After a real
    # absence, let Fitness start the archive handshake immediately so HA gets a
    # fair chance to sync before the phone reacquires the watch.
    availability_return_sync_delay=0.0,
    availability_return_min_gap=60.0,
)
