"""Xiaomi Mi Band 1 / 1A / 1S direct-history adapter registration."""
from __future__ import annotations

from typing import Any, Iterable

from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..base import BluetoothArchiveAdapterSpec
from .coordinator import MiBand1Coordinator
from .protocol import MIBAND1_SERVICE_UUID, miband1_identity


def _bluetooth_matchers() -> tuple[BluetoothCallbackMatcher, ...]:
    # FEE0 by itself is deliberately not enough for identity; match_bluetooth
    # requires a legacy local name too.  The broad matcher merely lets us see
    # the advertisement before applying that stricter predicate.
    return (
        BluetoothCallbackMatcher(local_name="MI", connectable=False),
        BluetoothCallbackMatcher(local_name="MI1*", connectable=False),
        BluetoothCallbackMatcher(service_uuid=MIBAND1_SERVICE_UUID, connectable=False),
    )


def _match_bluetooth(
    name: str | None,
    service_uuids: Iterable[str],
    manufacturer_data: dict[int, bytes] | None,
) -> dict[str, Any] | None:
    return miband1_identity(name, service_uuids, manufacturer_data)


ARCHIVE_ADAPTER = BluetoothArchiveAdapterSpec(
    adapter_id="xiaomi_miband1",
    coordinator_factory=MiBand1Coordinator,
    bluetooth_matchers=_bluetooth_matchers,
    match_bluetooth=_match_bluetooth,
    advertisement_capabilities=frozenset(),
    sync_capabilities=frozenset({"health_history", "sleep_history", "device_state"}),
    generic_identity_probe=False,
)
