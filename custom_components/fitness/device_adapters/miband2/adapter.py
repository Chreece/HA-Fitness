"""Xiaomi Mi Band 2 direct-history adapter registration."""
from __future__ import annotations

from typing import Any, Iterable

from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..base import BluetoothArchiveAdapterSpec
from .coordinator import MiBand2Coordinator
from .protocol import MIBAND2_BASIC_SERVICE_UUID, MIBAND2_SERVICE_UUID, miband2_identity


def _bluetooth_matchers() -> tuple[BluetoothCallbackMatcher, ...]:
    return (
        BluetoothCallbackMatcher(local_name="MI Band 2", connectable=False),
        BluetoothCallbackMatcher(local_name="Mi Band 2", connectable=False),
        BluetoothCallbackMatcher(service_uuid=MIBAND2_SERVICE_UUID, connectable=False),
    )


def _match_bluetooth(
    name: str | None,
    service_uuids: Iterable[str],
    manufacturer_data: dict[int, bytes] | None,
) -> dict[str, Any] | None:
    return miband2_identity(name, service_uuids, manufacturer_data)


ARCHIVE_ADAPTER = BluetoothArchiveAdapterSpec(
    adapter_id="xiaomi_miband2",
    coordinator_factory=MiBand2Coordinator,
    bluetooth_matchers=_bluetooth_matchers,
    match_bluetooth=_match_bluetooth,
    advertisement_capabilities=frozenset(),
    # Raw categories are intentionally retained as context, but we do not claim
    # sleep_history until stage codes are independently stable across firmware.
    sync_capabilities=frozenset({"health_history", "device_state"}),
    generic_identity_probe=False,
)
