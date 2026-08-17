"""CYCPLUS M1 local BLE workout archive synchronization.

The M1 exposes a small vendor file-transfer protocol over a Nordic-UART-style
GATT service.  It does not provide a byte-offset command, so interrupted
transfers are resumed safely at the file boundary: Fitness persists the active
filename and completed-file catalogue, reconnects, validates the whole FIT
container, and retries only the unfinished file.
"""
from __future__ import annotations

import asyncio
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import io
from itertools import islice
import logging
import math
import re
from functools import partial
from typing import Any, Callable, Iterable

from homeassistant.components import bluetooth
from homeassistant.helpers.storage import Store

from ..const import (
    CAPABILITY_WORKOUT_HISTORY,
    CYCPLUS_SYNC_STORE_KEY,
    CYCPLUS_SYNC_STORE_VERSION,
    DOMAIN,
)
from ..providers.workouts import Workout, _dt

_LOGGER = logging.getLogger(__name__)

CYCPLUS_M1_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
CYCPLUS_M1_COMMAND_UUID = "6e400004-b5a3-f393-e0a9-e50e24dcca9e"
CYCPLUS_M1_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
CYCPLUS_M1_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

_READ_PERMISSION = b"\xff\x00\xff"
_DISK_SPACE = b"\x09\x00\x09"
_COPY = b"\x43"
_COPY_OK = b"\x06"
_COPY_FINISH = b"\x15"
_END_MARKER = b"\x04"
_FIT_REQUEST_SUFFIX = b"\x50"

_M1_NAME = re.compile(
    r"^(?:CYCPLUS[\s_-]*)?M1(?:[\s_-]*([0-9A-F]{4,16}))?$",
    re.IGNORECASE,
)
_FIT_FILENAME = re.compile(r"(?<!\d)(\d{14}\.fit)(?![A-Za-z0-9])", re.IGNORECASE)

SYNC_INTERVAL = timedelta(minutes=15)
MAX_TRANSFER_BYTES = 16 * 1024 * 1024
MAX_FILES_PER_SYNC = 3
MAX_BYTES_PER_SYNC = 24 * 1024 * 1024
BATCH_CONTINUE_DELAY = 60.0
BLE_CLEANUP_TIMEOUT = 5.0
SHUTDOWN_TIMEOUT = 12.0
MAX_FIT_RECORDS = 100_000
MAX_FIT_METADATA_FRAMES = 2_048
MAX_FIT_SESSIONS = 64
MAX_CATALOGUE_BYTES = 2 * 1024 * 1024
MAX_CATALOGUE_FILES = 4_096
MAX_STORED_DEVICES = 64
MAX_STORED_FILES_PER_DEVICE = 4_096
MAX_STORED_FILES_TOTAL = 8_192
PROTOCOL_TIMEOUT = 12.0
BLOCK_TIMEOUT = 20.0
FILE_RETRY_FRONT_LIMIT = 3
PROTOCOL_NOTIFICATION_QUEUE_LIMIT = 128

_FIT_RECORD_FIELDS = frozenset({
    "timestamp",
    "position_lat",
    "position_long",
    "enhanced_speed",
    "speed",
    "heart_rate",
    "power",
    "cadence",
})
_FIT_RETAINED_FRAMES = frozenset({
    "session",
    "record",
    "lap",
    "file_id",
    "device_info",
})

ERROR_CODE_BY_STAGE = {
    "connection": "connection_failed",
    "catalog": "catalog_failed",
    "transfer": "transfer_interrupted",
    "validation": "invalid_fit",
    "import": "import_failed",
}


def cycplus_m1_name_identity(name: str | None) -> dict[str, str] | None:
    """Return the route identity encoded in an M1 Bluetooth local name.

    Web Bluetooth intentionally cannot expose a device's real address.  The M1
    local name carries the same per-device hexadecimal number on its browser and
    Home Assistant routes, so that exact value is the safe bridge between them.
    A name match alone is never enough to enable the archive protocol; the local
    Home Assistant advertisement still has to expose the verified vendor service.
    """
    match = _M1_NAME.fullmatch(str(name or "").strip())
    if match is None:
        return None
    result = {"cycplus_model_id": "M1"}
    if match.group(1):
        number = match.group(1).upper()
        result.update(
            cycplus_device_number=number,
            fitness_physical_identity=f"cycplus:m1:{number.lower()}",
        )
    return result


def cycplus_m1_identity(
    name: str | None, service_uuids: Iterable[str]
) -> dict[str, str] | None:
    """Return verified M1 advertisement identity, including its visible number."""
    services = {str(value).lower() for value in service_uuids}
    name_identity = cycplus_m1_name_identity(name)
    if name_identity is None or CYCPLUS_M1_SERVICE_UUID not in services:
        return None
    result = {
        "manufacturer": "CYCPLUS",
        "model": "CYCPLUS M1 GPS Bike Computer",
        "model_id": "M1",
        "cycplus_protocol": "m1_ble_fit_archive_v1",
        **name_identity,
    }
    if name_identity.get("cycplus_device_number"):
        result["device_number"] = name_identity["cycplus_device_number"]
    return result


def cycplus_request(filename: str) -> bytes:
    """Build the M1 file request documented by compatible local clients."""
    encoded = filename.encode("ascii")
    suffix = (
        _FIT_REQUEST_SUFFIX
        if filename.lower().endswith(".fit")
        else bytes([_xor_checksum(bytes([0x05]) + encoded)])
    )
    return b"\x05" + encoded + suffix


def _xor_checksum(payload: bytes) -> int:
    result = 0
    for value in payload:
        result ^= value
    return result


def extract_fit_filenames(payload: bytes) -> list[str]:
    """Extract every timestamped FIT filename from text or JSON catalogues."""
    if len(payload) > MAX_CATALOGUE_BYTES:
        raise ValueError("CYCPLUS catalogue exceeds the safe size limit")
    text = bytes(payload).rstrip(b"\x00").decode("utf-8", errors="ignore")
    # A single bounded regex pass finds filenames in both JSON and plain-text
    # catalogues. Building a full JSON object first amplified a catalogue into a
    # much larger recursive Python tree and then scanned the same text twice.
    candidates = [match.group(1) for match in _FIT_FILENAME.finditer(text)]
    # File names are normally numeric and lower-case, but preserve the exact
    # spelling advertised by the device in case a firmware uses a case-sensitive
    # archive. De-duplicate case-insensitively so a JSON field plus embedded text
    # cannot schedule the same transfer twice.
    unique: dict[str, str] = {}
    for value in candidates:
        unique.setdefault(value.lower(), value)
        if len(unique) >= MAX_CATALOGUE_FILES:
            break
    return sorted(unique.values(), key=str.lower)


def parse_disk_space(payload: bytes) -> tuple[int | None, int | None]:
    """Decode the M1 free or ``free/total`` KiB response safely."""
    text = bytes(payload).decode("ascii", errors="ignore")
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if match is not None:
        free, total = int(match.group(1)), int(match.group(2))
        if total <= 0 or free > total:
            return None, None
        return free, total
    # Known M1 clients also observe a framed single integer which represents
    # free KiB only. Do not invent total capacity when firmware omits it.
    single = re.search(r"\d+", text)
    return (int(single.group(0)), None) if single is not None else (None, None)


