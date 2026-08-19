"""Protocol helpers for non-destructive keyed Huami legacy bands.

This module deliberately reuses only the stable FEE1 authentication/activity
wire contract already used by the Mi Band 2 adapter. It never sends AUTH_SEND_KEY,
so Home Assistant cannot replace the authentication key stored on the wearable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..miband2.protocol import (
    AUTH_REQUEST_RANDOM,
    AUTH_SEND_ENCRYPTED_PREFIX,
    FETCH_START,
    MIBAND2_ACTIVITY_UUID as ACTIVITY_UUID,
    MIBAND2_AUTH_UUID as AUTH_UUID,
    MIBAND2_FETCH_UUID as FETCH_UUID,
    MIBAND2_SERVICE_UUID as SERVICE_UUID,
    build_fetch_request,
    parse_activity_packet,
    parse_auth_notification,
    parse_fetch_start,
)

AUTH_KEY_BYTES = 16


@dataclass(slots=True, frozen=True)
class HuamiBandModel:
    adapter_id: str
    model_id: str
    model: str
    manufacturer: str
    vendor_identity: str
    names: tuple[str, ...]


MODELS: tuple[HuamiBandModel, ...] = (
    HuamiBandModel("xiaomi_miband3", "miband3", "Xiaomi Mi Band 3", "Xiaomi", "xiaomi", ("mi band 3", "xiaomi band 3")),
    HuamiBandModel("xiaomi_miband4", "miband4", "Xiaomi Mi Smart Band 4", "Xiaomi", "xiaomi", ("mi smart band 4", "mi band 4")),
    HuamiBandModel("xiaomi_miband5", "miband5", "Xiaomi Mi Smart Band 5", "Xiaomi", "xiaomi", ("mi smart band 5", "mi band 5")),
    HuamiBandModel("xiaomi_miband6", "miband6", "Xiaomi Mi Smart Band 6", "Xiaomi", "xiaomi", ("mi smart band 6", "mi band 6")),
    HuamiBandModel("xiaomi_miband7", "miband7", "Xiaomi Smart Band 7", "Xiaomi", "xiaomi", ("xiaomi smart band 7", "mi band 7", "smart band 7")),
    HuamiBandModel("amazfit_bip_lite", "bip_lite", "Amazfit Bip Lite", "Amazfit", "amazfit", ("amazfit bip lite",)),
    HuamiBandModel("amazfit_band5", "band5", "Amazfit Band 5", "Amazfit", "amazfit", ("amazfit band 5",)),
)
MODEL_BY_ADAPTER = {item.adapter_id: item for item in MODELS}


def normalize_auth_key(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        if len(value) != AUTH_KEY_BYTES:
            raise ValueError("Huami authentication key must contain 16 bytes")
        return value
    clean = str(value).strip().replace(" ", "").replace(":", "")
    if len(clean) != AUTH_KEY_BYTES * 2:
        raise ValueError("Huami authentication key must be 32 hexadecimal characters")
    try:
        raw = bytes.fromhex(clean)
    except ValueError as err:
        raise ValueError("Huami authentication key must be hexadecimal") from err
    if len(raw) != AUTH_KEY_BYTES:
        raise ValueError("Huami authentication key must contain 16 bytes")
    return raw


def _compact_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def keyed_band_identity(
    adapter_id: str,
    name: str | None,
    service_uuids: Iterable[str],
    manufacturer_data: dict[int, bytes] | None = None,
) -> dict[str, Any] | None:
    """Identify only one explicitly named Mi Band generation."""
    del manufacturer_data
    model = MODEL_BY_ADAPTER[adapter_id]
    services = {str(value).strip().lower() for value in (service_uuids or ())}
    normalized = _compact_name(name)
    if SERVICE_UUID not in services or normalized not in model.names:
        return None
    return {
        "archive_adapter": model.adapter_id,
        "archive_compatible": True,
        "workout_archive": False,
        "manufacturer": model.manufacturer,
        "fitness_vendor_identity": model.vendor_identity,
        "model": model.model,
        "model_id": model.model_id,
        "smart_device_default_type": "fitness_tracker",
        "miband_protocol": "huami_fee1_keyed",
        "requires_device_credentials": True,
        "credential_fields": ["auth_key"],
    }
