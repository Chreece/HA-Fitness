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

CYCPLUS_CONNECT_TIMEOUT = 35.0


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


def cycplus_m1_serial_identity(serial_number: str | None) -> dict[str, str] | None:
    """Return the route identity encoded at the end of an M1 GATT serial.

    Current M1 firmware exposes a long Device Information serial whose final
    four hexadecimal characters are the same number advertised in ``M1_XXXX``.
    Requiring the documented ``M1`` prefix and a non-trivial serial length keeps
    this bridge specific to the CYCPLUS device family; callers must additionally
    verify the M1 vendor service before trusting it.
    """
    serial = str(serial_number or "").strip().upper()
    if len(serial) < 8 or not serial.startswith("M1"):
        return None
    number = serial[-4:]
    if re.fullmatch(r"[0-9A-F]{4}", number) is None:
        return None
    return {
        "cycplus_model_id": "M1",
        "cycplus_device_number": number,
        "fitness_physical_identity": f"cycplus:m1:{number.lower()}",
    }


def cycplus_m1_route_identity(
    name: str | None,
    serial_number: str | None = None,
    service_uuids: Iterable[str] = (),
) -> dict[str, str] | None:
    """Correlate an M1 route from the strongest facts that route exposes.

    A local HA scanner proves the device through the archive service. Web
    Bluetooth normally exposes only the selected fitness service plus Device
    Information, so its equivalent proof is the strict M1 name family together
    with the documented long ``M1...XXXX`` serial. A suffixed ``M1_XXXX`` name
    remains independently sufficient because the server derives that token.
    """
    name_identity = cycplus_m1_name_identity(name) or {}
    if name_identity.get("fitness_physical_identity"):
        return name_identity

    serial_identity = cycplus_m1_serial_identity(serial_number)
    services = {str(value).lower() for value in service_uuids}
    if serial_identity and (
        CYCPLUS_M1_SERVICE_UUID in services
        or name_identity.get("cycplus_model_id") == "M1"
    ):
        return {**name_identity, **serial_identity}
    return name_identity or None


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
        "fitness_vendor_identity": "cycplus",
        "archive_adapter": "cycplus_m1",
        "smart_device_default_type": "bike_computer",
        "archive_compatible": True,
        "model": "CYCPLUS M1 GPS Bike Computer",
        "model_id": "M1",
        "cycplus_protocol": "m1_ble_fit_archive_v1",
        **name_identity,
    }
    # Every local M1 discovery must wait for a verified Device Information
    # serial, even when the advertised name already contains the short per-unit
    # suffix.  A single physical M1 can leave multiple local BLE address routes
    # visible in HA's cache while rotating addresses. Runtime intentionally does
    # not merge two direct local-BLE routes from a short vendor token alone, so
    # allowing the suffixed name to unlock Discovery can expose two Add cards for
    # one bike computer. The adapter's bounded GATT probe supplies the full serial;
    # exact-serial canonicalization then collapses those routes before Discovery.
    result["archive_discovery_identity_required"] = "cycplus_gatt_identity_verified"
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


def _first_number(values: dict[str, Any], *keys: str) -> float | None:
    """Return the first usable numeric value across FIT aliases.

    fitdecode can expose duplicate FIT fields as a small list.  A list-valued
    enhanced field must not mask the scalar legacy alias that follows it (the
    M1 currently does this for enhanced_avg_speed/enhanced_max_speed).
    """
    for key in keys:
        value = values.get(key)
        candidates = value if isinstance(value, (list, tuple)) else (value,)
        for candidate in candidates:
            number = _number(candidate)
            if number is not None:
                return number
    return None


def _iso(value: Any) -> str | None:
    parsed = _dt(value)
    return parsed.isoformat() if parsed is not None else None


def _gps_points(records, limit: int = 256) -> list[list[float]]:
    """Return an evenly sampled, bounded FIT GPS track for the workout map."""
    points: list[list[float]] = []
    for record in records:
        lat = _degrees(record.get("position_lat"))
        lon = _degrees(record.get("position_long"))
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        point = [round(float(lat), 6), round(float(lon), 6)]
        if not points or point != points[-1]:
            points.append(point)
    if len(points) <= limit:
        return points
    last = len(points) - 1
    return [points[round(i * last / (limit - 1))] for i in range(limit)]


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
    laps = [values for name, values in messages if name == "lap"]
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
        duration = _first_number(session, "total_timer_time", "total_elapsed_time")
        moving = _first_number(
            session, "total_moving_time", "total_timer_time", "total_elapsed_time"
        )
        elapsed = _first_number(session, "total_elapsed_time")
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

        average_speed = _first_number(session, "enhanced_avg_speed", "avg_speed")
        maximum_speed = _first_number(session, "enhanced_max_speed", "max_speed")
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
            moving_time_s=moving,
            elapsed_time_s=elapsed,
            distance_m=_first_number(session, "total_distance"),
            avg_hr=_first_number(session, "avg_heart_rate")
            or _mean(item.get("heart_rate") for item in relevant),
            max_hr=_first_number(session, "max_heart_rate")
            or _maximum(item.get("heart_rate") for item in relevant),
            avg_power=_first_number(session, "avg_power")
            or _mean(item.get("power") for item in relevant),
            max_power=_first_number(session, "max_power")
            or _maximum(item.get("power") for item in relevant),
            weighted_power=_first_number(
                session, "normalized_power", "weighted_average_power"
            ),
            avg_cadence=_first_number(session, "avg_cadence")
            or _mean(item.get("cadence") for item in relevant),
            max_cadence=_first_number(session, "max_cadence")
            or _maximum(item.get("cadence") for item in relevant),
            elevation_gain_m=_first_number(session, "total_ascent"),
            elevation_loss_m=_first_number(session, "total_descent"),
            calories=_first_number(session, "total_calories"),
            aerobic_training_effect=_first_number(
                session, "total_training_effect", "aerobic_training_effect"
            ),
            anaerobic_training_effect=_first_number(
                session, "total_anaerobic_training_effect", "anaerobic_training_effect"
            ),
            training_load=_first_number(
                session, "training_stress_score", "training_load"
            ),
            average_speed_m_s=average_speed,
            max_speed_m_s=maximum_speed,
            kilojoules=(total_work / 1000.0) if total_work is not None else None,
            gps_track=_gps_points(relevant),
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
            "gps_track": _gps_points(relevant),
            "gps_points": _gps_points(relevant),
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


