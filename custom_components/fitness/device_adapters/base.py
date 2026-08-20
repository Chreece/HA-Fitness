"""Generic contracts for direct physical-device workout archive adapters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(slots=True, frozen=True)
class BluetoothArchiveAdapterSpec:
    """Self-contained Bluetooth archive adapter registration."""

    adapter_id: str
    coordinator_factory: Callable[[Any], Any]
    bluetooth_matchers: Callable[[], tuple[Any, ...]]
    match_bluetooth: Callable[
        [str | None, Iterable[str], dict[int, bytes] | None],
        dict[str, Any] | None,
    ]
    advertisement_capabilities: frozenset[str]
    # Canonical archive domains the adapter can retrieve during a full manual sync.
    sync_capabilities: frozenset[str] = frozenset()
    # GATT services a previously-authorized remote browser may expose to the
    # generic Fitness GATT proxy. An empty set keeps that archive adapter local
    # only. Adapter opt-in is deliberate because Web Bluetooth requires service
    # UUIDs up front and some secure protocols are bound to one local central.
    remote_gatt_services: frozenset[str] = frozenset()
    # Some devices use a secure/pairing-sensitive GATT session that must be
    # owned entirely by the adapter.  For those devices the generic Bluetooth
    # DIS probe would create a second short-lived connection before the adapter
    # can establish its stable central/bond.
    generic_identity_probe: bool = True
    # Adapter-specific return-to-range policy.  The shared archive registry
    # detects unavailable -> available transitions, while an adapter may ask to
    # seize a short connection window immediately after a meaningful absence.
    # The default keeps the existing relaxed behavior for ordinary devices.
    availability_return_sync_delay: float = 3.0
    availability_return_min_gap: float = 0.0
    enrich_connected_metadata: Callable[
        [dict[str, Any], Iterable[str]], dict[str, Any]
    ] | None = None