def _fit_container(data: bytes) -> bytes | None:
    """Return exactly one framed FIT container, excluding transfer padding."""
    if len(data) < 14:
        return None
    header_size = data[0]
    if header_size not in {12, 14} or len(data) < header_size + 2:
        return None
    if data[8:12] != b".FIT":
        return None
    data_size = int.from_bytes(data[4:8], "little")
    container_size = header_size + data_size + 2
    if container_size > len(data):
        return None
    return bytes(data[:container_size])


def _valid_fit_container(data: bytes) -> bool:
    """Perform cheap FIT framing validation before invoking the full decoder."""
    return _fit_container(data) is not None


def _json_safe(
    value: Any, *, _depth: int = 0, _budget: list[int] | None = None
) -> Any:
    if _budget is None:
        _budget = [4096]
    if _budget[0] <= 0:
        return "<fitness-payload-budget-exhausted>"
    _budget[0] -= 1
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value[:512].hex()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value[:2048] if isinstance(value, str) else value
    if _depth >= 6:
        return f"<fitness-depth-limit:{type(value).__name__}>"
    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item, _depth=_depth + 1, _budget=_budget)
            for item in value[:100]
            if _budget[0] > 0
        ]
    if isinstance(value, dict):
        return {
            str(key)[:256]: _json_safe(
                item, _depth=_depth + 1, _budget=_budget
            )
            for key, item in islice(value.items(), 100)
            if _budget[0] > 0
        }
    return str(value)[:500]


def decode_fit_messages(data: bytes) -> list[tuple[str, dict[str, Any]]]:
    """Decode a bounded, dependency-neutral FIT workout snapshot.

    Record frames are the overwhelming majority of a FIT file. Retain only the
    fields used by Fitness calculations and reject implausibly large streams so
    a corrupt device file cannot expand into gigabytes of Python dictionaries.
    """
    container = _fit_container(data)
    if container is None:
        raise ValueError("invalid FIT container framing")

    import fitdecode  # Imported only in the executor-backed decode path.

    messages: list[tuple[str, dict[str, Any]]] = []
    record_count = 0
    metadata_count = 0
    with fitdecode.FitReader(
        io.BytesIO(container), check_crc=fitdecode.CrcCheck.RAISE
    ) as reader:
        for frame in reader:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            frame_name = str(frame.name)
            if frame_name not in _FIT_RETAINED_FRAMES:
                continue
            if frame_name == "record":
                record_count += 1
                if record_count > MAX_FIT_RECORDS:
                    raise ValueError("FIT file exceeds the safe record limit")
            else:
                metadata_count += 1
                if metadata_count > MAX_FIT_METADATA_FRAMES:
                    raise ValueError("FIT file exceeds the safe metadata limit")
            fields: dict[str, Any] = {}
            for field in frame.fields:
                name = str(field.name)
                if frame_name == "record" and name not in _FIT_RECORD_FIELDS:
                    continue
                value = _json_safe(field.value)
                if value is None:
                    continue
                if name in fields:
                    previous = fields[name]
                    fields[name] = (
                        [*previous, value] if isinstance(previous, list) else [previous, value]
                    )
                else:
                    fields[name] = value
            messages.append((frame_name, fields))
    return messages


