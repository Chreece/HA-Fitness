"""Independent read-only HPlus daily-history protocol primitives."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

HPLUS_SERVICE_UUID = "14701820-620a-3973-7c78-9cfff0876abd"
HPLUS_CONTROL_UUID = "14702856-620a-3973-7c78-9cfff0876abd"
HPLUS_MEASURE_UUID = "14702853-620a-3973-7c78-9cfff0876abd"

CMD_GET_DAY_DATA = 0x15
DATA_DAY_SUMMARY = 0x38
DATA_DAY_SUMMARY_ALT = 0x39
DAY_SUMMARY_LENGTH = 17


@dataclass(slots=True, frozen=True)
class HPlusDaySummary:
    """One daily summary reported by an HPlus-protocol wearable."""

    day: date
    steps: int
    distance_m: int
    calories: int
    activity_minutes: int
    max_heart_rate: int
    min_heart_rate: int


def hplus_identity(
    name: str | None,
    service_uuids: Iterable[str],
) -> dict[str, Any] | None:
    """Recognize HPlus only from its protocol service, never a model-name list."""
    services = {str(value).strip().lower() for value in (service_uuids or ())}
    if HPLUS_SERVICE_UUID not in services:
        return None
    advertised = str(name or "").strip()
    return {
        "archive_adapter": "hplus_history",
        "workout_archive": False,
        "manufacturer": "HPlus protocol family",
        "fitness_vendor_identity": "hplus",
        "model": advertised or "HPlus-compatible wearable",
        "smart_device_default_type": "fitness_tracker",
        "hplus_protocol": "daily_summary_v1",
    }


def build_day_history_request() -> bytes:
    """Return the read-only command that requests all stored day summaries."""
    return bytes([CMD_GET_DAY_DATA])


def parse_day_summary(payload: bytes) -> HPlusDaySummary:
    """Parse the documented 0x38/0x39 daily summary payload."""
    data = bytes(payload)
    if len(data) != DAY_SUMMARY_LENGTH:
        raise ValueError("invalid HPlus day-summary length")
    if data[0] not in {DATA_DAY_SUMMARY, DATA_DAY_SUMMARY_ALT}:
        raise ValueError("not an HPlus day-summary packet")

    steps = data[2] * 256 + data[1]
    distance_m = data[4] * 256 + data[3]
    # This intentionally follows the documented HPlus wire formula.  It is
    # unusual, so do not simplify it without a real-device capture proving a
    # different encoding.
    calories = data[6] * 256 + data[8] * 256 + data[7] + data[5]
    year = data[10] * 256 + data[9]
    month = data[11]
    day = data[12]
    activity_minutes = data[14] * 256 + data[13]
    try:
        recorded_day = date(year, month, day)
    except ValueError as err:
        raise ValueError("invalid HPlus day-summary date") from err

    return HPlusDaySummary(
        day=recorded_day,
        steps=steps,
        distance_m=distance_m,
        calories=calories,
        activity_minutes=activity_minutes,
        max_heart_rate=data[15],
        min_heart_rate=data[16],
    )
