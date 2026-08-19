"""HPlus-family direct daily-history adapter registration."""
from __future__ import annotations

from typing import Any, Iterable
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..base import BluetoothArchiveAdapterSpec
from .coordinator import HPlusHistoryCoordinator
from .protocol import HPLUS_SERVICE_UUID, hplus_identity


def _bluetooth_matchers() -> tuple[BluetoothCallbackMatcher, ...]:
    return (
        BluetoothCallbackMatcher(service_uuid=HPLUS_SERVICE_UUID, connectable=False),
    )


def _match_bluetooth(
    name: str | None,
    service_uuids: Iterable[str],
    _manufacturer_data: dict[int, bytes] | None,
) -> dict[str, Any] | None:
    return hplus_identity(name, service_uuids)


ARCHIVE_ADAPTER = BluetoothArchiveAdapterSpec(
    adapter_id="hplus_history",
    coordinator_factory=HPlusHistoryCoordinator,
    bluetooth_matchers=_bluetooth_matchers,
    match_bluetooth=_match_bluetooth,
    advertisement_capabilities=frozenset(),
    sync_capabilities=frozenset({"health_history", "device_state"}),
    generic_identity_probe=False,
)