def _value(values: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = values.get(key)
        if value not in (None, ""):
            return value
    return None


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _iso(value: Any) -> str | None:
    parsed = _dt(value)
    return parsed.isoformat() if parsed is not None else None


def _degrees(value: Any) -> float | None:
    numeric = _number(value)
    if numeric is None:
        return None
    if abs(numeric) > 180:
        numeric = numeric * 180.0 / (2**31)
    return numeric


def _mean(values: Iterable[Any]) -> float | None:
    total = 0.0
    count = 0
    for value in values:
        number = _number(value)
        if number is None:
            continue
        total += number
        count += 1
    return total / count if count else None


def _maximum(values: Iterable[Any]) -> float | None:
    result: float | None = None
    for value in values:
        number = _number(value)
        if number is not None and (result is None or number > result):
            result = number
    return result


def _battery_status(value: Any) -> str | None:
    """Normalize FIT battery status to the translated HA enum contract."""
    if value in (None, ""):
        return None
    numeric = {
        1: "new",
        2: "good",
        3: "ok",
        4: "low",
        5: "critical",
        6: "charging",
        7: "unknown",
    }
    number = _number(value)
    integer = int(number) if number is not None and number.is_integer() else None
    if integer in numeric:
        return numeric[integer]
    normalized = re.sub(r"[^a-z]+", "_", str(value).strip().lower()).strip("_")
    aliases = {
        "new": "new",
        "good": "good",
        "ok": "ok",
        "low": "low",
        "critical": "critical",
        "charging": "charging",
        "unknown": "unknown",
        "invalid": "unknown",
    }
    return aliases.get(normalized, "unknown")


def _session_records(
    records: list[dict[str, Any]],
    start: str | None,
    end: str | None,
    *,
    timed_records: list[tuple[datetime, dict[str, Any]]] | None = None,
    record_times: list[datetime] | None = None,
) -> list[dict[str, Any]]:
    start_dt, end_dt = _dt(start), _dt(end)
    if start_dt is None and end_dt is None:
        return records
    if timed_records is not None and record_times is not None:
        lower = bisect_left(record_times, start_dt) if start_dt is not None else 0
        upper = (
            bisect_right(record_times, end_dt)
            if end_dt is not None
            else len(timed_records)
        )
        return [record for _timestamp, record in timed_records[lower:upper]]
    selected = []
    for record in records:
        timestamp = _dt(record.get("timestamp"))
        if timestamp is None:
            continue
        if start_dt is not None and timestamp < start_dt:
            continue
        if end_dt is not None and timestamp > end_dt:
            continue
        selected.append(record)
    return selected


def _fit_device_attributes(
    messages: list[tuple[str, dict[str, Any]]], advertised_number: str | None
) -> dict[str, Any]:
    file_ids = [values for name, values in messages if name == "file_id"]
    device_info = [values for name, values in messages if name == "device_info"]
    primary = next(
        (item for item in device_info if str(item.get("device_index", "0")) in {"0", "creator"}),
        device_info[0] if device_info else {},
    )
    file_id = file_ids[0] if file_ids else {}
    manufacturer = _value(primary, "manufacturer") or _value(file_id, "manufacturer")
    product = (
        _value(primary, "product_name", "descriptor", "product")
        or _value(file_id, "product_name", "product")
    )
    serial = _value(primary, "serial_number") or _value(file_id, "serial_number")
    if str(serial or "").strip().lower() in {
        "0",
        "-1",
        "4294967295",
        "0xffffffff",
        "unknown",
    }:
        serial = None
    attributes = {
        "device_number": advertised_number,
        "fit_manufacturer": manufacturer,
        "fit_product": product,
        "fit_serial_number": serial,
        "fit_hardware_version": _value(primary, "hardware_version"),
        "fit_software_version": _value(primary, "software_version"),
        "fit_battery_voltage": _value(primary, "battery_voltage"),
        "fit_battery_status": _battery_status(_value(primary, "battery_status")),
    }
    return {
        key: _json_safe(value)
        for key, value in attributes.items()
        if value not in (None, "")
    }


@dataclass(slots=True)
class FitImportResult:
    workouts: list[Workout]
    device_attributes: dict[str, Any]
    sha256: str


def workouts_from_fit_messages(
    messages: list[tuple[str, dict[str, Any]]],
    *,
    filename: str,
    sensor_id: str,
    advertised_number: str | None,
    sha256: str,
) -> FitImportResult:
    """Normalize all sessions in one M1 FIT file into canonical workouts."""
    sessions = [values for name, values in messages if name == "session"]
    if len(sessions) > MAX_FIT_SESSIONS:
        raise ValueError("FIT file exceeds the safe session limit")
    records = [values for name, values in messages if name == "record"]
    file_ids = [values for name, values in messages if name == "file_id"]
    timed_records = sorted(
        (
            (timestamp, record)
            for record in records
            if (timestamp := _dt(record.get("timestamp"))) is not None
        ),
        key=lambda item: item[0],
    )
    record_times = [timestamp for timestamp, _record in timed_records]

    if not sessions and records:
        sessions = [{
            "start_time": records[0].get("timestamp"),
            "timestamp": records[-1].get("timestamp"),
            "sport": "cycling",
        }]
    if not sessions:
        raise ValueError("FIT file contains no completed session")

    workouts: list[Workout] = []
    for index, session in enumerate(sessions):
        start = _iso(_value(session, "start_time"))
        if start is None and file_ids:
            start = _iso(_value(file_ids[0], "time_created"))
        if start is None:
            filename_match = re.match(r"(\d{14})\.fit$", filename, re.IGNORECASE)
            if filename_match:
                try:
                    start = datetime.strptime(
                        filename_match.group(1), "%Y%m%d%H%M%S"
                    ).replace(tzinfo=timezone.utc).isoformat()
                except ValueError:
                    pass
        end = _iso(_value(session, "timestamp", "end_time"))
        duration = _number(_value(session, "total_timer_time", "total_elapsed_time"))
        elapsed = _number(_value(session, "total_elapsed_time"))
        if end is None and start is not None and duration is not None:
            end = (_dt(start) + timedelta(seconds=duration)).isoformat()

        relevant = _session_records(
            records,
            start,
            end,
            timed_records=timed_records,
            record_times=record_times,
        )
        first_position = next(
            (
                record
                for record in relevant
                if record.get("position_lat") is not None
                and record.get("position_long") is not None
            ),
            {},
        )
        start_latitude = _degrees(first_position.get("position_lat"))
        start_longitude = _degrees(first_position.get("position_long"))

        average_speed = _number(_value(session, "enhanced_avg_speed", "avg_speed"))
        maximum_speed = _number(_value(session, "enhanced_max_speed", "max_speed"))
        if average_speed is None:
            average_speed = _mean(
                _value(item, "enhanced_speed", "speed") for item in relevant
            )
        if maximum_speed is None:
            maximum_speed = _maximum(
                _value(item, "enhanced_speed", "speed") for item in relevant
            )

        total_work = _number(_value(session, "total_work"))
        summary = {
            key: _json_safe(value)
            for key, value in session.items()
            if value not in (None, "")
        }
        source = f"cycplus_m1:{sensor_id}:{filename}:{index}"
        workout = Workout(
            source=source,
            sport=str(_value(session, "sport") or "cycling"),
            start=start,
            end=end,
            duration_s=duration,
            moving_time_s=duration,
            elapsed_time_s=elapsed,
            distance_m=_number(_value(session, "total_distance")),
            avg_hr=_number(_value(session, "avg_heart_rate"))
            or _mean(item.get("heart_rate") for item in relevant),
            max_hr=_number(_value(session, "max_heart_rate"))
            or _maximum(item.get("heart_rate") for item in relevant),
            avg_power=_number(_value(session, "avg_power"))
            or _mean(item.get("power") for item in relevant),
            max_power=_number(_value(session, "max_power"))
            or _maximum(item.get("power") for item in relevant),
            weighted_power=_number(
                _value(session, "normalized_power", "weighted_average_power")
            ),
            avg_cadence=_number(_value(session, "avg_cadence"))
            or _mean(item.get("cadence") for item in relevant),
            max_cadence=_number(_value(session, "max_cadence"))
            or _maximum(item.get("cadence") for item in relevant),
            elevation_gain_m=_number(_value(session, "total_ascent")),
            elevation_loss_m=_number(_value(session, "total_descent")),
            calories=_number(_value(session, "total_calories")),
            aerobic_training_effect=_number(
                _value(session, "total_training_effect", "aerobic_training_effect")
            ),
            anaerobic_training_effect=_number(
                _value(session, "total_anaerobic_training_effect", "anaerobic_training_effect")
            ),
            training_load=_number(
                _value(session, "training_stress_score", "training_load")
            ),
            average_speed_m_s=average_speed,
            max_speed_m_s=maximum_speed,
            kilojoules=(total_work / 1000.0) if total_work is not None else None,
            start_latitude=start_latitude,
            start_longitude=start_longitude,
            device_name="CYCPLUS M1",
            sources=[source],
            provider_domains=["cycplus_m1"],
            extra={
                "fitness_adapter": "cycplus_m1",
                "fitness_history_source": "cycplus_m1_ble_fit",
                "source_filename": filename,
                "source_file_sha256": sha256,
                "fit_session_index": index,
                "fit_session_count": len(sessions),
                "fit_lap_count": int(_number(_value(session, "num_laps")) or len(laps)),
                "fit_record_count": len(relevant),
                "fit_avg_temperature_c": _number(_value(session, "avg_temperature")),
                "fit_max_temperature_c": _number(_value(session, "max_temperature")),
                "fit_sub_sport": _json_safe(_value(session, "sub_sport")),
                "fit_session": summary,
            },
        )
        factual_fields = (
            "sport", "start", "end", "duration_s", "moving_time_s",
            "elapsed_time_s", "distance_m", "avg_hr", "max_hr", "avg_power",
            "max_power", "weighted_power", "avg_cadence", "max_cadence",
            "elevation_gain_m", "elevation_loss_m", "calories",
            "aerobic_training_effect", "anaerobic_training_effect",
            "training_load", "average_speed_m_s", "max_speed_m_s", "kilojoules",
            "start_latitude", "start_longitude", "device_name",
        )
        workout.field_sources = {
            key: "cycplus_m1"
            for key in factual_fields
            if getattr(workout, key) is not None
        }
        workout.provider_values = {"cycplus_m1": summary}
        if workout.start:
            workouts.append(workout)

    if not workouts:
        raise ValueError("FIT file has no usable workout timestamp")
    return FitImportResult(
        workouts=workouts,
        device_attributes=_fit_device_attributes(messages, advertised_number),
        sha256=sha256,
    )


def parse_fit_workouts(
    data: bytes, *, filename: str, sensor_id: str, advertised_number: str | None
) -> FitImportResult:
    container = _fit_container(data)
    if container is None:
        raise ValueError("invalid FIT container framing")
    digest = hashlib.sha256(container).hexdigest()
    messages = decode_fit_messages(container)
    return workouts_from_fit_messages(
        messages,
        filename=filename,
        sensor_id=sensor_id,
        advertised_number=advertised_number,
        sha256=digest,
    )


class CycplusM1Protocol:
    """One connected M1 file-transfer session."""

    def __init__(self, client, progress: Callable[[int], None] | None = None) -> None:
        self.client = client
        self.progress = progress
        self._command_queue: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=PROTOCOL_NOTIFICATION_QUEUE_LIMIT
        )
        self._any_queue: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue(
            maxsize=PROTOCOL_NOTIFICATION_QUEUE_LIMIT
        )
        self._block_ready = asyncio.Event()
        self._collecting = False
        self._first_packet = False
        self._packet_count = 0
        self._buffer = bytearray()
        self._ended = False
        self._overflow = False
        self._last_progress_size = 0
        self._transfer_limit = MAX_TRANSFER_BYTES
        self._next_transfer_limit = MAX_TRANSFER_BYTES

    @staticmethod
    def _put_latest(queue: asyncio.Queue, value: Any) -> None:
        """Keep notification queues bounded while preserving newest responses."""
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(value)

    def _on_command(self, _sender, data: bytearray) -> None:
        payload = bytes(data)
        self._put_latest(self._command_queue, payload)
        self._put_latest(self._any_queue, ("command", payload))

    def _on_data(self, _sender, data: bytearray) -> None:
        payload = bytes(data)
        # Stream packets can number in the hundreds of thousands. They belong in
        # the bounded transfer buffer only; duplicating every packet into the
        # handshake queue would retain the whole file twice until finalization.
        if not self._collecting:
            self._put_latest(self._any_queue, ("data", payload))
        if payload == _END_MARKER:
            self._ended = True
            self._block_ready.set()
            return
        if not self._collecting:
            return
        if self._first_packet:
            payload = payload[3:]
            self._first_packet = False
        self._buffer.extend(payload)
        self._packet_count += 1
        if len(self._buffer) > self._transfer_limit:
            self._overflow = True
            self._block_ready.set()
            return
        if (
            self.progress is not None
            and len(self._buffer) - self._last_progress_size >= 4096
        ):
            self._last_progress_size = len(self._buffer)
            self.progress(len(self._buffer))
        if self._packet_count >= 6:
            self._block_ready.set()

    @staticmethod
    def _drain(queue: asyncio.Queue) -> None:
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    async def _write(self, uuid: str, payload: bytes) -> None:
        async with asyncio.timeout(PROTOCOL_TIMEOUT):
            await self.client.write_gatt_char(uuid, payload, response=False)

    async def _write_wait_any(self, uuid: str, payload: bytes) -> bytes:
        self._drain(self._any_queue)
        await self._write(uuid, payload)
        async with asyncio.timeout(PROTOCOL_TIMEOUT):
            _kind, response = await self._any_queue.get()
        return response

    async def _write_wait_command(
        self, uuid: str, payload: bytes, predicate: Callable[[bytes], bool]
    ) -> bytes:
        self._drain(self._command_queue)
        await self._write(uuid, payload)
        async with asyncio.timeout(PROTOCOL_TIMEOUT):
            while True:
                response = await self._command_queue.get()
                if predicate(response):
                    return response

    async def async_start(self) -> None:
        async with asyncio.timeout(PROTOCOL_TIMEOUT):
            await self.client.start_notify(
                CYCPLUS_M1_COMMAND_UUID, self._on_command
            )
        async with asyncio.timeout(PROTOCOL_TIMEOUT):
            await self.client.start_notify(CYCPLUS_M1_TX_UUID, self._on_data)

    async def async_stop(self) -> None:
        for uuid in (CYCPLUS_M1_COMMAND_UUID, CYCPLUS_M1_TX_UUID):
            try:
                async with asyncio.timeout(BLE_CLEANUP_TIMEOUT):
                    await self.client.stop_notify(uuid)
            except TimeoutError:
                _LOGGER.warning(
                    "Timed out stopping CYCPLUS M1 notification %s", uuid
                )
            except Exception:
                pass

    async def async_disk_space(self) -> tuple[int | None, int | None]:
        response = await self._write_wait_command(
            CYCPLUS_M1_COMMAND_UUID,
            _DISK_SPACE,
            lambda value: parse_disk_space(value)[0] is not None,
        )
        return parse_disk_space(response)

    async def _request_read_permission(self) -> None:
        await self._write_wait_command(
            CYCPLUS_M1_COMMAND_UUID,
            _READ_PERMISSION,
            lambda value: bool(value),
        )

    async def async_read_file(
        self, filename: str, *, maximum_bytes: int = MAX_TRANSFER_BYTES
    ) -> bytes:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", filename):
            raise ValueError("unsafe CYCPLUS filename")
        await self._request_read_permission()
        expected = b"\x06" + filename.encode("ascii")
        await self._write_wait_command(
            CYCPLUS_M1_COMMAND_UUID,
            cycplus_request(filename),
            lambda value: value.startswith(expected),
        )

        # Prepare the device's copy window, acknowledge it, then request the first
        # six-packet block. Each block has a three-byte prefix and two-byte trailer.
        await self._write_wait_any(CYCPLUS_M1_RX_UUID, _COPY)
        await self._write(CYCPLUS_M1_RX_UUID, _COPY_OK)

        self._buffer = bytearray()
        self._packet_count = 0
        self._first_packet = True
        self._ended = False
        self._overflow = False
        self._last_progress_size = 0
        self._transfer_limit = max(
            1,
            min(
                int(maximum_bytes),
                int(getattr(self, "_next_transfer_limit", MAX_TRANSFER_BYTES)),
                MAX_TRANSFER_BYTES,
            ),
        )
        self._collecting = True
        self._block_ready.clear()
        await self._write(CYCPLUS_M1_RX_UUID, _COPY)

        try:
            while True:
                async with asyncio.timeout(BLOCK_TIMEOUT):
                    await self._block_ready.wait()
                if self._overflow:
                    raise ValueError("CYCPLUS transfer exceeds the safe file-size limit")
                if len(self._buffer) < 2:
                    raise ValueError("CYCPLUS transfer block is truncated")
                del self._buffer[-2:]
                ended = self._ended
                self._packet_count = 0
                self._first_packet = True
                self._block_ready.clear()
                await self._write(CYCPLUS_M1_RX_UUID, _COPY_OK)
                if ended:
                    break
        finally:
            self._collecting = False

        await self._write_wait_any(CYCPLUS_M1_RX_UUID, _COPY_FINISH)
        await self._write_wait_any(CYCPLUS_M1_RX_UUID, _COPY_OK)
        # Do not strip trailing NUL bytes here: either byte of a valid FIT CRC can
        # legitimately be zero. FIT parsing trims transport padding from the
        # length in the container header; text catalogue parsing strips its own
        # padding after transfer.
        return bytes(self._buffer)

    async def async_file_catalog(self) -> tuple[str, bytes, list[str]]:
        errors = []
        empty: tuple[str, bytes, list[str]] | None = None
        for filename in ("filelist.txt", "workouts.json"):
            try:
                self._next_transfer_limit = MAX_CATALOGUE_BYTES
                payload = await self.async_read_file(filename)
                files = extract_fit_filenames(payload)
                if files:
                    return filename, payload, files
                if empty is None:
                    empty = (filename, payload, files)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                errors.append(f"{filename}: {err}")
            finally:
                self._next_transfer_limit = MAX_TRANSFER_BYTES
        if empty is not None:
            return empty
        raise RuntimeError("; ".join(errors) or "workout catalogue unavailable")


