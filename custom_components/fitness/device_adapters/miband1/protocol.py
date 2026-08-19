"""Independent read-only protocol primitives for Xiaomi Mi Band 1/1A/1S.

The first-generation Mi Band family predates the later Huami authentication
service.  Its FEE0 service exposes a control point, minute activity stream,
realtime steps and battery state.  This module deliberately implements only
well-established read/sync operations; pairing/user-profile mutation and
firmware operations are out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

MIBAND1_SERVICE_UUID = "0000fee0-0000-1000-8000-00805f9b34fb"
MIBAND1_CONTROL_UUID = "0000ff05-0000-1000-8000-00805f9b34fb"
MIBAND1_REALTIME_STEPS_UUID = "0000ff06-0000-1000-8000-00805f9b34fb"
MIBAND1_ACTIVITY_UUID = "0000ff07-0000-1000-8000-00805f9b34fb"
MIBAND1_BATTERY_UUID = "0000ff0c-0000-1000-8000-00805f9b34fb"

CMD_FETCH_ACTIVITY = b"\x06"
CMD_STOP_SYNC = b"\x11"
CMD_ACTIVITY_ACK = 0x0A

ACTIVITY_HEADER_LENGTH = 11
ACTIVITY_RECORD_LENGTH = 3
ACTIVITY_TYPE_NORMAL = 0
ACTIVITY_TYPE_WALKING = 1
ACTIVITY_TYPE_RUNNING = 2
ACTIVITY_TYPE_NOT_WORN = 3
ACTIVITY_TYPE_LIGHT_SLEEP = 4
ACTIVITY_TYPE_DEEP_SLEEP = 5
ACTIVITY_TYPE_CHARGING = 6
ACTIVITY_TYPE_ON_BED = 7

_ACTIVITY_NAMES = {
    ACTIVITY_TYPE_NORMAL: "normal",
    ACTIVITY_TYPE_WALKING: "walking",
    ACTIVITY_TYPE_RUNNING: "running",
    ACTIVITY_TYPE_NOT_WORN: "not_worn",
    ACTIVITY_TYPE_LIGHT_SLEEP: "light_sleep",
    ACTIVITY_TYPE_DEEP_SLEEP: "deep_sleep",
    ACTIVITY_TYPE_CHARGING: "charging",
    ACTIVITY_TYPE_ON_BED: "on_bed",
}


@dataclass(slots=True, frozen=True)
class MiBand1ActivityHeader:
    """Header preceding one block of 3-byte, one-minute activity records."""

    data_type: int
    start_local: datetime
    total_records: int
    block_records: int

    @property
    def block_bytes(self) -> int:
        return self.block_records * ACTIVITY_RECORD_LENGTH


@dataclass(slots=True, frozen=True)
class MiBand1ActivitySample:
    """One minute of activity history from the band."""

    timestamp: datetime
    activity_type: int
    intensity: int
    steps: int

    @property
    def activity_name(self) -> str:
        return _ACTIVITY_NAMES.get(self.activity_type, f"unknown_{self.activity_type}")


@dataclass(slots=True, frozen=True)
class MiBand1BatteryState:
    """Documented battery-state characteristic fields."""

    battery: int | None
    last_charge_local: datetime | None
    charge_cycles: int | None
    charging: bool | None
    status: int | None


def _uuid16(value: int) -> str:
    return f"0000{value:04x}-0000-1000-8000-00805f9b34fb"


def miband1_identity(
    name: str | None,
    service_uuids: Iterable[str],
    manufacturer_data: dict[int, bytes] | None = None,
) -> dict[str, Any] | None:
    """Recognize only the legacy first-generation Mi Band family.

    FEE0 survived into later Huami devices, so service UUID alone is not safe
    evidence.  The original family used the short local name ``MI``; some 1S
    stacks expose an ``MI1S``-style name.  A historic Xiaomi MAC prefix is
    accepted only as supporting evidence by callers, never on its own here.
    """
    del manufacturer_data
    services = {str(value).strip().lower() for value in (service_uuids or ())}
    advertised = str(name or "").strip()
    compact = advertised.replace(" ", "").replace("-", "").lower()
    if MIBAND1_SERVICE_UUID not in services:
        return None
    if compact not in {"mi", "mi1", "mi1a", "mi1s", "miband1", "miband1a", "miband1s"}:
        return None
    model = "Xiaomi Mi Band 1 family"
    if compact.endswith("1s"):
        model = "Xiaomi Mi Band 1S"
    elif compact.endswith("1a"):
        model = "Xiaomi Mi Band 1A"
    return {
        "archive_adapter": "xiaomi_miband1",
        "archive_compatible": True,
        "workout_archive": False,
        "manufacturer": "Xiaomi",
        "fitness_vendor_identity": "xiaomi",
        "model": model,
        "model_id": "miband1_family",
        "smart_device_default_type": "fitness_tracker",
        "miband_protocol": "legacy_fee0_v1",
    }


def _local_datetime(year_offset: int, month_zero_based: int, day: int, hour: int, minute: int, second: int) -> datetime:
    """Decode the band's local wall-clock timestamp without inventing a zone."""
    try:
        return datetime(
            2000 + int(year_offset),
            int(month_zero_based) + 1,
            int(day),
            int(hour),
            int(minute),
            int(second),
        )
    except ValueError as err:
        raise ValueError("invalid Mi Band 1 timestamp") from err


