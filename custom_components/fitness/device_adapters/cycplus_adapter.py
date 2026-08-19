"""Self-contained CYCPLUS M1 Bluetooth archive adapter registration."""
from __future__ import annotations

from typing import Any, Iterable

from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..const import CAPABILITY_WORKOUT_HISTORY
from .base import BluetoothArchiveAdapterSpec
from .cycplus_m1 import (
    CYCPLUS_M1_SERVICE_UUID,
    CycplusM1Coordinator,
    cycplus_m1_identity,
    cycplus_m1_serial_identity,
)


def _bluetooth_matchers() -> tuple[BluetoothCallbackMatcher, ...]:
    return (
        BluetoothCallbackMatcher(
            service_uuid=CYCPLUS_M1_SERVICE_UUID, connectable=False
        ),
    )


def _match_bluetooth(
    name: str | None,
    service_uuids: Iterable[str],
    _manufacturer_data: dict[int, bytes] | None,
) -> dict[str, Any] | None:
    return cycplus_m1_identity(name, service_uuids)


def _enrich_connected_metadata(
    metadata: dict[str, Any], service_uuids: Iterable[str]
) -> dict[str, Any]:
    """Interpret M1 Device Information only after vendor-service verification."""
    result = dict(metadata)
    services = {str(value).lower() for value in (service_uuids or ())}
    if CYCPLUS_M1_SERVICE_UUID not in services:
        return result
    serial_identity = cycplus_m1_serial_identity(result.get("serial_number"))
    if serial_identity:
        result.update(serial_identity)
    return result


ARCHIVE_ADAPTER = BluetoothArchiveAdapterSpec(
    adapter_id="cycplus_m1",
    coordinator_factory=CycplusM1Coordinator,
    bluetooth_matchers=_bluetooth_matchers,
    match_bluetooth=_match_bluetooth,
    advertisement_capabilities=frozenset({CAPABILITY_WORKOUT_HISTORY}),
    sync_capabilities=frozenset({"workout_history", "gps_tracks", "device_state"}),
    enrich_connected_metadata=_enrich_connected_metadata,
)