def _number_from_value(value: Any) -> float | None:
    """Read one scalar from a FIT value that may have duplicate-field values."""
    if isinstance(value, (list, tuple)):
        for item in value:
            number = _number(item)
            if number is not None:
                return number
        return None
    return _number(value)


def _mapping_number(values: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in values:
            continue
        number = _number_from_value(values.get(key))
        if number is not None:
            return number
    return None


def _stored_workout_provider(workout: dict[str, Any]) -> dict[str, Any]:
    provider_values = workout.get("provider_values")
    if isinstance(provider_values, dict):
        values = provider_values.get("cycplus_m1")
        if isinstance(values, dict):
            return values
    extra = workout.get("extra")
    if isinstance(extra, dict):
        values = extra.get("fit_session")
        if isinstance(values, dict):
            return values
    return {}


def _stored_workout_number(
    workout: dict[str, Any], field: str, *provider_keys: str
) -> float | None:
    number = _number_from_value(workout.get(field))
    if number is not None:
        return number
    return _mapping_number(_stored_workout_provider(workout), *provider_keys)


def _rounded(value: float | None, digits: int = 2) -> float | int | None:
    if value is None:
        return None
    rounded = round(float(value), digits)
    return int(rounded) if rounded.is_integer() else rounded


def _cycplus_workout_metrics(
    state: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Build truthful physical-device workout sensors from the cached FIT archive.

    The archive cache is the device-scoped source of truth.  Metrics absent from
    the latest ride are intentionally omitted, so a bike computer that recorded
    no HR/cadence/power does not manufacture permanently unavailable entities.
    Rolling totals use the retained M1 FIT sessions and therefore remain separate
    from profile-level merged history (Strava/Garmin/etc.).
    """
    files = state.get("files")
    if not isinstance(files, dict):
        return {}

    workouts: list[tuple[datetime, dict[str, Any]]] = []
    for record in files.values():
        if not isinstance(record, dict):
            continue
        items = record.get("workouts")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            started = _dt(item.get("start"))
            if started is None:
                continue
            workouts.append((started, item))
    if not workouts:
        return {}

    workouts.sort(key=lambda item: item[0])
    _latest_start, latest = workouts[-1]
    provider = _stored_workout_provider(latest)

    duration_s = _stored_workout_number(latest, "duration_s", "total_timer_time")
    moving_s = _stored_workout_number(
        latest, "moving_time_s", "total_moving_time", "total_timer_time"
    )
    elapsed_s = _stored_workout_number(latest, "elapsed_time_s", "total_elapsed_time")
    distance_m = _stored_workout_number(latest, "distance_m", "total_distance")
    avg_speed = _stored_workout_number(
        latest, "average_speed_m_s", "enhanced_avg_speed", "avg_speed"
    )
    max_speed = _stored_workout_number(
        latest, "max_speed_m_s", "enhanced_max_speed", "max_speed"
    )
    kilojoules = _number_from_value(latest.get("kilojoules"))
    if kilojoules is None:
        total_work_j = _mapping_number(provider, "total_work")
        if total_work_j is not None:
            kilojoules = total_work_j / 1000.0

    values: dict[str, Any] = {
        "cycplus_workout_duration": _rounded(duration_s / 60.0 if duration_s is not None else None),
        "cycplus_workout_moving_time": _rounded(moving_s / 60.0 if moving_s is not None else None),
        "cycplus_workout_elapsed_time": _rounded(elapsed_s / 60.0 if elapsed_s is not None else None),
        "cycplus_workout_distance": _rounded(distance_m / 1000.0 if distance_m is not None else None, 3),
        "cycplus_workout_average_speed": _rounded(avg_speed * 3.6 if avg_speed is not None else None),
        "cycplus_workout_max_speed": _rounded(max_speed * 3.6 if max_speed is not None else None),
        "cycplus_workout_avg_hr": _rounded(_stored_workout_number(latest, "avg_hr", "avg_heart_rate"), 1),
        "cycplus_workout_max_hr": _rounded(_stored_workout_number(latest, "max_hr", "max_heart_rate"), 1),
        "cycplus_workout_avg_power": _rounded(_stored_workout_number(latest, "avg_power", "avg_power"), 1),
        "cycplus_workout_max_power": _rounded(_stored_workout_number(latest, "max_power", "max_power"), 1),
        "cycplus_workout_weighted_power": _rounded(
            _stored_workout_number(
                latest, "weighted_power", "normalized_power", "weighted_average_power"
            ),
            1,
        ),
        "cycplus_workout_avg_cadence": _rounded(_stored_workout_number(latest, "avg_cadence", "avg_cadence"), 1),
        "cycplus_workout_max_cadence": _rounded(_stored_workout_number(latest, "max_cadence", "max_cadence"), 1),
        "cycplus_workout_elevation_gain": _rounded(
            _stored_workout_number(latest, "elevation_gain_m", "total_ascent"), 1
        ),
        "cycplus_workout_elevation_loss": _rounded(
            _stored_workout_number(latest, "elevation_loss_m", "total_descent"), 1
        ),
        "cycplus_workout_calories": _rounded(
            _stored_workout_number(latest, "calories", "total_calories"), 1
        ),
        "cycplus_workout_training_load": _rounded(
            _stored_workout_number(latest, "training_load", "training_stress_score", "training_load"),
            2,
        ),
        "cycplus_workout_aerobic_effect": _rounded(
            _stored_workout_number(
                latest, "aerobic_training_effect", "total_training_effect", "aerobic_training_effect"
            ),
            2,
        ),
        "cycplus_workout_anaerobic_effect": _rounded(
            _stored_workout_number(
                latest,
                "anaerobic_training_effect",
                "total_anaerobic_training_effect",
                "anaerobic_training_effect",
            ),
            2,
        ),
        "cycplus_workout_kilojoules": _rounded(kilojoules, 1),
        "cycplus_workout_avg_altitude": _rounded(
            _mapping_number(provider, "avg_altitude", "enhanced_avg_altitude"), 1
        ),
        "cycplus_workout_max_altitude": _rounded(
            _mapping_number(provider, "max_altitude", "enhanced_max_altitude"), 1
        ),
        "cycplus_workout_min_altitude": _rounded(
            _mapping_number(provider, "min_altitude", "enhanced_min_altitude"), 1
        ),
        "cycplus_workout_avg_temperature": _rounded(
            _mapping_number(provider, "avg_temperature"), 1
        ),
        "cycplus_workout_max_temperature": _rounded(
            _mapping_number(provider, "max_temperature"), 1
        ),
        "cycplus_workout_avg_positive_grade": _rounded(
            _mapping_number(provider, "avg_pos_grade"), 2
        ),
        "cycplus_workout_max_positive_grade": _rounded(
            _mapping_number(provider, "max_pos_grade"), 2
        ),
        "cycplus_workout_avg_negative_grade": _rounded(
            _mapping_number(provider, "avg_neg_grade"), 2
        ),
        "cycplus_workout_max_negative_grade": _rounded(
            _mapping_number(provider, "max_neg_grade"), 2
        ),
        "cycplus_history_workout_count": len(workouts),
    }

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    def _aggregate(cutoff: datetime | None = None) -> tuple[float, float, float]:
        total_distance = 0.0
        total_moving = 0.0
        total_ascent = 0.0
        for started, workout in workouts:
            if cutoff is not None and started < cutoff:
                continue
            distance = _stored_workout_number(workout, "distance_m", "total_distance")
            moving = _stored_workout_number(
                workout, "moving_time_s", "total_moving_time", "total_timer_time"
            )
            ascent = _stored_workout_number(workout, "elevation_gain_m", "total_ascent")
            if distance is not None:
                total_distance += distance
            if moving is not None:
                total_moving += moving
            if ascent is not None:
                total_ascent += ascent
        return total_distance, total_moving, total_ascent

    total_distance, total_moving, total_ascent = _aggregate()
    distance_7d, moving_7d, _ = _aggregate(reference - timedelta(days=7))
    distance_30d, moving_30d, _ = _aggregate(reference - timedelta(days=30))
    values.update({
        "cycplus_history_total_distance": _rounded(total_distance / 1000.0, 2),
        "cycplus_history_total_moving_time": _rounded(total_moving / 3600.0, 2),
        "cycplus_history_total_ascent": _rounded(total_ascent, 1),
        "cycplus_history_7d_distance": _rounded(distance_7d / 1000.0, 2),
        "cycplus_history_7d_moving_time": _rounded(moving_7d / 3600.0, 2),
        "cycplus_history_30d_distance": _rounded(distance_30d / 1000.0, 2),
        "cycplus_history_30d_moving_time": _rounded(moving_30d / 3600.0, 2),
    })
    return {key: value for key, value in values.items() if value is not None}


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

# The newest workout is user fitness information, not protocol diagnostics.
_DETAIL_META["cycplus_latest_workout"].pop("entity_category", None)

_WORKOUT_META: dict[str, dict[str, Any]] = {
    "cycplus_workout_duration": {
        "translation_key": "last_workout_duration", "icon": "mdi:timer-outline",
        "unit": "min", "device_class": "duration", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_moving_time": {
        "translation_key": "last_workout_moving_time", "icon": "mdi:timer-play-outline",
        "unit": "min", "device_class": "duration", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_elapsed_time": {
        "translation_key": "last_workout_elapsed_time", "icon": "mdi:timer-sand",
        "unit": "min", "device_class": "duration", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_distance": {
        "translation_key": "last_workout_distance", "icon": "mdi:map-marker-distance",
        "unit": "km", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_average_speed": {
        "translation_key": "last_workout_average_speed", "icon": "mdi:speedometer",
        "unit": "km/h", "device_class": "speed", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_max_speed": {
        "translation_key": "last_workout_max_speed", "icon": "mdi:speedometer",
        "unit": "km/h", "device_class": "speed", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_avg_hr": {
        "translation_key": "last_workout_avg_hr", "icon": "mdi:heart-pulse",
        "unit": "bpm", "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_max_hr": {
        "translation_key": "last_workout_max_hr", "icon": "mdi:heart-pulse",
        "unit": "bpm", "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_avg_power": {
        "translation_key": "last_workout_avg_power", "icon": "mdi:flash",
        "unit": "W", "device_class": "power", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_max_power": {
        "translation_key": "last_workout_max_power", "icon": "mdi:flash",
        "unit": "W", "device_class": "power", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_weighted_power": {
        "translation_key": "last_workout_weighted_power", "icon": "mdi:flash-outline",
        "unit": "W", "device_class": "power", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_avg_cadence": {
        "translation_key": "last_workout_avg_cadence", "icon": "mdi:rotate-right",
        "unit": "1/min", "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_max_cadence": {
        "translation_key": "last_workout_max_cadence", "icon": "mdi:rotate-right",
        "unit": "1/min", "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_elevation_gain": {
        "translation_key": "last_workout_elevation_gain", "icon": "mdi:elevation-rise",
        "unit": "m", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_elevation_loss": {
        "translation_key": "last_workout_elevation_loss", "icon": "mdi:elevation-decline",
        "unit": "m", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_calories": {
        "translation_key": "last_workout_calories", "icon": "mdi:fire",
        "unit": "kcal", "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_training_load": {
        "translation_key": "last_workout_training_load", "icon": "mdi:chart-bell-curve-cumulative",
        "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_aerobic_effect": {
        "translation_key": "last_workout_aerobic_effect", "icon": "mdi:lungs",
        "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_anaerobic_effect": {
        "translation_key": "last_workout_anaerobic_effect", "icon": "mdi:run-fast",
        "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_kilojoules": {
        "translation_key": "last_workout_kilojoules", "icon": "mdi:lightning-bolt",
        "unit": "kJ", "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_workout_avg_altitude": {
        "translation_key": "cycplus_workout_avg_altitude", "icon": "mdi:image-filter-hdr",
        "unit": "m", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_max_altitude": {
        "translation_key": "cycplus_workout_max_altitude", "icon": "mdi:image-filter-hdr",
        "unit": "m", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_min_altitude": {
        "translation_key": "cycplus_workout_min_altitude", "icon": "mdi:image-filter-hdr",
        "unit": "m", "device_class": "distance", "state_class": "measurement",
        "enabled_default": False,
    },
    "cycplus_workout_avg_temperature": {
        "translation_key": "cycplus_workout_avg_temperature", "icon": "mdi:thermometer",
        "unit": "°C", "device_class": "temperature", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_workout_max_temperature": {
        "translation_key": "cycplus_workout_max_temperature", "icon": "mdi:thermometer-high",
        "unit": "°C", "device_class": "temperature", "state_class": "measurement",
        "enabled_default": False,
    },
    "cycplus_workout_avg_positive_grade": {
        "translation_key": "cycplus_workout_avg_positive_grade", "icon": "mdi:slope-uphill",
        "unit": "%", "state_class": "measurement", "enabled_default": False,
    },
    "cycplus_workout_max_positive_grade": {
        "translation_key": "cycplus_workout_max_positive_grade", "icon": "mdi:slope-uphill",
        "unit": "%", "state_class": "measurement", "enabled_default": False,
    },
    "cycplus_workout_avg_negative_grade": {
        "translation_key": "cycplus_workout_avg_negative_grade", "icon": "mdi:slope-downhill",
        "unit": "%", "state_class": "measurement", "enabled_default": False,
    },
    "cycplus_workout_max_negative_grade": {
        "translation_key": "cycplus_workout_max_negative_grade", "icon": "mdi:slope-downhill",
        "unit": "%", "state_class": "measurement", "enabled_default": False,
    },
    "cycplus_history_workout_count": {
        "translation_key": "cycplus_history_workout_count", "icon": "mdi:bike-fast",
        "state_class": "measurement", "enabled_default": True,
    },
    "cycplus_history_total_distance": {
        "translation_key": "cycplus_history_total_distance", "icon": "mdi:map-marker-distance",
        "unit": "km", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_history_total_moving_time": {
        "translation_key": "cycplus_history_total_moving_time", "icon": "mdi:timer-outline",
        "unit": "h", "device_class": "duration", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_history_total_ascent": {
        "translation_key": "cycplus_history_total_ascent", "icon": "mdi:elevation-rise",
        "unit": "m", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_history_7d_distance": {
        "translation_key": "cycplus_history_7d_distance", "icon": "mdi:calendar-week",
        "unit": "km", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_history_7d_moving_time": {
        "translation_key": "cycplus_history_7d_moving_time", "icon": "mdi:calendar-week",
        "unit": "h", "device_class": "duration", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_history_30d_distance": {
        "translation_key": "cycplus_history_30d_distance", "icon": "mdi:calendar-month",
        "unit": "km", "device_class": "distance", "state_class": "measurement",
        "enabled_default": True,
    },
    "cycplus_history_30d_moving_time": {
        "translation_key": "cycplus_history_30d_moving_time", "icon": "mdi:calendar-month",
        "unit": "h", "device_class": "duration", "state_class": "measurement",
        "enabled_default": True,
    },
}


class CycplusM1Coordinator:
    """Own automatic, profile-aware and restart-safe M1 synchronization."""

    adapter_id = "cycplus_m1"
    sync_unique_suffix = "cycplus_sync_workouts"
    sync_translation_key = "sync_device_data"
    sync_icon = "mdi:calendar-sync"

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
        self._published_workout_metrics: dict[str, dict[str, Any]] = {}
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
                "catalog_filename", "device_attributes", "workout_metrics",
                "workout_metrics_date",
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
        # Builds which promoted FIT ``device_info`` into Bluetooth DeviceInfo
        # left the recording-source serial/revisions in the persisted live
        # endpoint. Clean those values even when every workout is already
        # downloaded, so migration does not depend on a future FIT transfer.
        for raw_sensor_id, state in tuple(
            self._state.get("devices", {}).items()
        ):
            attributes = (
                state.get("device_attributes")
                if isinstance(state, dict)
                else None
            )
            if isinstance(attributes, dict):
                self._apply_fit_device_attributes(raw_sensor_id, attributes)
        self._migrate_persisted_m1_route_identities()
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
        for state in self._state.get("devices", {}).values():
            if isinstance(state, dict):
                state["workout_metrics"] = _cycplus_workout_metrics(state)
                state["workout_metrics_date"] = datetime.now(timezone.utc).date().isoformat()
        await self._save()

    def _migrate_persisted_m1_route_identities(self) -> None:
        """Rebuild the exact M1 route bridge without waiting for rediscovery."""
        devices = self._state.get("devices", {})
        for restored in tuple(self.runtime.sensors.values()):
            sensor_id = self.runtime.resolve_sensor_id(restored.sensor_id)
            sensor = self.runtime.sensors.get(sensor_id)
            endpoint = (
                sensor.endpoints.get("bluetooth")
                if sensor is not None
                else None
            )
            if sensor is None or endpoint is None:
                continue
            metadata = dict(endpoint.metadata)
            services = {
                str(value).lower()
                for value in (
                    list(metadata.get("service_uuids") or [])
                    + list(metadata.get("gatt_services") or [])
                )
            }
            route_identity = cycplus_m1_route_identity(
                metadata.get("advertised_name") or sensor.name,
                metadata.get("serial_number"),
                services,
            ) or {}

            state = devices.get(restored.sensor_id)
            if not isinstance(state, dict):
                state = devices.get(sensor_id)
            attributes = (
                state.get("device_attributes")
                if isinstance(state, dict)
                else None
            )
            number = (
                str(attributes.get("device_number") or "").strip().upper()
                if isinstance(attributes, dict)
                else ""
            )
            if re.fullmatch(r"[0-9A-F]{4,16}", number):
                route_identity.update(
                    cycplus_m1_name_identity(f"M1_{number}") or {}
                )
            if not route_identity.get("fitness_physical_identity"):
                continue

            metadata.update({
                "manufacturer": "CYCPLUS",
                "model": "CYCPLUS M1 GPS Bike Computer",
                "model_id": "M1",
                "cycplus_protocol": "m1_ble_fit_archive_v1",
                **route_identity,
            })
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
            self._migrate_sensor_state(restored.sensor_id, merged.sensor_id)

        # Repair duplicate M1 installs created by older rotating-address discovery
        # before Home Assistant materializes/restores their registry surfaces.
        self._repair_persisted_duplicate_m1s()

        # This migration runs on the provider's control-plane setup task, after
        # the hub restored its HA device links. Materialize the canonical side
        # immediately and remove every now-resolvable discarded alias instead of
        # depending solely on the delayed radio-path cleanup callback.
        for sensor in tuple(self.runtime.sensors.values()):
            physical_identity = str(
                sensor.metadata.get("fitness_physical_identity")
                or next(
                    (
                        endpoint.metadata.get("fitness_physical_identity")
                        for endpoint in sensor.endpoints.values()
                        if endpoint.metadata.get("fitness_physical_identity")
                    ),
                    "",
                )
            ).lower()
            if (
                physical_identity.startswith("cycplus:m1:")
                and self.runtime.sensor_is_accepted(sensor.sensor_id)
            ):
                self.runtime.ensure_sensor_device(sensor.sensor_id)
        self.runtime._cleanup_persisted_sensor_alias_devices()

    @staticmethod
    def _sensor_gatt_serial(sensor) -> str | None:
        """Return a verified full M1 Device Information serial for one route."""
        values = [
            getattr(sensor, "metadata", {}).get("serial_number"),
            *(
                endpoint.metadata.get("serial_number")
                for endpoint in getattr(sensor, "endpoints", {}).values()
            ),
        ]
        for value in values:
            serial = str(value or "").strip().upper()
            if cycplus_m1_serial_identity(serial) is not None:
                return serial
        return None

    @staticmethod
    def _sensor_m1_physical_identity(sensor) -> str | None:
        """Return the exact M1 route identity already attached to a sensor."""
        values = [
            getattr(sensor, "metadata", {}).get("fitness_physical_identity"),
            *(
                endpoint.metadata.get("fitness_physical_identity")
                for endpoint in getattr(sensor, "endpoints", {}).values()
            ),
        ]
        identities = {
            str(value).strip().lower()
            for value in values
            if str(value or "").strip().lower().startswith("cycplus:m1:")
        }
        return next(iter(identities)) if len(identities) == 1 else None

    @staticmethod
    def _is_m1_sensor(sensor) -> bool:
        endpoint = getattr(sensor, "endpoints", {}).get("bluetooth")
        metadata = endpoint.metadata if endpoint is not None else {}
        return bool(
            str(metadata.get("archive_adapter") or "") == "cycplus_m1"
            or str(getattr(sensor, "metadata", {}).get("archive_adapter") or "")
            == "cycplus_m1"
        )

    def _state_for_existing_sensor(self, sensor_id: str) -> dict[str, Any] | None:
        state = self._state.get("devices", {}).get(str(sensor_id))
        return state if isinstance(state, dict) else None

    def _legacy_archive_duplicate(self, a_id: str, b_id: str) -> bool:
        """Use M1-owned archive evidence to recognize old duplicate installs.

        Older builds could install one rotating-address M1 more than once before
        the GATT serial was known.  Equal model names are deliberately *not*
        enough to merge.  A shared device number plus at least one identical FIT
        filename is adapter-owned evidence that both records came from the same
        physical archive.
        """
        a = self._state_for_existing_sensor(a_id)
        b = self._state_for_existing_sensor(b_id)
        if not a or not b:
            return False
        a_attrs = a.get("device_attributes") if isinstance(a.get("device_attributes"), dict) else {}
        b_attrs = b.get("device_attributes") if isinstance(b.get("device_attributes"), dict) else {}
        a_number = str(a_attrs.get("device_number") or "").strip().upper()
        b_number = str(b_attrs.get("device_number") or "").strip().upper()
        if (
            not a_number
            or a_number != b_number
            or re.fullmatch(r"[0-9A-F]{4,16}", a_number) is None
        ):
            return False
        a_files = set((a.get("files") or {}).keys()) if isinstance(a.get("files"), dict) else set()
        b_files = set((b.get("files") or {}).keys()) if isinstance(b.get("files"), dict) else set()
        return bool(a_files & b_files)

    def _accepted_registry_serial_owner_id(self, serial: str) -> str | None:
        """Return the installed Fitness sensor ID owning this exact M1 serial.

        The Device Registry is the durable source of truth for an already-added
        physical device.  Older Fitness builds can lose the matching live-runtime
        topology while the HA device, profile assignment and entities continue to
        exist.  Recovery therefore must *not* require that the registry owner's
        ``live_sensor:<id>`` is already present in ``runtime.sensors``; that was the
        hole which let the same M1 reopen Discovery after restart.

        This lookup is intentionally strict: the current route has already proved
        the full M1 GATT serial and vendor service, and exactly one Fitness Devices
        registry row must carry that same full serial plus an M1 model identity.
        """
        devices_entry = getattr(self.runtime, "devices_entry", None)
        if devices_entry is None:
            return None

        from homeassistant.helpers import device_registry as dr

        wanted = str(serial or "").strip().upper()
        if cycplus_m1_serial_identity(wanted) is None:
            return None

        registry = dr.async_get(self.hass)
        matches: set[str] = set()
        for device in tuple(registry.devices.values()):
            if devices_entry.entry_id not in set(
                getattr(device, "config_entries", set())
            ):
                continue
            if (
                str(getattr(device, "serial_number", None) or "")
                .strip()
                .upper()
                != wanted
            ):
                continue

            model_id = str(getattr(device, "model_id", None) or "").strip().upper()
            model = str(getattr(device, "model", None) or "").strip().upper()
            if model_id != "M1" and "CYCPLUS M1" not in model:
                continue

            for domain, identifier in set(getattr(device, "identifiers", set())):
                identifier = str(identifier)
                if domain != DOMAIN or not identifier.startswith("live_sensor:sensor:"):
                    continue
                matches.add(identifier.removeprefix("live_sensor:"))

        if len(matches) != 1:
            return None
        return next(iter(matches))

    def canonicalize_connected_sensor(self, sensor_id: str) -> str:
        """Collapse rotating-address M1 aliases after one verified GATT identity.

        The generic runtime intentionally refuses to merge two local BLE devices
        from a short vendor number alone.  M1 can do better: once one route has a
        verified full GATT serial, exact-serial duplicates are indisputably the
        same unit.  Legacy accepted routes carrying only the matching M1 physical
        token are also absorbed when they are currently unavailable, which is the
        characteristic rotating-address restart case rather than two concurrently
        observed bike computers.
        """
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        current = self.runtime.sensors.get(sensor_id)
        if current is None or not self._is_m1_sensor(current):
            return sensor_id
        serial = self._sensor_gatt_serial(current)
        if serial is None:
            return sensor_id
        # Full Device Information serial is already the strongest M1 identity we
        # have.  Older accepted records may predate fitness_physical_identity even
        # though they persisted the same verified GATT serial.  Derive the route
        # token from that serial instead of refusing to repair those legacy rows.
        serial_identity = cycplus_m1_serial_identity(serial) or {}
        physical = (
            self._sensor_m1_physical_identity(current)
            or str(serial_identity.get("fitness_physical_identity") or "").lower()
            or None
        )
        if physical:
            current.metadata.setdefault("fitness_physical_identity", physical)
            current.metadata.setdefault(
                "cycplus_device_number", serial_identity.get("cycplus_device_number")
            )
        # Keep the endpoint from the connection that just proved the identity.
        # Generic same-transport merging intentionally prefers an existing local
        # endpoint, but an M1 rotating its address needs the opposite: the newly
        # connected route is the only address we know is usable right now.
        connected_endpoint = current.endpoints.get("bluetooth")

        candidates = []
        for candidate in tuple(self.runtime.sensors.values()):
            candidate_id = self.runtime.resolve_sensor_id(candidate.sensor_id)
            if candidate_id == sensor_id or candidate_id not in self.runtime.sensors:
                continue
            candidate = self.runtime.sensors[candidate_id]
            if not self._is_m1_sensor(candidate):
                continue
            candidate_serial = self._sensor_gatt_serial(candidate)
            candidate_physical = self._sensor_m1_physical_identity(candidate)
            exact_serial = bool(candidate_serial and candidate_serial == serial)
            stale_same_route = bool(
                candidate_serial is None
                and physical is not None
                and candidate_physical == physical
                and not candidate.available
            )
            if exact_serial or stale_same_route:
                # Backfill the stable route token on exact-serial legacy records so
                # registry materialization after the merge is canonical too.
                if exact_serial and physical:
                    candidate.metadata.setdefault("fitness_physical_identity", physical)
                    candidate.metadata.setdefault(
                        "cycplus_device_number",
                        serial_identity.get("cycplus_device_number"),
                    )
                candidates.append(candidate)

        # Legacy recovery: HA may still have the installed M1 device and profile
        # assignment even when Fitness's private live-topology store no longer has
        # the corresponding runtime object.  The previous repair tried to use the
        # Device Registry but then required that registry owner to already exist in
        # runtime.sensors, which made the fallback useless in exactly this restart
        # failure mode.
        #
        # Recreate a tiny accepted canonical witness under the durable installed
        # sensor ID, then let the normal merge transaction move this freshly proved
        # Bluetooth endpoint onto it.  This preserves all existing HA entity unique
        # IDs/profile references and aborts any discovery flow opened for the new
        # provisional ID.
        registry_owner_id = self._accepted_registry_serial_owner_id(serial)
        if registry_owner_id is not None and registry_owner_id != sensor_id:
            owner_id = self.runtime.resolve_sensor_id(registry_owner_id)
            registry_owner = self.runtime.sensors.get(owner_id)
            if registry_owner is None:
                registry_owner = type(current)(
                    sensor_id=registry_owner_id,
                    name=current.name,
                    capabilities=set(),
                    metadata={
                        "accepted": True,
                        "manufacturer": "CYCPLUS",
                        "model": "CYCPLUS M1 GPS Bike Computer",
                        "model_id": "M1",
                        "serial_number": serial,
                        "fitness_vendor_identity": "cycplus",
                        "archive_adapter": "cycplus_m1",
                        "fitness_serial_identity_verified": True,
                        "cycplus_gatt_identity_verified": True,
                        **(
                            {
                                "fitness_physical_identity": physical,
                                "cycplus_device_number": serial_identity.get(
                                    "cycplus_device_number"
                                ),
                            }
                            if physical
                            else {}
                        ),
                    },
                )
                self.runtime.sensors[registry_owner_id] = registry_owner

            if all(
                item.sensor_id != registry_owner.sensor_id
                for item in candidates
            ):
                candidates.append(registry_owner)

        canonical = current
        for duplicate in candidates:
            if duplicate.sensor_id not in self.runtime.sensors:
                continue
            left_id = canonical.sensor_id
            right_id = duplicate.sensor_id
            canonical = self.runtime._merge_physical_sensors(canonical, duplicate)
            for old_id in {left_id, right_id}:
                if old_id != canonical.sensor_id:
                    self._migrate_sensor_state(old_id, canonical.sensor_id)
        if candidates:
            if connected_endpoint is not None:
                canonical.endpoints["bluetooth"] = connected_endpoint
                self.runtime.endpoint_aliases[connected_endpoint.endpoint_id] = (
                    canonical.sensor_id
                )
                canonical.metadata.setdefault("transport_details", {})["bluetooth"] = {
                    "endpoint_id": connected_endpoint.endpoint_id,
                    "address": connected_endpoint.address,
                    **dict(connected_endpoint.metadata),
                }
            canonical.metadata["merge_evidence"] = "cycplus_m1_gatt_serial"
            self.runtime._schedule_save()
        return canonical.sensor_id

    def _repair_persisted_duplicate_m1s(self) -> None:
        """Collapse old M1 duplicate installs from exact adapter-owned evidence."""
        sensors = [
            sensor
            for sensor in tuple(self.runtime.sensors.values())
            if sensor.sensor_id in self.runtime.sensors and self._is_m1_sensor(sensor)
        ]
        for sensor in sensors:
            if sensor.sensor_id not in self.runtime.sensors:
                continue
            canonical_id = self.canonicalize_connected_sensor(sensor.sensor_id)
            canonical = self.runtime.sensors.get(self.runtime.resolve_sensor_id(canonical_id))
            if canonical is None:
                continue
            for duplicate in tuple(self.runtime.sensors.values()):
                if duplicate.sensor_id == canonical.sensor_id or not self._is_m1_sensor(duplicate):
                    continue
                if not self._legacy_archive_duplicate(canonical.sensor_id, duplicate.sensor_id):
                    continue
                left_id = canonical.sensor_id
                right_id = duplicate.sensor_id
                canonical = self.runtime._merge_physical_sensors(canonical, duplicate)
                for old_id in {left_id, right_id}:
                    if old_id != canonical.sensor_id:
                        self._migrate_sensor_state(old_id, canonical.sensor_id)
                canonical.metadata["merge_evidence"] = "cycplus_m1_archive_identity"

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
                merged["workout_metrics"] = _cycplus_workout_metrics(merged)
                merged["workout_metrics_date"] = datetime.now(timezone.utc).date().isoformat()
                devices[new_id] = merged
            else:
                devices[new_id] = old
                if isinstance(old, dict):
                    old["workout_metrics"] = _cycplus_workout_metrics(old)
                    old["workout_metrics_date"] = datetime.now(timezone.utc).date().isoformat()

        task = self._tasks.pop(old_id, None)
        if task is not None and not task.done():
            self._tasks.setdefault(new_id, task)
        queued = self._queued_after_task.pop(old_id, None)
        if queued is not None:
            self._queued_after_task[new_id] = queued
        progress = self._progress_publish.pop(old_id, None)
        if progress is not None:
            self._progress_publish[new_id] = progress
        self._published_workout_metrics.pop(old_id, None)
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

    async def async_clear_fit_cache(self, retain_count: int = 30, *, profile_id: str | None = None, ownership: str = "profile") -> int:
        """Prune only Fitness-owned cache records allowed by the requested ownership scope."""
        retain_count = max(0, min(int(retain_count), 500))
        removed = 0
        for state in self._state.setdefault("devices", {}).values():
            files = state.get("files") if isinstance(state, dict) else None
            if not isinstance(files, dict):
                continue
            eligible = [
                (key, record) for key, record in files.items()
                if isinstance(record, dict)
                and (
                    ownership == "all_fitness_owned"
                    or (
                        profile_id is not None
                        and profile_id in {str(value) for value in record.get("imported_profiles") or []}
                    )
                )
            ]
            if len(eligible) <= retain_count:
                continue
            ordered = sorted(
                eligible,
                key=lambda item: str((item[1] or {}).get("completed_at") or item[0]),
                reverse=True,
            )
            keep = {key for key, _value in ordered[:retain_count]}
            eligible_keys = {key for key, _record in eligible}
            for key in list(files):
                if key in eligible_keys and key not in keep:
                    files.pop(key, None)
                    removed += 1
            state["workout_metrics"] = _cycplus_workout_metrics(state)
            state["workout_metrics_date"] = datetime.now(timezone.utc).date().isoformat()
        if removed:
            await self._save()
        return removed

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
        if not self.runtime.sensor_archive_profile_ids(sensor_id):
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
        self._published_workout_metrics.pop(sensor_id, None)
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
        today = datetime.now(timezone.utc).date().isoformat()
        workout_metrics = state.get("workout_metrics")
        if (
            not isinstance(workout_metrics, dict)
            or state.get("workout_metrics_date") != today
        ):
            workout_metrics = _cycplus_workout_metrics(state)
            state["workout_metrics"] = workout_metrics
            state["workout_metrics_date"] = today
        previous_metrics = self._published_workout_metrics.get(sensor_id)
        if previous_metrics != workout_metrics:
            self.runtime.clear_sensor_details_prefix(sensor_id, "cycplus_workout_")
            self.runtime.clear_sensor_details_prefix(sensor_id, "cycplus_history_")
            if workout_metrics:
                self.runtime.publish_details(
                    sensor_id,
                    workout_metrics,
                    transport="cycplus_m1_archive",
                    metadata=_WORKOUT_META,
                    priority=90,
                )
            self._published_workout_metrics[sensor_id] = dict(workout_metrics)

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
        profile_ids = self.runtime.sensor_archive_profile_ids(sensor_id)
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

        remote_client = self.provider.remote_gatt_client(sensor_id)
        ble_device = None
        if remote_client is None:
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
                async with asyncio.timeout(CYCPLUS_CONNECT_TIMEOUT):
                    if remote_client is not None:
                        client = remote_client
                        await client.connect()
                    else:
                        client = await self.provider.establish_connection(
                            ble_device, sensor.name or endpoint.address, max_attempts=2
                        )
                previous_id = sensor_id
                if remote_client is None:
                    sensor = await self.provider._async_enrich_identity(
                        sensor, endpoint, client, manage_client_state=False
                    )
                    sensor_id = self._migrate_sensor_state(previous_id, sensor.sensor_id)
                else:
                    # Remote registration already performed DIS/service
                    # verification in the browser and canonicalized that metadata
                    # before the archive worker was scheduled.
                    sensor_id = self._migrate_sensor_state(
                        previous_id,
                        self.runtime.resolve_sensor_id(
                            self.runtime.sensors.get(previous_id, sensor).sensor_id
                        ),
                    )
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
                    if not self.runtime.sensor_archive_profile_ids(sensor_id):
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
                    state["workout_metrics"] = _cycplus_workout_metrics(state)
                    state["workout_metrics_date"] = datetime.now(timezone.utc).date().isoformat()
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
        self._published_workout_metrics.clear()
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

