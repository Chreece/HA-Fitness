"""Control-plane catalog for local smart workout devices.

The catalog describes setup UX only. Runtime protocol selection remains capability-
based inside each adapter and must never branch on a consumer model name.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import CAPABILITY_WORKOUT_HISTORY

MAX_SMART_WORKOUT_DEVICE_CHOICES = 32
MAX_SMART_DEVICE_MODEL_LABEL = 96

DEVICE_TYPE_AUTO = "auto"
DEVICE_TYPE_SPORT_WATCH = "sport_watch"
DEVICE_TYPE_BIKE_COMPUTER = "bike_computer"
DEVICE_TYPE_FITNESS_EQUIPMENT = "fitness_equipment"
DEVICE_TYPE_OTHER = "other"

DEVICE_TYPES = (
    DEVICE_TYPE_AUTO,
    DEVICE_TYPE_SPORT_WATCH,
    DEVICE_TYPE_BIKE_COMPUTER,
    DEVICE_TYPE_FITNESS_EQUIPMENT,
    DEVICE_TYPE_OTHER,
)


@dataclass(slots=True, frozen=True)
class SmartWorkoutVendor:
    """One vendor setup recipe exposed in the Fitness control plane."""

    vendor_id: str
    label: str
    device_types: tuple[str, ...]
    requires_pairing: bool
    guide_key: str


SUPPORTED_SETUP_VENDORS: tuple[SmartWorkoutVendor, ...] = (
    SmartWorkoutVendor(
        vendor_id="garmin",
        label="Garmin",
        device_types=(
            DEVICE_TYPE_AUTO,
            DEVICE_TYPE_SPORT_WATCH,
            DEVICE_TYPE_BIKE_COMPUTER,
            DEVICE_TYPE_OTHER,
        ),
        requires_pairing=True,
        guide_key="garmin_local",
    ),
)

_VENDOR_BY_ID = {item.vendor_id: item for item in SUPPORTED_SETUP_VENDORS}


def setup_vendor(vendor_id: str | None) -> SmartWorkoutVendor | None:
    """Return one setup recipe without any model routing."""
    return _VENDOR_BY_ID.get(str(vendor_id or "").strip().lower())


def _metadata_vendor(metadata: dict[str, Any] | None) -> str | None:
    """Return vendor identity from adapter/protocol evidence, not model names."""
    metadata = metadata or {}
    explicit = str(metadata.get("fitness_vendor_identity") or "").strip().lower()
    if explicit:
        return explicit
    manufacturer = str(metadata.get("manufacturer") or "").strip().lower()
    return manufacturer or None


def smart_workout_vendor(sensor) -> str:
    """Identify vendor only when physical-device evidence is non-conflicting.

    A stale endpoint alias must never turn a CYCPLUS physical device into a
    Garmin setup candidate (or vice versa). Consumer model/local names are not
    consulted.
    """
    vendors: set[str] = set()
    if vendor := _metadata_vendor(getattr(sensor, "metadata", {}) or {}):
        vendors.add(vendor)
    for endpoint in (getattr(sensor, "endpoints", {}) or {}).values():
        if vendor := _metadata_vendor(getattr(endpoint, "metadata", {}) or {}):
            vendors.add(vendor)
    if len(vendors) == 1:
        return next(iter(vendors))
    if len(vendors) > 1:
        return "conflict"
    return "unknown"


def smart_workout_archive_compatibility(sensor) -> bool | None:
    """Return verified archive compatibility, or None while verification is pending."""
    endpoints = getattr(sensor, "endpoints", {}) or {}
    bluetooth = endpoints.get("bluetooth")
    metadata = getattr(bluetooth, "metadata", {}) or {} if bluetooth is not None else {}
    if metadata.get("archive_adapter"):
        # Some direct-device adapters import wellness history (sleep, daily
        # activity, HR/HRV, SpO2, etc.) but do not expose a workout archive.
        # Keep those devices out of the Smart workout verification flow while
        # preserving the existing default for workout-capable archive adapters.
        if metadata.get("workout_archive") is False:
            return None
        value = metadata.get("archive_compatible")
        return value if isinstance(value, bool) else None
    if CAPABILITY_WORKOUT_HISTORY in set(getattr(sensor, "capabilities", set()) or set()):
        return True
    return None


def is_smart_workout_candidate(sensor) -> bool:
    """Return whether a physical device may enter Smart workout verification.

    Verified incompatible archive endpoints are deliberately hidden. Strong
    vendor candidates remain selectable so Fitness can automatically pair and
    perform the bounded GATT compatibility check.
    """
    if smart_workout_vendor(sensor) == "conflict":
        return False
    capabilities = set(getattr(sensor, "capabilities", set()) or set())
    if CAPABILITY_WORKOUT_HISTORY in capabilities:
        return True
    endpoints = getattr(sensor, "endpoints", {}) or {}
    for endpoint in endpoints.values():
        metadata = getattr(endpoint, "metadata", {}) or {}
        if (
            metadata.get("archive_adapter")
            and metadata.get("workout_archive") is not False
            and metadata.get("archive_compatible") is not False
        ):
            return True
    return False


def smart_workout_model_label(sensor) -> str:
    """Return display-only model text; it never selects a protocol backend."""
    metadata = getattr(sensor, "metadata", {}) or {}
    configured = str(metadata.get("smart_device_model_label") or "").strip()
    if configured:
        return configured[:MAX_SMART_DEVICE_MODEL_LABEL]
    for key in ("model", "model_id"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value[:MAX_SMART_DEVICE_MODEL_LABEL]
    return str(getattr(sensor, "name", None) or "Smart workout device")[
        :MAX_SMART_DEVICE_MODEL_LABEL
    ]


def smart_workout_device_type(sensor) -> str:
    """Return user-supplied display classification or a conservative default."""
    metadata = getattr(sensor, "metadata", {}) or {}
    configured = str(metadata.get("smart_device_type") or "").strip()
    if configured in DEVICE_TYPES:
        return configured
    adapter_default = str(metadata.get("smart_device_default_type") or "").strip()
    if adapter_default in DEVICE_TYPES:
        return adapter_default
    return DEVICE_TYPE_AUTO


def is_smart_workout_sensor(sensor) -> bool:
    """Return whether local workout archive compatibility is verified."""
    return (
        smart_workout_archive_compatibility(sensor) is True
        and CAPABILITY_WORKOUT_HISTORY in set(getattr(sensor, "capabilities", set()) or set())
    )


def smart_workout_capability_labels(sensor) -> tuple[str, ...]:
    """Return a bounded, stable control-plane capability summary."""
    labels: list[str] = []
    capabilities = set(getattr(sensor, "capabilities", set()) or set())
    compatibility = smart_workout_archive_compatibility(sensor)
    if compatibility is True and CAPABILITY_WORKOUT_HISTORY in capabilities:
        labels.append("workout archive")
    elif compatibility is None and is_smart_workout_candidate(sensor):
        labels.append("archive compatibility check pending")
    for capability in ("heart_rate", "cadence", "power", "speed", "battery"):
        if capability in capabilities:
            labels.append(capability.replace("_", " "))
    return tuple(labels[:8])
