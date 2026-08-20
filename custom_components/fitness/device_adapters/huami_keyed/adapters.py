"""Registrations for read-only keyed Xiaomi Mi Band 3-7 adapters."""
from __future__ import annotations

from typing import Any, Iterable

from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..base import BluetoothArchiveAdapterSpec
from .coordinator import HuamiKeyedCoordinator
from .protocol import MODEL_BY_ADAPTER, SERVICE_UUID, keyed_band_identity

class MiBand3Coordinator(HuamiKeyedCoordinator):
    adapter_id = "xiaomi_miband3"
    model_name = "Xiaomi Mi Band 3"
    sync_unique_suffix = "sync_xiaomi_miband3_full"

class MiBand4Coordinator(HuamiKeyedCoordinator):
    adapter_id = "xiaomi_miband4"
    model_name = "Xiaomi Mi Smart Band 4"
    sync_unique_suffix = "sync_xiaomi_miband4_full"

class MiBand5Coordinator(HuamiKeyedCoordinator):
    adapter_id = "xiaomi_miband5"
    model_name = "Xiaomi Mi Smart Band 5"
    sync_unique_suffix = "sync_xiaomi_miband5_full"

class MiBand6Coordinator(HuamiKeyedCoordinator):
    adapter_id = "xiaomi_miband6"
    model_name = "Xiaomi Mi Smart Band 6"
    sync_unique_suffix = "sync_xiaomi_miband6_full"

class MiBand7Coordinator(HuamiKeyedCoordinator):
    adapter_id = "xiaomi_miband7"
    model_name = "Xiaomi Smart Band 7"
    sync_unique_suffix = "sync_xiaomi_miband7_full"

class AmazfitBipLiteCoordinator(HuamiKeyedCoordinator):
    adapter_id = "amazfit_bip_lite"
    model_name = "Amazfit Bip Lite"
    sync_unique_suffix = "sync_amazfit_bip_lite_full"

class AmazfitBand5Coordinator(HuamiKeyedCoordinator):
    adapter_id = "amazfit_band5"
    model_name = "Amazfit Band 5"
    sync_unique_suffix = "sync_amazfit_band5_full"

_COORDINATORS = {
    "xiaomi_miband3": MiBand3Coordinator,
    "xiaomi_miband4": MiBand4Coordinator,
    "xiaomi_miband5": MiBand5Coordinator,
    "xiaomi_miband6": MiBand6Coordinator,
    "xiaomi_miband7": MiBand7Coordinator,
    "amazfit_bip_lite": AmazfitBipLiteCoordinator,
    "amazfit_band5": AmazfitBand5Coordinator,
}

def _spec(adapter_id: str) -> BluetoothArchiveAdapterSpec:
    model = MODEL_BY_ADAPTER[adapter_id]
    def matchers() -> tuple[BluetoothCallbackMatcher, ...]:
        return tuple(
            [BluetoothCallbackMatcher(local_name=name, connectable=False) for name in model.names]
            + [BluetoothCallbackMatcher(service_uuid=SERVICE_UUID, connectable=False)]
        )
    def match(name: str | None, service_uuids: Iterable[str], manufacturer_data: dict[int, bytes] | None) -> dict[str, Any] | None:
        return keyed_band_identity(adapter_id, name, service_uuids, manufacturer_data)
    return BluetoothArchiveAdapterSpec(
        adapter_id=adapter_id,
        coordinator_factory=_COORDINATORS[adapter_id],
        bluetooth_matchers=matchers,
        match_bluetooth=match,
        advertisement_capabilities=frozenset(),
        sync_capabilities=frozenset({"health_history"}),
        remote_gatt_services=frozenset({SERVICE_UUID}),
        generic_identity_probe=False,
    )

MIBAND3_ARCHIVE_ADAPTER = _spec("xiaomi_miband3")
MIBAND4_ARCHIVE_ADAPTER = _spec("xiaomi_miband4")
MIBAND5_ARCHIVE_ADAPTER = _spec("xiaomi_miband5")
MIBAND6_ARCHIVE_ADAPTER = _spec("xiaomi_miband6")
MIBAND7_ARCHIVE_ADAPTER = _spec("xiaomi_miband7")
AMAZFIT_BIP_LITE_ARCHIVE_ADAPTER = _spec("amazfit_bip_lite")
AMAZFIT_BAND5_ARCHIVE_ADAPTER = _spec("amazfit_band5")
ARCHIVE_ADAPTERS = (
    MIBAND3_ARCHIVE_ADAPTER,
    MIBAND4_ARCHIVE_ADAPTER,
    MIBAND5_ARCHIVE_ADAPTER,
    MIBAND6_ARCHIVE_ADAPTER,
    MIBAND7_ARCHIVE_ADAPTER,
    AMAZFIT_BIP_LITE_ARCHIVE_ADAPTER,
    AMAZFIT_BAND5_ARCHIVE_ADAPTER,
)