_DETAIL_META: dict[str, dict[str, Any]] = {
    "cycplus_device_number": {"icon": "mdi:identifier", "enabled_default": True},
    "cycplus_sync_state": {
        "icon": "mdi:sync", "enabled_default": True, "device_class": "enum",
        "options": ["idle", "waiting", "connecting", "syncing", "ready", "retrying", "error"],
    },
    "cycplus_last_sync": {
        "icon": "mdi:clock-check-outline", "enabled_default": True,
        "device_class": "timestamp",
    },
    "cycplus_last_successful_sync": {
        "icon": "mdi:check-circle-outline", "enabled_default": True,
        "device_class": "timestamp",
    },
    "cycplus_device_workout_count": {"icon": "mdi:calendar-multiple", "enabled_default": True},
    "cycplus_imported_file_count": {"icon": "mdi:file-check-outline", "enabled_default": True},
    "cycplus_pending_file_count": {"icon": "mdi:file-clock-outline", "enabled_default": True},
    "cycplus_active_file": {"icon": "mdi:file-download-outline", "enabled_default": True},
    "cycplus_downloaded_bytes": {
        "icon": "mdi:download", "enabled_default": False, "unit": "B",
        "device_class": "data_size", "state_class": "measurement",
    },
    "cycplus_retry_count": {"icon": "mdi:reload", "enabled_default": False},
    "cycplus_disk_free_kb": {
        "icon": "mdi:harddisk", "enabled_default": False, "unit": "KiB",
        "device_class": "data_size", "state_class": "measurement",
    },
    "cycplus_disk_total_kb": {
        "icon": "mdi:harddisk", "enabled_default": False, "unit": "KiB",
        "device_class": "data_size", "state_class": "measurement",
    },
    "cycplus_last_error": {
        "icon": "mdi:alert-circle-outline", "enabled_default": True,
        "device_class": "enum",
        "options": [
            "none", "connection_failed", "catalog_failed",
            "transfer_interrupted", "invalid_fit", "import_failed", "unknown",
        ],
    },
    "cycplus_latest_workout": {
        "icon": "mdi:bike-fast", "enabled_default": True,
        "device_class": "timestamp",
    },
    "cycplus_fit_serial_number": {"icon": "mdi:identifier", "enabled_default": False},
    "cycplus_fit_manufacturer": {"icon": "mdi:factory", "enabled_default": False},
    "cycplus_fit_product": {"icon": "mdi:devices", "enabled_default": False},
    "cycplus_fit_hardware_version": {"icon": "mdi:chip", "enabled_default": False},
    "cycplus_fit_software_version": {"icon": "mdi:code-tags", "enabled_default": False},
    "cycplus_fit_battery_voltage": {
        "icon": "mdi:battery", "enabled_default": False, "unit": "V",
        "device_class": "voltage", "state_class": "measurement",
    },
    "cycplus_fit_battery_status": {
        "icon": "mdi:battery-heart-variant", "enabled_default": False,
        "device_class": "enum",
        "options": ["new", "good", "ok", "low", "critical", "charging", "unknown"],
    },
}
for _key, _meta in _DETAIL_META.items():
    _meta.update(
        translation_key=_key,
        entity_category="diagnostic",
    )


