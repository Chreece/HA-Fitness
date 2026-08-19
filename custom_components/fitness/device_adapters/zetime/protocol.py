"""Independent read-only MyKronoz ZeTime history protocol primitives."""
from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any

BASE = "0000{}-0000-1000-8000-00805f9b34fb"
ZETIME_SERVICE_UUID = BASE.format("6006")
ZETIME_PHONE_TO_WATCH_UUID = BASE.format("8001")
ZETIME_VALIDATE_NOTIFY_UUID = BASE.format("8002")
ZETIME_WATCH_REPLY_UUID = BASE.format("8003")
ZETIME_WATCH_NOTIFY_UUID = BASE.format("8004")

TYPE_REQUEST = 0x70
TYPE_RESPONSE = 0x80
SUBJECT_AVAILABILITY = 0x52
SUBJECT_ACTIVITY = 0x54
SUBJECT_SLEEP = 0x56
SUBJECT_HEART_RATE = 0x61

SLEEP_DEEP = 0x00
SLEEP_LIGHT = 0x01
SLEEP_AWAKE = 0x02
SLEEP_AWAKE_BEGIN = 0x03
SLEEP_BEGIN = 0x10
SLEEP_END = 0x11

MAX_FRAME_PAYLOAD = 4096


@dataclass(slots=True, frozen=True)
class ZeTimeFrame:
    subject: int
    message_type: int
    payload: bytes


@dataclass(slots=True, frozen=True)
class ZeTimeActivity:
    packet: int
    timestamp: int
    steps: int
    calories: int
    distance_m: int
    activity_minutes: int


@dataclass(slots=True, frozen=True)
class ZeTimeSleepEvent:
    packet: int
    timestamp: int
    sleep_type: int


@dataclass(slots=True, frozen=True)
class ZeTimeHeartRate:
    packet: int
    timestamp: int
    heart_rate: int


def zetime_identity(name: str | None, service_uuids) -> dict[str, Any] | None:
    services = {str(value).lower() for value in (service_uuids or ())}
    normalized = str(name or "").strip()
    if ZETIME_SERVICE_UUID not in services and not normalized.lower().startswith("zetime"):
        return None
    return {
        "archive_adapter": "mykronoz_zetime",
        "workout_archive": False,
        "manufacturer": "MyKronoz",
        "fitness_vendor_identity": "mykronoz",
        "model": "ZeTime",
        "model_id": "zetime",
        "smart_device_default_type": "smartwatch",
        "zetime_protocol": "6006_history_v1",
    }


def build_frame(subject: int, message_type: int, payload: bytes = b"") -> bytes:
    payload = bytes(payload)
    if len(payload) > MAX_FRAME_PAYLOAD:
        raise ValueError("ZeTime payload exceeds safe limit")
    return b"\x6f" + bytes([subject & 0xFF, message_type & 0xFF]) + struct.pack("<H", len(payload)) + payload + b"\x8f"


def build_history_request(subject: int, packet: int | None = None) -> bytes:
    if subject == SUBJECT_AVAILABILITY:
        return build_frame(subject, TYPE_REQUEST, b"\x00")
    if subject not in {SUBJECT_ACTIVITY, SUBJECT_SLEEP, SUBJECT_HEART_RATE}:
        raise ValueError("unsupported ZeTime history subject")
    if packet is None:
        packet = 0
    return build_frame(subject, TYPE_REQUEST, struct.pack("<H", int(packet) & 0xFFFF))


def parse_frame(data: bytes) -> ZeTimeFrame:
    data = bytes(data)
    if len(data) < 6 or data[0] != 0x6F or data[-1] != 0x8F:
        raise ValueError("invalid ZeTime frame")
    size = struct.unpack_from("<H", data, 3)[0]
    if size > MAX_FRAME_PAYLOAD or len(data) != size + 6:
        raise ValueError("invalid ZeTime frame length")
    return ZeTimeFrame(data[1], data[2], data[5 : 5 + size])


class ZeTimeFrameBuffer:
    """Bounded reassembler for ZeTime notifications split at 20-byte ATT writes."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[ZeTimeFrame]:
        self._buffer.extend(bytes(chunk))
        if len(self._buffer) > MAX_FRAME_PAYLOAD + 64:
            self._buffer.clear()
            raise ValueError("ZeTime receive buffer exceeds safe limit")
        frames: list[ZeTimeFrame] = []
        while self._buffer:
            if self._buffer[0] != 0x6F:
                try:
                    start = self._buffer.index(0x6F)
                except ValueError:
                    self._buffer.clear()
                    break
                del self._buffer[:start]
            if len(self._buffer) < 5:
                break
            size = struct.unpack_from("<H", self._buffer, 3)[0]
            if size > MAX_FRAME_PAYLOAD:
                self._buffer.clear()
                raise ValueError("ZeTime frame declares excessive payload")
            total = size + 6
            if len(self._buffer) < total:
                break
            raw = bytes(self._buffer[:total])
            del self._buffer[:total]
            frames.append(parse_frame(raw))
        return frames


def parse_availability(frame: ZeTimeFrame) -> tuple[int, int, int]:
    if frame.subject != SUBJECT_AVAILABILITY or frame.message_type != TYPE_RESPONSE or len(frame.payload) < 6:
        raise ValueError("invalid ZeTime availability response")
    return struct.unpack_from("<HHH", frame.payload, 0)


def parse_activity(frame: ZeTimeFrame) -> ZeTimeActivity:
    if frame.subject != SUBJECT_ACTIVITY or frame.message_type != TYPE_RESPONSE or len(frame.payload) < 22:
        raise ValueError("invalid ZeTime activity response")
    packet, timestamp, steps, calories, distance_m, active = struct.unpack_from("<HIIIII", frame.payload, 0)
    return ZeTimeActivity(packet, timestamp, steps, calories, distance_m, active)


def parse_sleep(frame: ZeTimeFrame) -> ZeTimeSleepEvent:
    if frame.subject != SUBJECT_SLEEP or frame.message_type != TYPE_RESPONSE or len(frame.payload) < 7:
        raise ValueError("invalid ZeTime sleep response")
    packet, timestamp, sleep_type = struct.unpack_from("<HIB", frame.payload, 0)
    return ZeTimeSleepEvent(packet, timestamp, sleep_type)


def parse_heart_rate(frame: ZeTimeFrame) -> ZeTimeHeartRate:
    if frame.subject != SUBJECT_HEART_RATE or frame.message_type != TYPE_RESPONSE or len(frame.payload) < 7:
        raise ValueError("invalid ZeTime heart-rate response")
    packet, timestamp, heart_rate = struct.unpack_from("<HIB", frame.payload, 0)
    return ZeTimeHeartRate(packet, timestamp, heart_rate)