def parse_activity_header(payload: bytes) -> MiBand1ActivityHeader:
    data = bytes(payload)
    if len(data) != ACTIVITY_HEADER_LENGTH:
        raise ValueError("invalid Mi Band 1 activity-header length")
    data_type = int(data[0])
    if data_type != 1:
        raise ValueError(f"unsupported Mi Band 1 activity data type {data_type}")
    start = _local_datetime(*data[1:7])
    total_records = int.from_bytes(data[7:9], "little")
    block_records = int.from_bytes(data[9:11], "little")
    if total_records > 60_000 or block_records > total_records:
        raise ValueError("invalid Mi Band 1 activity record counts")
    return MiBand1ActivityHeader(data_type, start, total_records, block_records)


def parse_activity_records(
    payload: bytes,
    *,
    start: datetime,
    timezone_info,
) -> tuple[MiBand1ActivitySample, ...]:
    """Parse complete minute triplets and convert local wall time to UTC."""
    from datetime import timedelta

    data = bytes(payload)
    if len(data) % ACTIVITY_RECORD_LENGTH:
        raise ValueError("misaligned Mi Band 1 activity payload")
    result: list[MiBand1ActivitySample] = []
    for index in range(0, len(data), ACTIVITY_RECORD_LENGTH):
        activity_type, intensity, steps = data[index : index + ACTIVITY_RECORD_LENGTH]
        local = start + timedelta(minutes=index // ACTIVITY_RECORD_LENGTH)
        aware = local.replace(tzinfo=timezone_info)
        result.append(
            MiBand1ActivitySample(
                timestamp=aware.astimezone(timezone.utc),
                activity_type=int(activity_type),
                intensity=int(intensity),
                steps=int(steps),
            )
        )
    return tuple(result)


def build_activity_ack(header: MiBand1ActivityHeader, block_bytes: int | None = None) -> bytes:
    """Acknowledge one complete block using its local timestamp and byte count."""
    start = header.start_local
    count = header.block_bytes if block_bytes is None else int(block_bytes)
    if not 0 <= count <= 0xFFFF:
        raise ValueError("invalid Mi Band 1 ACK byte count")
    return bytes(
        [
            CMD_ACTIVITY_ACK,
            start.year - 2000,
            start.month - 1,
            start.day,
            start.hour,
            start.minute,
            start.second,
            count & 0xFF,
            (count >> 8) & 0xFF,
        ]
    )


def parse_battery_state(payload: bytes) -> MiBand1BatteryState:
    data = bytes(payload)
    if len(data) < 10:
        raise ValueError("truncated Mi Band 1 battery payload")
    level = int(data[0]) if int(data[0]) <= 100 else None
    try:
        last_charge = _local_datetime(*data[1:7])
    except ValueError:
        last_charge = None
    cycles = int.from_bytes(data[7:9], "little")
    status = int(data[9])
    charging = True if status in {2, 3} else False if status in {1, 4} else None
    return MiBand1BatteryState(level, last_charge, cycles, charging, status)


def parse_realtime_steps(payload: bytes) -> int:
    data = bytes(payload)
    if len(data) < 4:
        raise ValueError("truncated Mi Band 1 realtime-steps payload")
    value = int.from_bytes(data[:4], "little")
    if value > 250_000:
        raise ValueError("invalid Mi Band 1 realtime steps")
    return value
