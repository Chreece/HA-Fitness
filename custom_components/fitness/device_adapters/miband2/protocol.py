"""Read-only Xiaomi Mi Band 2 protocol primitives.

The implementation is intentionally limited to the independently documented
legacy Huami BLE authentication and retained minute-activity transfer.  Raw
activity categories are preserved as context; we do not invent sleep stages
from category values whose semantics vary by firmware.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

MIBAND2_SERVICE_UUID = "0000fee1-0000-1000-8000-00805f9b34fb"
MIBAND2_BASIC_SERVICE_UUID = "0000fee0-0000-1000-8000-00805f9b34fb"
MIBAND2_AUTH_UUID = "00000009-0000-3512-2118-0009af100700"
MIBAND2_FETCH_UUID = "00000004-0000-3512-2118-0009af100700"
MIBAND2_ACTIVITY_UUID = "00000005-0000-3512-2118-0009af100700"
MIBAND2_BATTERY_UUID = "00000006-0000-3512-2118-0009af100700"
MIBAND2_REALTIME_STEPS_UUID = "00000007-0000-3512-2118-0009af100700"

# Legacy Mi Band 2 application-layer key documented by independent clients.
LEGACY_AUTH_KEY = b"0123456789@ABCDE"
AUTH_REQUEST_RANDOM = b"\x02\x08"
AUTH_SEND_ENCRYPTED_PREFIX = b"\x03\x08"
AUTH_RESPONSE = 0x10
AUTH_SUCCESS = 0x01
AUTH_FAIL = 0x04
FETCH_RESPONSE_PREFIX = b"\x10\x01\x01"
FETCH_START = b"\x02"

ACTIVITY_RECORDS_PER_PACKET = 4
ACTIVITY_RECORD_LENGTH = 4
ACTIVITY_PACKET_LENGTH = 1 + ACTIVITY_RECORDS_PER_PACKET * ACTIVITY_RECORD_LENGTH
NO_HEART_RATE = {0, 254, 255}


@dataclass(slots=True, frozen=True)
class MiBand2ActivitySample:
    timestamp: datetime
    category: int
    acceleration: int
    steps: int
    heart_rate: int | None

    @property
    def activity_level(self) -> float:
        # The published capture interprets acceleration as a 0..255 intensity
        # scale (e.g. 0x1b ~= 10%). Keep raw value in context and expose a
        # normalized percentage to the canonical catalog.
        return round(self.acceleration * 100.0 / 255.0, 1)


def miband2_identity(
    name: str | None,
    service_uuids: Iterable[str],
    manufacturer_data: dict[int, bytes] | None = None,
) -> dict[str, Any] | None:
    """Strictly identify Mi Band 2 without swallowing later Huami families."""
    del manufacturer_data
    services = {str(value).strip().lower() for value in (service_uuids or ())}
    compact = "".join(ch for ch in str(name or "").lower() if ch.isalnum())
    if MIBAND2_SERVICE_UUID not in services:
        return None
    if compact not in {"miband2", "xiaomimiband2"}:
        return None
    return {
        "archive_adapter": "xiaomi_miband2",
        "archive_compatible": True,
        "workout_archive": False,
        "manufacturer": "Xiaomi",
        "fitness_vendor_identity": "xiaomi",
        "model": "Xiaomi Mi Band 2",
        "model_id": "miband2",
        "smart_device_default_type": "fitness_tracker",
        "miband_protocol": "huami_fee1_v2",
    }


def parse_auth_notification(payload: bytes) -> tuple[str, bytes | None]:
    """Parse one legacy authentication notification."""
    data = bytes(payload)
    if len(data) < 3 or data[0] != AUTH_RESPONSE:
        raise ValueError("invalid Mi Band 2 authentication response")
    step, status = int(data[1]), int(data[2])
    if status == AUTH_FAIL:
        return (f"failed_{step}", None)
    if status != AUTH_SUCCESS:
        return (f"status_{step}_{status}", None)
    if step == 2:
        if len(data) != 19:
            raise ValueError("invalid Mi Band 2 authentication challenge")
        return ("challenge", data[3:19])
    if step == 3:
        return ("authenticated", None)
    if step == 1:
        return ("key_accepted", None)
    return (f"success_{step}", None)


def build_fetch_request(start_local: datetime) -> bytes:
    """Build the documented retained-activity start-date request."""
    dt = start_local.replace(second=0, microsecond=0)
    if not 2000 <= dt.year <= 2099:
        raise ValueError("Mi Band 2 fetch year out of range")
    return (
        b"\x01\x01"
        + int(dt.year).to_bytes(2, "little")
        + bytes([dt.month, dt.day, dt.hour, dt.minute, 0x00, 0x08])
    )


def parse_fetch_start(payload: bytes) -> datetime:
    """Return the band's actual local transfer start timestamp."""
    data = bytes(payload)
    if len(data) < 9 or not data.startswith(FETCH_RESPONSE_PREFIX):
        raise ValueError("invalid Mi Band 2 fetch-start response")
    year = int.from_bytes(data[3:5], "little")
    try:
        return datetime(year, data[5], data[6], data[7], data[8])
    except ValueError as err:
        raise ValueError("invalid Mi Band 2 fetch-start timestamp") from err


def parse_activity_packet(
    payload: bytes,
    *,
    transfer_start_local: datetime,
    packet_number: int,
    timezone_info,
) -> tuple[MiBand2ActivitySample, ...]:
    """Decode one indexed packet containing four one-minute observations."""
    data = bytes(payload)
    if len(data) != ACTIVITY_PACKET_LENGTH:
        raise ValueError("invalid Mi Band 2 activity packet length")
    if not 0 <= packet_number <= 0xFFFF:
        raise ValueError("invalid Mi Band 2 packet number")
    packet_index = int(data[0])
    if packet_index != packet_number % 256:
        raise ValueError("Mi Band 2 packet index does not match transfer sequence")

    samples: list[MiBand2ActivitySample] = []
    base_minute = packet_number * ACTIVITY_RECORDS_PER_PACKET
    for record_index in range(ACTIVITY_RECORDS_PER_PACKET):
        offset = 1 + record_index * ACTIVITY_RECORD_LENGTH
        category, acceleration, steps, hr_raw = data[offset : offset + ACTIVITY_RECORD_LENGTH]
        local = transfer_start_local + timedelta(minutes=base_minute + record_index)
        aware = local.replace(tzinfo=timezone_info).astimezone(timezone.utc)
        heart_rate = None if hr_raw in NO_HEART_RATE else int(hr_raw)
        if heart_rate is not None and not 20 <= heart_rate <= 260:
            heart_rate = None
        samples.append(
            MiBand2ActivitySample(
                timestamp=aware,
                category=int(category),
                acceleration=int(acceleration),
                steps=int(steps),
                heart_rate=heart_rate,
            )
        )
    return tuple(samples)


def parse_battery_level(payload: bytes) -> int:
    """Read only the stable leading battery-percentage byte."""
    data = bytes(payload)
    if not data or data[0] > 100:
        raise ValueError("invalid Mi Band 2 battery payload")
    return int(data[0])


def parse_realtime_steps(payload: bytes) -> int:
    data = bytes(payload)
    if len(data) < 4:
        raise ValueError("truncated Mi Band 2 realtime steps")
    value = int.from_bytes(data[:4], "little")
    if value > 250_000:
        raise ValueError("invalid Mi Band 2 realtime steps")
    return value
