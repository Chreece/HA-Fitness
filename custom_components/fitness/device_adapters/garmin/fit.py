"""Bounded Garmin FIT normalization for local workout imports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import io
import math
from typing import Any

from ...providers.workouts import Workout, _dt

MAX_FIT_BYTES = 32 * 1024 * 1024
MAX_FIT_RECORDS = 150_000
MAX_FIT_METADATA_FRAMES = 8_192
MAX_SET_MESSAGES = 4_096
MAX_VENDOR_FIELDS_PER_MESSAGE = 64

_RECORD_FIELDS = frozenset({
    "timestamp", "position_lat", "position_long", "enhanced_speed", "speed",
    "heart_rate", "power", "cadence", "distance",
})
_RETAINED = frozenset({"session", "record", "lap", "file_id", "device_info", "set", "activity", "sport"})


def _safe(value: Any, *, depth: int = 0) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value[:512].hex()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value[:1024] if isinstance(value, str) else value
    if depth >= 4:
        return f"<garmin-depth-limit:{type(value).__name__}>"
    if isinstance(value, (list, tuple)):
        return [_safe(item, depth=depth + 1) for item in value[:64]]
    if isinstance(value, dict):
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_VENDOR_FIELDS_PER_MESSAGE:
                break
            result[str(key)[:128]] = _safe(item, depth=depth + 1)
        return result
    return str(value)[:512]


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _first(values: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = values.get(key)
        if value not in (None, ""):
            return value
    return None


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


def _mean(values) -> float | None:
    numbers = [number for value in values if (number := _number(value)) is not None]
    return sum(numbers) / len(numbers) if numbers else None


def _maximum(values) -> float | None:
    numbers = [number for value in values if (number := _number(value)) is not None]
    return max(numbers) if numbers else None


def _fit_container(data: bytes) -> bytes:
    data = bytes(data)
    if len(data) < 14 or len(data) > MAX_FIT_BYTES:
        raise ValueError("FIT container size is outside safe bounds")
    header_size = data[0]
    if header_size not in {12, 14} or len(data) < header_size + 2:
        raise ValueError("invalid FIT header")
    if data[8:12] != b".FIT":
        raise ValueError("missing FIT signature")
    payload_size = int.from_bytes(data[4:8], "little")
    total = header_size + payload_size + 2
    if total > len(data) or total > MAX_FIT_BYTES:
        raise ValueError("FIT container length is invalid")
    return data[:total]


def decode_fit(data: bytes) -> list[tuple[str, dict[str, Any]]]:
    """Decode only bounded fields needed for canonical workout normalization."""
    container = _fit_container(data)
    import fitdecode

    messages: list[tuple[str, dict[str, Any]]] = []
    record_count = 0
    metadata_count = 0
    set_count = 0
    with fitdecode.FitReader(io.BytesIO(container), check_crc=fitdecode.CrcCheck.RAISE) as reader:
        for frame in reader:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            name = str(frame.name)
            if name not in _RETAINED:
                continue
            if name == "record":
                record_count += 1
                if record_count > MAX_FIT_RECORDS:
                    raise ValueError("FIT record count exceeds safe limit")
            else:
                metadata_count += 1
                if metadata_count > MAX_FIT_METADATA_FRAMES:
                    raise ValueError("FIT metadata count exceeds safe limit")
            if name == "set":
                set_count += 1
                if set_count > MAX_SET_MESSAGES:
                    raise ValueError("FIT strength set count exceeds safe limit")

            values: dict[str, Any] = {}
            vendor_count = 0
            for field in frame.fields:
                field_name = str(field.name)
                if name == "record" and field_name not in _RECORD_FIELDS:
                    continue
                if field_name.startswith("unknown_") or field_name.isdigit():
                    vendor_count += 1
                    if vendor_count > MAX_VENDOR_FIELDS_PER_MESSAGE:
                        continue
                value = _safe(field.value)
                if value is None:
                    continue
                if field_name in values:
                    old = values[field_name]
                    values[field_name] = [*old, value] if isinstance(old, list) else [old, value]
                else:
                    values[field_name] = value
            messages.append((name, values))
    return messages


def _reported_reps_plausible(reps: Any, duration: Any) -> bool | None:
    if reps is None:
        return None
    numeric = _number(reps)
    if numeric is None or numeric < 0:
        return False
    if numeric == 0:
        return True
    seconds = _number(duration)
    if seconds and seconds > 0 and numeric / seconds > 10:
        return False
    return True


def _normalize_sets(sets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float, float, bool]:
    normalized: list[dict[str, Any]] = []
    active_duration = 0.0
    rest_duration = 0.0
    all_reps_plausible = True
    known = {
        "duration", "repetitions", "weight", "set_type", "start_time", "timestamp",
        "category", "category_subtype", "weight_display_unit", "message_index", "wkt_step_index",
    }
    for sequence, item in enumerate(sets[:MAX_SET_MESSAGES], 1):
        set_type = str(item.get("set_type") or "unknown")
        duration = _number(item.get("duration"))
        reps = item.get("repetitions")
        plausible = _reported_reps_plausible(reps, duration)
        if plausible is False:
            all_reps_plausible = False
        categories = item.get("category")
        if not isinstance(categories, list):
            categories = [categories] if categories is not None else []
        categories = [value for value in categories if value not in (None, "unknown")]
        vendor = {
            str(key): _safe(value)
            for key, value in item.items()
            if key not in known
        }
        normalized.append({
            "sequence": sequence,
            "type": set_type,
            "start_time": _iso(item.get("start_time")),
            "duration_s": duration,
            "repetitions_reported": _safe(reps),
            "repetitions_plausible": plausible,
            "weight_kg_reported": _number(item.get("weight")),
            "exercise_categories": [_safe(value) for value in categories[:16]],
            "message_index": _safe(item.get("message_index")),
            "workout_step_index": _safe(item.get("wkt_step_index")),
            "vendor_fields": vendor,
        })
        if duration is not None:
            if set_type == "active":
                active_duration += duration
            elif set_type == "rest":
                rest_duration += duration
    return normalized, active_duration, rest_duration, all_reps_plausible


def workout_from_fit(
    data: bytes,
    *,
    sensor_id: str,
    source_key: str,
    source_label: str | None = None,
) -> Workout:
    """Normalize the first completed Garmin activity session to Workout."""
    container = _fit_container(data)
    digest = hashlib.sha256(container).hexdigest()
    messages = decode_fit(container)
    sessions = [values for name, values in messages if name == "session"]
    if not sessions:
        raise ValueError("Garmin FIT contains no completed session")
    session = sessions[0]
    records = [values for name, values in messages if name == "record"]
    sets = [values for name, values in messages if name == "set"]
    file_ids = [values for name, values in messages if name == "file_id"]
    device_info = [values for name, values in messages if name == "device_info"]
    file_id = file_ids[0] if file_ids else {}
    device = device_info[0] if device_info else {}

    start_dt = _dt(_first(session, "start_time")) or _dt(_first(file_id, "time_created"))
    if start_dt is None:
        raise ValueError("Garmin FIT has no usable start time")
    duration = _number(_first(session, "total_timer_time", "total_elapsed_time"))
    elapsed = _number(_first(session, "total_elapsed_time", "total_timer_time"))
    reported_end = _dt(_first(session, "timestamp", "end_time"))
    end_dt = reported_end
    if duration is not None and (end_dt is None or end_dt <= start_dt):
        end_dt = start_dt + timedelta(seconds=max(0.0, elapsed if elapsed is not None else duration))

    relevant = []
    for record in records:
        timestamp = _dt(record.get("timestamp"))
        if timestamp is None:
            continue
        if timestamp < start_dt or (end_dt is not None and timestamp > end_dt + timedelta(seconds=1)):
            continue
        relevant.append(record)

    first_position = next((r for r in relevant if r.get("position_lat") is not None and r.get("position_long") is not None), {})
    avg_speed = _number(_first(session, "enhanced_avg_speed", "avg_speed"))
    max_speed = _number(_first(session, "enhanced_max_speed", "max_speed"))
    if avg_speed is None:
        avg_speed = _mean(_first(item, "enhanced_speed", "speed") for item in relevant)
    if max_speed is None:
        max_speed = _maximum(_first(item, "enhanced_speed", "speed") for item in relevant)

    normalized_sets, active_duration, rest_duration, reps_plausible = _normalize_sets(sets)
    reported_total_reps = _number(session.get("total_reps"))
    trusted_reps = reported_total_reps if (not sets or reps_plausible) else None
    weights = [
        item.get("weight_kg_reported") for item in normalized_sets
        if item.get("type") == "active" and item.get("weight_kg_reported") is not None
        and item.get("repetitions_plausible") is not False
    ]
    reps = [
        _number(item.get("repetitions_reported")) for item in normalized_sets
        if item.get("type") == "active" and item.get("repetitions_plausible") is True
    ]
    volume = 0.0
    has_volume = False
    for item in normalized_sets:
        if item.get("type") != "active" or item.get("repetitions_plausible") is not True:
            continue
        r = _number(item.get("repetitions_reported"))
        w = _number(item.get("weight_kg_reported"))
        if r is not None and w is not None:
            volume += r * w
            has_volume = True

    product = _first(file_id, "garmin_product", "product_name", "product") or _first(device, "product_name", "descriptor", "product")
    serial = _first(file_id, "serial_number") or _first(device, "serial_number")
    source = f"garmin_local:{sensor_id}:{source_key}"
    summary = {key: _safe(value) for key, value in session.items() if value not in (None, "")}
    workout = Workout(
        source=source,
        name=str(_first(session, "sport_profile_name") or "") or None,
        sport=str(_first(session, "sub_sport", "sport") or "workout"),
        start=start_dt.isoformat(),
        end=end_dt.isoformat() if end_dt is not None else None,
        duration_s=duration,
        moving_time_s=_number(_first(session, "active_time")) or duration,
        elapsed_time_s=elapsed,
        distance_m=_number(session.get("total_distance")),
        avg_hr=_number(session.get("avg_heart_rate")) or _mean(item.get("heart_rate") for item in relevant),
        max_hr=_number(session.get("max_heart_rate")) or _maximum(item.get("heart_rate") for item in relevant),
        avg_power=_number(session.get("avg_power")) or _mean(item.get("power") for item in relevant),
        max_power=_number(session.get("max_power")) or _maximum(item.get("power") for item in relevant),
        weighted_power=_number(_first(session, "normalized_power", "weighted_average_power")),
        avg_cadence=_number(session.get("avg_cadence")) or _mean(item.get("cadence") for item in relevant),
        max_cadence=_number(session.get("max_cadence")) or _maximum(item.get("cadence") for item in relevant),
        elevation_gain_m=_number(session.get("total_ascent")),
        elevation_loss_m=_number(session.get("total_descent")),
        calories=_number(session.get("total_calories")),
        aerobic_training_effect=_number(_first(session, "total_training_effect", "aerobic_training_effect")),
        anaerobic_training_effect=_number(_first(session, "total_anaerobic_training_effect", "anaerobic_training_effect")),
        training_load=_number(_first(session, "training_load_peak", "training_stress_score", "training_load")),
        average_speed_m_s=avg_speed,
        max_speed_m_s=max_speed,
        total_reps=trusted_reps,
        strength_total_sets=float(sum(1 for item in normalized_sets if item.get("type") == "active")) if sets else None,
        volume_kg=volume if has_volume else None,
        exercise_count=float(len({tuple(item.get("exercise_categories") or []) for item in normalized_sets if item.get("exercise_categories")})) if sets else None,
        start_latitude=_degrees(first_position.get("position_lat")),
        start_longitude=_degrees(first_position.get("position_long")),
        device_name=str(source_label or product or "Garmin"),
        sample_count=len(relevant),
        sources=[source],
        provider_domains=["garmin_local"],
        extra={
            "fitness_adapter": "garmin_local",
            "fitness_history_source": "garmin_local_ble_fit",
            "source_file_sha256": digest,
            "garmin_source_key": source_key,
            "garmin_product": _safe(product),
            "garmin_serial_number": _safe(serial),
            "fit_sport": _safe(session.get("sport")),
            "fit_sub_sport": _safe(session.get("sub_sport")),
            "sport_profile_name": _safe(session.get("sport_profile_name")),
            "garmin_reported_end_time": reported_end.isoformat() if reported_end else None,
            "garmin_end_time_derived": bool(end_dt is not None and reported_end != end_dt),
            "garmin_reported_repetitions": _safe(session.get("total_reps")),
            "garmin_repetitions_plausible": reps_plausible,
            "garmin_reported_segment_count": _safe(session.get("num_laps")),
            "strength_segments": normalized_sets,
            "strength_active_duration_s": active_duration,
            "strength_rest_duration_s": rest_duration,
            "fit_record_count": len(relevant),
            "fit_session": summary,
        },
    )
    factual = (
        "name", "sport", "start", "end", "duration_s", "moving_time_s", "elapsed_time_s",
        "distance_m", "avg_hr", "max_hr", "avg_power", "max_power", "weighted_power",
        "avg_cadence", "max_cadence", "elevation_gain_m", "elevation_loss_m", "calories",
        "aerobic_training_effect", "anaerobic_training_effect", "training_load", "average_speed_m_s",
        "max_speed_m_s", "total_reps", "strength_total_sets", "volume_kg", "exercise_count",
        "start_latitude", "start_longitude", "device_name", "sample_count",
    )
    workout.field_sources = {key: "garmin_local" for key in factual if getattr(workout, key) is not None}
    workout.provider_values = {"garmin_local": summary}
    return workout
