"""Bangle.js direct archive adapter registration."""
from __future__ import annotations

from typing import Any, Iterable
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..base import BluetoothArchiveAdapterSpec
from .coordinator import BangleJsCoordinator
from .protocol import NUS_SERVICE_UUID, bangle_identity


def _bluetooth_matchers() -> tuple[BluetoothCallbackMatcher, ...]:
    return (BluetoothCallbackMatcher(local_name="Bangle.js*", service_uuid=NUS_SERVICE_UUID, connectable=False),)


def _match_bluetooth(name: str | None, service_uuids: Iterable[str], _manufacturer_data: dict[int, bytes] | None) -> dict[str, Any] | None:
    return bangle_identity(name, service_uuids)


ARCHIVE_ADAPTER = BluetoothArchiveAdapterSpec(
    adapter_id="bangle_js",
    coordinator_factory=BangleJsCoordinator,
    bluetooth_matchers=_bluetooth_matchers,
    match_bluetooth=_match_bluetooth,
    advertisement_capabilities=frozenset({"workout_history", "health_history"}),
    sync_capabilities=frozenset({"health_history", "sleep_history", "workout_history", "gps_tracks", "device_state"}),
    generic_identity_probe=False,
)
