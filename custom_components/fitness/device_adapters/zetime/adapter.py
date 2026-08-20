"""MyKronoz ZeTime direct-history adapter registration."""
from __future__ import annotations

from typing import Any, Iterable
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..base import BluetoothArchiveAdapterSpec
from .coordinator import ZeTimeCoordinator
from .protocol import ZETIME_SERVICE_UUID, zetime_identity


def _bluetooth_matchers() -> tuple[BluetoothCallbackMatcher, ...]:
    return (
        BluetoothCallbackMatcher(local_name="ZeTime*", connectable=False),
        BluetoothCallbackMatcher(service_uuid=ZETIME_SERVICE_UUID, connectable=False),
    )


def _match_bluetooth(
    name: str | None,
    service_uuids: Iterable[str],
    _manufacturer_data: dict[int, bytes] | None,
) -> dict[str, Any] | None:
    return zetime_identity(name, service_uuids)


ARCHIVE_ADAPTER = BluetoothArchiveAdapterSpec(
    adapter_id="mykronoz_zetime",
    coordinator_factory=ZeTimeCoordinator,
    bluetooth_matchers=_bluetooth_matchers,
    match_bluetooth=_match_bluetooth,
    advertisement_capabilities=frozenset(),
    sync_capabilities=frozenset({"health_history", "sleep_history", "device_state"}),
    remote_gatt_services=frozenset({ZETIME_SERVICE_UUID}),
    generic_identity_probe=False,
)
