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


def smart_workout_vendor(sensor) -> str:
    """Identify a smart-workout vendor only from verified protocol metadata."""
    endpoints = getattr(sensor, "endpoints", {}) or {}
    bluetooth = endpoints.get("bluetooth")
    metadata: dict[str, Any] = {}
    if bluetooth is not None:
        metadata.update(getattr(bluetooth, "metadata", {}) or {})
    metadata.update(getattr(sensor, "metadata", {}) or {})

    archive_adapter = str(metadata.get("archive_adapter") or "").lower()
    if archive_adapter == "garmin_local" or metadata.get("garmin_local"):
        return "garmin"
    if metadata.get("cycplus_protocol"):
        return "cycplus"
    manufacturer = str(metadata.get("manufacturer") or "").strip().lower()
    if manufacturer == "garmin":
        return "garmin"
    if manufacturer == "cycplus":
        return "cycplus"
    return "unknown"


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
    vendor = smart_workout_vendor(sensor)
    if vendor == "cycplus":
        return DEVICE_TYPE_BIKE_COMPUTER
    return DEVICE_TYPE_AUTO


def is_smart_workout_sensor(sensor) -> bool:
    """Return whether this physical sensor exposes a local workout archive."""
    return CAPABILITY_WORKOUT_HISTORY in set(getattr(sensor, "capabilities", set()) or set())


def smart_workout_capability_labels(sensor) -> tuple[str, ...]:
    """Return a bounded, stable control-plane capability summary."""
    labels: list[str] = []
    capabilities = set(getattr(sensor, "capabilities", set()) or set())
    if CAPABILITY_WORKOUT_HISTORY in capabilities:
        labels.append("workout archive")
    for capability in ("heart_rate", "cadence", "power", "speed", "battery"):
        if capability in capabilities:
            labels.append(capability.replace("_", " "))
    return tuple(labels[:8])