class CycplusM1Coordinator:
    """Own automatic, profile-aware and restart-safe M1 synchronization."""

    def __init__(self, provider) -> None:
        self.provider = provider
        self.runtime = provider.runtime
        self.hass = provider.hass
        self._store = Store[dict[str, Any]](
            self.hass,
            CYCPLUS_SYNC_STORE_VERSION,
            CYCPLUS_SYNC_STORE_KEY,
            private=True,
        )
        self._state: dict[str, Any] = {"devices": {}}
        self._tasks: dict[str, asyncio.Task] = {}
        self._queued_after_task: dict[str, tuple[asyncio.Task, float]] = {}
        self._initialized = False
        self._stopping = False
        self._progress_publish: dict[str, tuple[int, float]] = {}
        self._save_lock = asyncio.Lock()
        # One archive connection/decode at a time prevents several accepted M1s
        # from saturating Bluetooth, the executor and profile persistence after
        # a restart or mass reassignment.
        self._sync_semaphore = asyncio.Semaphore(1)
        self._background_tasks: set[asyncio.Task] = set()

    def _start_background_task(self, coroutine, name: str) -> asyncio.Task:
        """Own short persistence tasks so provider shutdown can await them."""
        task = self.hass.async_create_background_task(
            coroutine, name, eager_start=False
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def async_setup(self) -> None:
        stored = await self._store.async_load() or {}
        devices = stored.get("devices")
        if isinstance(devices, dict):
            clean_devices: dict[str, dict[str, Any]] = {}
            remaining_files = MAX_STORED_FILES_TOTAL
            scalar_keys = {
                "sync_state", "last_sync", "last_successful_sync",
                "device_workout_count", "pending_file_count", "pending_file",
                "downloaded_bytes", "retry_count", "disk_free_kb",
                "disk_total_kb", "last_error_code", "latest_workout",
                "catalog_filename", "device_attributes",
            }
            for raw_sensor_id, raw_state in islice(
                devices.items(), MAX_STORED_DEVICES
            ):
                sensor_id = str(raw_sensor_id or "").strip()[:256]
                if not sensor_id or not isinstance(raw_state, dict):
                    continue
                state = {
                    key: _json_safe(raw_state.get(key), _budget=[512])
                    for key in scalar_keys
                    if raw_state.get(key) is not None
                }
                clean_files: dict[str, dict[str, Any]] = {}
                raw_files = raw_state.get("files")
                if isinstance(raw_files, dict) and remaining_files > 0:
                    file_limit = min(MAX_STORED_FILES_PER_DEVICE, remaining_files)
                    for raw_name, raw_record in islice(raw_files.items(), file_limit):
                        name = str(raw_name or "").strip()[:64]
                        if not _FIT_FILENAME.fullmatch(name) or not isinstance(raw_record, dict):
                            continue
                        clean = _json_safe(raw_record, _budget=[1_024])
                        if isinstance(clean, dict):
                            clean_files[name] = clean
                    remaining_files -= len(clean_files)
                state["files"] = clean_files
                raw_failures = raw_state.get("file_failures")
                if isinstance(raw_failures, dict):
                    state["file_failures"] = {
                        str(name)[:64]: _json_safe(value, _budget=[64])
                        for name, value in islice(
                            raw_failures.items(), MAX_STORED_FILES_PER_DEVICE
                        )
                        if _FIT_FILENAME.fullmatch(str(name or "").strip())
                        and isinstance(value, dict)
                    }
                clean_devices[sensor_id] = state
            self._state = {"devices": clean_devices}
        self._initialized = True
        if int(stored.get("workout_compaction_version") or 0) < 1:
            for state in self._state.get("devices", {}).values():
                files = state.get("files") if isinstance(state, dict) else None
                if not isinstance(files, dict):
                    continue
                for record in files.values():
                    workouts = record.get("workouts") if isinstance(record, dict) else None
                    if not isinstance(workouts, list):
                        continue
                    compacted = []
                    for item in workouts:
                        if not isinstance(item, dict):
                            continue
                        try:
                            compacted.append(Workout(**item).as_persistent_dict())
                        except TypeError:
                            continue
                    record["workouts"] = compacted
            self._state["workout_compaction_version"] = 1
        # Rewrite a bounded snapshot even when the old compaction marker exists;
        # this removes oversized/corrupt legacy state before normal scheduling.
        self._state["workout_compaction_version"] = 1
        await self._save()

    def _device(self, sensor_id: str) -> dict[str, Any]:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        devices = self._state.setdefault("devices", {})
        state = devices.get(sensor_id)
        if not isinstance(state, dict):
            if len(devices) >= MAX_STORED_DEVICES:
                inactive = next(
                    (
                        key for key in devices
                        if key not in self._tasks
                        or self._tasks[key].done()
                    ),
                    next(iter(devices)),
                )
                devices.pop(inactive, None)
            state = devices[sensor_id] = {"files": {}, "retry_count": 0}
        # Release candidates before this version stored raw exception text. It
        # remains neither useful nor appropriate as localized entity state.
        state.pop("last_error", None)
        return state

    def _migrate_sensor_state(self, old_id: str, new_id: str) -> str:
        """Move checkpoints when identity enrichment changes the canonical ID."""
        old_id = str(old_id)
        new_id = self.runtime.resolve_sensor_id(new_id)
        if old_id == new_id:
            return new_id
        devices = self._state.setdefault("devices", {})
        old = devices.pop(old_id, None)
        current = devices.get(new_id)
        if isinstance(old, dict):
            if isinstance(current, dict):
                old_files = old.get("files") if isinstance(old.get("files"), dict) else {}
                current_files = (
                    current.get("files") if isinstance(current.get("files"), dict) else {}
                )
                merged = {**current, **old}
                merged["files"] = dict(
                    list({**current_files, **old_files}.items())[
                        -MAX_STORED_FILES_PER_DEVICE:
                    ]
                )
                latest = max(
                    str(old.get("latest_workout") or ""),
                    str(current.get("latest_workout") or ""),
                )
                if latest:
                    merged["latest_workout"] = latest
                devices[new_id] = merged
            else:
                devices[new_id] = old

        task = self._tasks.pop(old_id, None)
        if task is not None and not task.done():
            self._tasks.setdefault(new_id, task)
        queued = self._queued_after_task.pop(old_id, None)
        if queued is not None:
            self._queued_after_task[new_id] = queued
        progress = self._progress_publish.pop(old_id, None)
        if progress is not None:
            self._progress_publish[new_id] = progress
        return new_id

    async def _save(self) -> None:
        if self._initialized:
            async with self._save_lock:
                await self._store.async_save(self._state)

    def advertise(self, sensor_id: str, identity: dict[str, str]) -> None:
        """Publish static identity and schedule sync only after user acceptance."""
        details = {
            "cycplus_device_number": identity.get("device_number"),
        }
        self.runtime.publish_details(
            sensor_id,
            {key: value for key, value in details.items() if value not in (None, "")},
            transport="cycplus_m1_advertisement",
            metadata=_DETAIL_META,
            priority=85,
        )
        self._publish(sensor_id)
        if self.runtime.sensor_is_accepted(sensor_id):
            self.schedule(sensor_id, delay=2.0)

    def acceptance_changed(self, sensor_id: str, accepted: bool) -> None:
        if accepted:
            self.schedule(sensor_id, delay=1.0, force=True)
            return
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        task = self._tasks.pop(sensor_id, None)
        self._queued_after_task.pop(sensor_id, None)
        if task is not None and not task.done():
            task.cancel()

    def assignment_changed(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if not self.runtime.sensor_assigned_profile_ids(sensor_id):
            task = self._tasks.pop(sensor_id, None)
            self._queued_after_task.pop(sensor_id, None)
            if task is not None and not task.done():
                task.cancel()
            state = self._device(sensor_id)
            state.update(
                sync_state="idle", pending_file=None, pending_file_count=0
            )
            self._publish(sensor_id)
            self._start_background_task(
                self._save(),
                f"fitness pause unassigned CYCPLUS M1 sync {sensor_id}",
            )
            return
        if self.runtime.sensor_is_accepted(sensor_id):
            self.schedule(sensor_id, delay=0.5, force=True)

    def forget_sensor(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        task = self._tasks.pop(sensor_id, None)
        self._queued_after_task.pop(sensor_id, None)
        if task is not None and not task.done():
            task.cancel()
        if self._state.setdefault("devices", {}).pop(sensor_id, None) is not None:
            self._start_background_task(
                self._save(), f"fitness forget CYCPLUS M1 sync state {sensor_id}"
            )

    def schedule(self, sensor_id: str, *, delay: float, force: bool = False) -> None:
        if self._stopping or not self._initialized:
            return
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if not force:
            last = _dt(self._device(sensor_id).get("last_successful_sync"))
            if last is not None and datetime.now(timezone.utc) - last < SYNC_INTERVAL:
                return
        current = self._tasks.get(sensor_id)
        if current is not None and not current.done():
            if force:
                self._queue_after_task(sensor_id, current, delay)
            return

        async def _delayed() -> None:
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                await self._async_sync(sensor_id, force=force)
            except asyncio.CancelledError:
                raise
            finally:
                current_task = asyncio.current_task()
                resolved = self.runtime.resolve_sensor_id(sensor_id)
                for task_id in {sensor_id, resolved}:
                    if self._tasks.get(task_id) is current_task:
                        self._tasks.pop(task_id, None)

        self._tasks[sensor_id] = self.hass.async_create_background_task(
            _delayed(), f"fitness CYCPLUS M1 workout sync {sensor_id}", eager_start=False
        )

    def _queue_after_task(
        self, sensor_id: str, task: asyncio.Task, delay: float
    ) -> None:
        """Coalesce forced retries without interrupting an active BLE transfer."""
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        existing = self._queued_after_task.get(sensor_id)
        if existing is not None and existing[0] is task:
            self._queued_after_task[sensor_id] = (task, min(existing[1], delay))
            return
        self._queued_after_task[sensor_id] = (task, delay)

        def _queue(finished: asyncio.Task) -> None:
            canonical = self.runtime.resolve_sensor_id(sensor_id)
            queued = self._queued_after_task.get(canonical)
            if queued is None or queued[0] is not finished:
                return
            _task, queued_delay = self._queued_after_task.pop(canonical)
            self.hass.loop.call_soon(
                lambda: self.schedule(canonical, delay=queued_delay, force=True)
            )

        task.add_done_callback(_queue)

    def _schedule_after_current(self, sensor_id: str, delay: float) -> None:
        """Queue a retry after the current task has removed its task marker."""
        current = asyncio.current_task()
        if current is None:
            self.hass.loop.call_soon(
                lambda: self.schedule(sensor_id, delay=delay, force=True)
            )
            return
        self._queue_after_task(sensor_id, current, delay)

    async def async_sync_now(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        task = self._tasks.get(sensor_id)
        if task is not None and not task.done():
            self._queue_after_task(sensor_id, task, 0.0)
            return
        await self._async_sync(sensor_id, force=True)

    def _publish(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        state = self._device(sensor_id)
        files = state.get("files") if isinstance(state.get("files"), dict) else {}
        values = {
            "cycplus_sync_state": state.get("sync_state", "idle"),
            "cycplus_last_sync": state.get("last_sync"),
            "cycplus_last_successful_sync": state.get("last_successful_sync"),
            "cycplus_device_workout_count": state.get("device_workout_count"),
            "cycplus_imported_file_count": len(files),
            "cycplus_pending_file_count": state.get("pending_file_count", 0),
            "cycplus_active_file": state.get("pending_file") or "",
            "cycplus_downloaded_bytes": state.get("downloaded_bytes"),
            "cycplus_retry_count": state.get("retry_count", 0),
            "cycplus_disk_free_kb": state.get("disk_free_kb"),
            "cycplus_disk_total_kb": state.get("disk_total_kb"),
            "cycplus_last_error": state.get("last_error_code") or "none",
            "cycplus_latest_workout": state.get("latest_workout"),
        }
        attrs = state.get("device_attributes")
        if isinstance(attrs, dict):
            values.update({f"cycplus_{key}": value for key, value in attrs.items()})
        self.runtime.publish_details(
            sensor_id,
            {key: value for key, value in values.items() if value is not None},
            transport="cycplus_m1_sync",
            metadata=_DETAIL_META,
            priority=95,
        )

    def _progress(self, sensor_id: str, size: int) -> None:
        now = self.hass.loop.time()
        previous_size, previous_time = self._progress_publish.get(sensor_id, (0, 0.0))
        if size - previous_size < 65536 and now - previous_time < 5.0:
            return
        self._progress_publish[sensor_id] = (size, now)
        state = self._device(sensor_id)
        state["downloaded_bytes"] = size
        self._publish(sensor_id)

    async def _import_records_to_profiles(
        self,
        sensor_id: str,
        records: list[dict[str, Any]],
        profile_ids: list[str],
    ) -> None:
        """Import one whole sync batch with at most one profile-store rewrite."""
        for profile_id in profile_ids:
            manager = self.hass.data.get(DOMAIN, {}).get(profile_id)
            if manager is None:
                continue
            pending_records: list[dict[str, Any]] = []
            profile_workouts: list[Workout] = []
            for record in records:
                imported = {
                    str(value) for value in record.get("imported_profiles") or []
                }
                if profile_id in imported:
                    continue
                payload = record.get("workouts")
                if not isinstance(payload, list):
                    continue
                record_workouts: list[Workout] = []
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    try:
                        record_workouts.append(Workout(**item))
                    except TypeError:
                        continue
                if not record_workouts:
                    continue
                pending_records.append(record)
                profile_workouts.extend(record_workouts)
            if not profile_workouts:
                continue
            # Manager enrichment is profile-specific and mutates the snapshots.
            await manager.async_import_device_workouts(profile_workouts)
            for record in pending_records:
                imported = {
                    str(value) for value in record.get("imported_profiles") or []
                }
                imported.add(profile_id)
                record["imported_profiles"] = sorted(imported)

    def _apply_fit_device_attributes(
        self, sensor_id: str, attributes: dict[str, Any]
    ) -> str:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        previous_id = sensor_id
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if sensor is None or endpoint is None:
            return sensor_id
        metadata = dict(endpoint.metadata)
        metadata.update({
            "manufacturer": "CYCPLUS",
            "model": "CYCPLUS M1 GPS Bike Computer",
            "model_id": "M1",
        })
        # FIT ``device_info`` values describe the recording source inside a
        # workout container.  They are useful diagnostics but do not share the
        # identity namespace of Bluetooth Device Information.  Promoting them to
        # HA DeviceInfo used to replace the GATT serial/revisions and split one
        # physical M1 into separate browser and local-archive devices.
        for metadata_key, fit_key in (
            ("serial_number", "fit_serial_number"),
            ("hardware_revision", "fit_hardware_version"),
            ("software_revision", "fit_software_version"),
        ):
            fit_value = attributes.get(fit_key)
            if fit_value in (None, "", 0, "0"):
                continue
            for target in (metadata, sensor.metadata):
                current = target.get(metadata_key)
                if current not in (None, "") and str(current) == str(fit_value):
                    target.pop(metadata_key, None)
        merged = self.runtime.register_transport_sensor(
            transport="bluetooth",
            endpoint_id=endpoint.endpoint_id,
            name=sensor.name,
            capabilities=set(endpoint.capabilities),
            address=endpoint.address,
            source=endpoint.source,
            last_seen=endpoint.last_seen,
            rssi=endpoint.rssi,
            available=endpoint.available,
            metadata=metadata,
        )
        return self._migrate_sensor_state(previous_id, merged.sensor_id)

    async def _async_sync(self, requested_sensor_id: str, *, force: bool = False) -> None:
        """Serialize device archive work across all CYCPLUS displays."""
        async with self._sync_semaphore:
            await self._async_sync_serialized(requested_sensor_id, force=force)

    async def _async_sync_serialized(
        self, requested_sensor_id: str, *, force: bool = False
    ) -> None:
        sensor_id = self.runtime.resolve_sensor_id(requested_sensor_id)
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if (
            self._stopping
            or sensor is None
            or endpoint is None
            or CAPABILITY_WORKOUT_HISTORY not in sensor.capabilities
            or not self.runtime.sensor_is_accepted(sensor_id)
        ):
            return
        profile_ids = self.runtime.sensor_assigned_profile_ids(sensor_id)
        state = self._device(sensor_id)
        if not profile_ids:
            state.update(
                sync_state="idle", pending_file_count=0, last_error_code="none"
            )
            self._publish(sensor_id)
            return

        if not force and state.get("last_successful_sync"):
            last = _dt(state.get("last_successful_sync"))
            if last is not None and datetime.now(timezone.utc) - last < SYNC_INTERVAL:
                return

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, endpoint.address, connectable=True
        )
        if ble_device is None:
            state.update(sync_state="waiting", last_error_code="none")
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, 60.0)
            return

        lock = self.provider._connect_lock(sensor_id)
        client = None
        protocol = None
        stage = "connection"
        try:
            async with lock:
                sensor_id = self.runtime.resolve_sensor_id(sensor_id)
                sensor = self.runtime.sensors.get(sensor_id)
                endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
                if sensor is None or endpoint is None:
                    return
                if self.provider.sensor_connected(sensor_id):
                    state.update(sync_state="waiting", last_error_code="none")
                    self._publish(sensor_id)
                    self._schedule_after_current(sensor_id, 60.0)
                    return

                state.update(
                    sync_state="connecting",
                    last_sync=datetime.now(timezone.utc).isoformat(),
                    last_error_code="none",
                )
                self._publish(sensor_id)
                client = await self.provider.establish_connection(
                    ble_device, sensor.name or endpoint.address, max_attempts=4
                )
                previous_id = sensor_id
                sensor = await self.provider._async_enrich_identity(
                    sensor, endpoint, client, manage_client_state=False
                )
                sensor_id = self._migrate_sensor_state(previous_id, sensor.sensor_id)
                state = self._device(sensor_id)
                protocol = CycplusM1Protocol(
                    client, progress=lambda size: self._progress(sensor_id, size)
                )
                await protocol.async_start()

                state["sync_state"] = "syncing"
                self._publish(sensor_id)
                try:
                    free, total = await protocol.async_disk_space()
                except Exception:
                    free, total = None, None
                if free is not None:
                    state["disk_free_kb"] = free
                if total is not None:
                    state["disk_total_kb"] = total

                stage = "catalog"
                catalog_name, _catalog, filenames = await protocol.async_file_catalog()
                state["catalog_filename"] = catalog_name
                state["device_workout_count"] = len(filenames)
                files = state.setdefault("files", {})
                if not isinstance(files, dict):
                    files = state["files"] = {}
                file_failures = state.setdefault("file_failures", {})
                if not isinstance(file_failures, dict):
                    file_failures = state["file_failures"] = {}
                for stale_name, failure in tuple(file_failures.items()):
                    if (
                        not isinstance(failure, dict)
                        or stale_name not in filenames
                        or stale_name in files
                    ):
                        file_failures.pop(stale_name, None)

                pending = state.get("pending_file")
                queue = [name for name in filenames if name not in files]
                queue.sort(
                    key=lambda name: (
                        int((file_failures.get(name) or {}).get("attempts") or 0)
                        >= FILE_RETRY_FRONT_LIMIT,
                        name.lower(),
                    )
                )
                pending_attempts = int(
                    (file_failures.get(pending) or {}).get("attempts") or 0
                )
                if pending in queue and pending_attempts < FILE_RETRY_FRONT_LIMIT:
                    queue.remove(pending)
                    queue.insert(0, pending)
                state["pending_file_count"] = len(queue)
                self._publish(sensor_id)

                # One synchronization cycle is intentionally small. Cached
                # records awaiting a newly assigned profile share the same batch
                # budget as downloads, preventing a 183-file archive from causing
                # hundreds of complete profile-history rewrites in one session.
                records_to_import = [
                    record
                    for record in files.values()
                    if isinstance(record, dict)
                    and any(
                        profile_id
                        not in {
                            str(value)
                            for value in record.get("imported_profiles") or []
                        }
                        for profile_id in profile_ids
                    )
                ][:MAX_FILES_PER_SYNC]
                download_slots = max(
                    0, MAX_FILES_PER_SYNC - len(records_to_import)
                )

                identity = cycplus_m1_identity(
                    endpoint.metadata.get("advertised_name") or sensor.name,
                    endpoint.metadata.get("service_uuids") or [CYCPLUS_M1_SERVICE_UUID],
                ) or {}
                advertised_number = identity.get("device_number")

                batch_bytes = 0
                for filename in queue[:download_slots]:
                    if not self.runtime.sensor_assigned_profile_ids(sensor_id):
                        return
                    state.update(
                        pending_file=filename,
                        downloaded_bytes=0,
                        pending_file_count=len([item for item in queue if item not in files]),
                    )
                    self._publish(sensor_id)
                    stage = "transfer"
                    payload = await protocol.async_read_file(filename)
                    payload_size = len(payload)
                    stage = "validation"
                    result = await self.hass.async_add_executor_job(
                        partial(
                            parse_fit_workouts,
                            payload,
                            filename=filename,
                            sensor_id=sensor_id,
                            advertised_number=advertised_number,
                        )
                    )
                    stage = "import"
                    sensor_id = self._apply_fit_device_attributes(
                        sensor_id, result.device_attributes
                    )
                    state = self._device(sensor_id)
                    files = state.setdefault("files", {})
                    record = {
                        "sha256": result.sha256,
                        "size": payload_size,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "workouts": [
                            workout.as_persistent_dict()
                            for workout in result.workouts
                        ],
                        "imported_profiles": [],
                    }
                    files[filename] = record
                    records_to_import.append(record)
                    file_failures.pop(filename, None)
                    state["device_attributes"] = result.device_attributes
                    starts = [
                        _dt(workout.start)
                        for workout in result.workouts
                        if _dt(workout.start) is not None
                    ]
                    if starts:
                        latest = max(starts).isoformat()
                        if not state.get("latest_workout") or latest > state["latest_workout"]:
                            state["latest_workout"] = latest
                    state["pending_file"] = None
                    state["downloaded_bytes"] = payload_size
                    state["pending_file_count"] = len(
                        [item for item in filenames if item not in files]
                    )
                    # Persist each completed file boundary. A crash may repeat at
                    # most the active file, never the entire bounded batch.
                    await self._save()
                    self._publish(sensor_id)
                    batch_bytes += payload_size
                    del payload, result
                    if batch_bytes >= MAX_BYTES_PER_SYNC:
                        break

                stage = "import"
                await self._import_records_to_profiles(
                    sensor_id, records_to_import, profile_ids
                )

                remaining_downloads = [
                    item for item in filenames if item not in files
                ]
                pending_cached_import = any(
                    isinstance(record, dict)
                    and any(
                        profile_id
                        not in {
                            str(value)
                            for value in record.get("imported_profiles") or []
                        }
                        for profile_id in profile_ids
                    )
                    for record in files.values()
                )
                more_work = bool(remaining_downloads or pending_cached_import)

                state.update(
                    sync_state="waiting" if more_work else "ready",
                    last_error_code="none",
                    retry_count=0,
                    pending_file=None,
                    pending_file_count=len(remaining_downloads),
                )
                if not more_work:
                    state["last_successful_sync"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                await self._save()
                self._publish(sensor_id)
                if more_work:
                    self._schedule_after_current(
                        sensor_id, BATCH_CONTINUE_DELAY
                    )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            state = self._device(sensor_id)
            retries = int(state.get("retry_count") or 0) + 1
            pending = state.get("pending_file")
            if pending:
                file_failures = state.setdefault("file_failures", {})
                if not isinstance(file_failures, dict):
                    file_failures = state["file_failures"] = {}
                failure = file_failures.get(str(pending))
                if not isinstance(failure, dict):
                    failure = {}
                    file_failures[str(pending)] = failure
                failure.update(
                    attempts=int(failure.get("attempts") or 0) + 1,
                    last_attempt=datetime.now(timezone.utc).isoformat(),
                    last_error=str(err)[:240],
                )
            state.update(
                sync_state="error" if retries >= 6 else "retrying",
                last_error_code=ERROR_CODE_BY_STAGE.get(stage, "unknown"),
                retry_count=retries,
            )
            await self._save()
            self._publish(sensor_id)
            delay = min(15 * 60.0, 30.0 * (2 ** min(retries - 1, 5)))
            self._schedule_after_current(sensor_id, delay)
            _LOGGER.debug("CYCPLUS M1 workout sync failed for %s: %s", sensor_id, err)
        finally:
            if protocol is not None:
                await protocol.async_stop()
            if client is not None:
                await self.provider._async_disconnect_client(
                    client, reason="CYCPLUS M1 sync cleanup"
                )
            self.runtime._notify_values_throttled({
                (self.runtime.resolve_sensor_id(sensor_id), "gatt_connection", None)
            })

    async def async_shutdown(self) -> None:
        self._stopping = True
        tasks = list({*self._tasks.values(), *self._background_tasks})
        self._tasks.clear()
        self._background_tasks.clear()
        self._queued_after_task.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            try:
                async with asyncio.timeout(SHUTDOWN_TIMEOUT):
                    await asyncio.gather(*tasks, return_exceptions=True)
            except TimeoutError:
                _LOGGER.warning(
                    "Timed out waiting for CYCPLUS M1 synchronization shutdown"
                )
