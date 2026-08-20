"""Ultrahuman Ring AIR direct-history adapter registration."""
from __future__ import annotations

from typing import Any, Iterable
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..base import BluetoothArchiveAdapterSpec
from .coordinator import UltrahumanAirCoordinator
from .protocol import ULTRAHUMAN_COMMAND_SERVICE_UUID, ULTRAHUMAN_STATE_SERVICE_UUID, ultrahuman_identity


def _bluetooth_matchers() -> tuple[BluetoothCallbackMatcher, ...]:
    return (
        BluetoothCallbackMatcher(local_name="UH_*", connectable=False),
        BluetoothCallbackMatcher(service_uuid=ULTRAHUMAN_COMMAND_SERVICE_UUID, connectable=False),
    )


def _match_bluetooth(
    name: str | None,
    service_uuids: Iterable[str],
    _manufacturer_data: dict[int, bytes] | None,
) -> dict[str, Any] | None:
    return ultrahuman_identity(name, service_uuids)


ARCHIVE_ADAPTER = BluetoothArchiveAdapterSpec(
    adapter_id="ultrahuman_air",
    coordinator_factory=UltrahumanAirCoordinator,
    bluetooth_matchers=_bluetooth_matchers,
    match_bluetooth=_match_bluetooth,
    advertisement_capabilities=frozenset(),
    sync_capabilities=frozenset({"health_history", "device_state"}),
    remote_gatt_services=frozenset({ULTRAHUMAN_COMMAND_SERVICE_UUID, ULTRAHUMAN_STATE_SERVICE_UUID}),
    generic_identity_probe=False,
)
