"""Independent read-only Ultrahuman Ring AIR BLE protocol primitives."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
import struct
from typing import Any

ULTRAHUMAN_COMMAND_SERVICE_UUID = "86f65000-f706-58a0-95b2-1fb9261e4dc7"
ULTRAHUMAN_COMMAND_WRITE_UUID = "86f65001-f706-58a0-95b2-1fb9261e4dc7"
ULTRAHUMAN_COMMAND_NOTIFY_UUID = "86f65002-f706-58a0-95b2-1fb9261e4dc7"
ULTRAHUMAN_STATE_SERVICE_UUID = "86f61000-f706-58a0-95b2-1fb9261e4dc7"
ULTRAHUMAN_STATE_CHAR_UUID = "86f61001-f706-58a0-95b2-1fb9261e4dc7"

OP_RECORDINGS = 0x04
OP_EARLIEST = 0x07
OP_LATEST = 0x08
RESULT_OK = 0x00
RESULT_NO_DATA = 0xEE
RESULT_FAILED = 0xFF

_NAME = re.compile(r"^UH_[0-9A-F]{12}$", re.IGNORECASE)
MAX_RECORDS_PER_RESPONSE = 32

MEASUREMENT_CONTEXT = {
    1: "normal",
    5: "exercise",
    6: "breathing",
    100: "not_on_finger",
}


@dataclass(slots=True, frozen=True)
class UltrahumanDeviceState:
    battery: int | None
    charging: bool | None
    device_temperature: float | None


def parse_device_state(payload: bytes) -> UltrahumanDeviceState:
    """Parse the documented 7-byte Ring AIR device-state characteristic."""
    data = bytes(payload)
    if len(data) < 7:
        raise ValueError("truncated Ultrahuman device-state payload")
    if data[:7] == b"\x00" * 7:
        return UltrahumanDeviceState(None, None, None)
    battery = int(data[0]) if 0 <= int(data[0]) <= 100 else None
    charging = True if data[5] == 0x03 else False if data[5] == 0x00 else None
    temperature = float(data[6])
    return UltrahumanDeviceState(battery, charging, temperature)


def measurement_context(value: int) -> str:
    return MEASUREMENT_CONTEXT.get(int(value), f"unknown_{int(value)}")


@dataclass(slots=True, frozen=True)
class UltrahumanRecording:
    """One 32-byte history slot from a Ring AIR."""

    index: int
    timestamp_a: int
    heart_rate: int
    hrv_ms: int
    spo2: int
    measurement_type: int
    timestamp_b: int
    skin_temperature_max: float
    skin_temperature_min: float
    timestamp_c: int
    activity_level: int
    steps: int
    stress: int

    @property
    def primary_timestamp(self) -> datetime | None:
        for value in (self.timestamp_a, self.timestamp_c, self.timestamp_b):
            if 946_684_800 <= int(value) <= 4_102_444_800:
                return datetime.fromtimestamp(int(value), tz=timezone.utc)
        return None


def ultrahuman_identity(name: str | None, service_uuids) -> dict[str, Any] | None:
    services = {str(value).lower() for value in (service_uuids or ())}
    normalized = str(name or "").strip()
    if not _NAME.fullmatch(normalized) and ULTRAHUMAN_COMMAND_SERVICE_UUID not in services:
        return None
    return {
        "archive_adapter": "ultrahuman_air",
        "workout_archive": False,
        "manufacturer": "Ultrahuman",
        "fitness_vendor_identity": "ultrahuman",
        "model": "Ultrahuman Ring AIR",
        "model_id": "ring_air",
        "smart_device_default_type": "smart_ring",
        "ultrahuman_protocol": "ring_air_ble_history_v1",
    }


def build_index_command(opcode: int) -> bytes:
    if opcode not in {OP_EARLIEST, OP_LATEST}:
        raise ValueError("unsupported Ultrahuman index opcode")
    return bytes([opcode])


def build_recordings_command(first_index: int) -> bytes:
    return bytes([OP_RECORDINGS]) + struct.pack("<H", int(first_index) & 0xFFFF)


def parse_index_response(payload: bytes, opcode: int) -> tuple[int, int | None]:
    data = bytes(payload)
    if len(data) < 3 or data[0] != opcode:
        raise ValueError("unexpected Ultrahuman index response")
    result = int(data[1])
    if result == RESULT_NO_DATA:
        return result, None
    if result != RESULT_OK or len(data) < 5:
        raise ValueError(f"Ultrahuman index request failed ({result:#04x})")
    return result, struct.unpack_from("<H", data, 3)[0]


def _safe_float(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None


def parse_recordings_response(payload: bytes) -> tuple[int, list[UltrahumanRecording]]:
    data = bytes(payload)
    if len(data) < 3 or data[0] != OP_RECORDINGS:
        raise ValueError("unexpected Ultrahuman recordings response")
    result = int(data[1])
    count = int(data[2])
    if result == RESULT_NO_DATA:
        return result, []
    if result != RESULT_OK:
        raise ValueError(f"Ultrahuman recordings request failed ({result:#04x})")
    if count > MAX_RECORDS_PER_RESPONSE:
        raise ValueError("Ultrahuman response contains too many records")
    required = 3 + count * 32
    if len(data) < required:
        raise ValueError("truncated Ultrahuman recordings response")

    records: list[UltrahumanRecording] = []
    for offset in range(3, required, 32):
        slot = data[offset : offset + 32]
        max_temp = _safe_float(struct.unpack_from("<f", slot, 12)[0])
        min_temp = _safe_float(struct.unpack_from("<f", slot, 16)[0])
        records.append(
            UltrahumanRecording(
                index=struct.unpack_from("<H", slot, 30)[0],
                timestamp_a=struct.unpack_from("<I", slot, 0)[0],
                heart_rate=slot[4],
                hrv_ms=slot[5],
                spo2=slot[6],
                measurement_type=slot[7],
                timestamp_b=struct.unpack_from("<I", slot, 8)[0],
                skin_temperature_max=max_temp if max_temp is not None else float("nan"),
                skin_temperature_min=min_temp if min_temp is not None else float("nan"),
                timestamp_c=struct.unpack_from("<I", slot, 20)[0],
                activity_level=struct.unpack_from("<H", slot, 24)[0],
                steps=struct.unpack_from("<H", slot, 26)[0],
                stress=struct.unpack_from("<H", slot, 28)[0],
            )
        )
    return result, records


def circular_distance(start: int, end: int) -> int:
    return (int(end) - int(start)) & 0xFFFF


def next_available_index(earliest: int, latest: int, checkpoint: int | None) -> int | None:
    """Return the next available uint16 slot after a durable checkpoint."""
    earliest &= 0xFFFF
    latest &= 0xFFFF
    if checkpoint is None:
        return earliest
    checkpoint &= 0xFFFF
    if circular_distance(earliest, checkpoint) > circular_distance(earliest, latest):
        # Device soft-reset or history wrapped beyond our old checkpoint.
        return earliest
    if checkpoint == latest:
        return None
    return (checkpoint + 1) & 0xFFFF
