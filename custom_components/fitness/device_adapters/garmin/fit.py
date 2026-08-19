"""Bounded Garmin FIT normalization for local workout imports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import io
import math
from typing import Any

from ...providers.workouts import Workout, _dt
from ...providers.sleep import SleepRecord
from ..history import DeviceHistoryBatch, DeviceMetricPoint

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



HEALTH_MESSAGE_NAMES = frozenset({
    "monitoring", "monitoring_info", "monitoring_hr_data", "resting_heart_rate",
    "hr", "hrv", "beat_intervals", "hrv_status_summary", "hrv_value", "stress_level",
    "respiration_rate", "spo2_data", "sleep_level", "sleep_assessment",
    "weight_scale", "blood_pressure", "hsa_step_data", "hsa_spo2_data",
    "hsa_stress_data", "hsa_respiration_data", "hsa_heart_rate_data",
    "hsa_body_battery_data", "skin_temp_overnight", "hsa_wrist_temperature_data",
    "device_aux_battery_info", "max_met_data",
})
MAX_HEALTH_FRAMES = 100_000


def _health_frames(data: bytes) -> list[tuple[str, dict[str, Any]]]:
    """Decode only documented/recognized wellness messages under hard bounds."""
    container = _fit_container(data)
    import fitdecode

    result: list[tuple[str, dict[str, Any]]] = []
    count = 0
    with fitdecode.FitReader(io.BytesIO(container), check_crc=fitdecode.CrcCheck.RAISE) as reader:
        for frame in reader:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            name = str(frame.name)
            if name not in HEALTH_MESSAGE_NAMES:
                continue
            count += 1
            if count > MAX_HEALTH_FRAMES:
                raise ValueError("Garmin wellness FIT frame count exceeds safe limit")
            values: dict[str, Any] = {}
            for field in frame.fields:
                field_name = str(field.name)
                if field_name.startswith("unknown_") or field_name.isdigit():
                    continue
                value = _safe(field.value)
                if value is None:
                    continue
                if field_name in values:
                    old = values[field_name]
                    values[field_name] = [*old, value] if isinstance(old, list) else [old, value]
                else:
                    values[field_name] = value
            if values:
                result.append((name, values))
    return result


def _point_time(values: dict[str, Any]) -> datetime | None:
    for key in (
        "timestamp", "stress_level_time", "local_timestamp", "start_time",
        "measurement_time", "sample_time", "time_created", "update_time",
    ):
        parsed = _dt(values.get(key))
        if parsed is not None:
            return parsed
    return None


def _scalar(value: Any, *, mean_list: bool = False) -> float | None:
    if isinstance(value, (list, tuple)):
        numbers = [number for item in value if (number := _number(item)) is not None]
        if not numbers:
            return None
        return sum(numbers) / len(numbers) if mean_list else numbers[-1]
    return _number(value)


def _scaled_percent(value: Any) -> float | None:
    number = _scalar(value)
    if number is None:
        return None
    while number > 100.0 and number <= 10000.0:
        number /= 100.0
    return number


def _scaled_respiration(value: Any) -> float | None:
    number = _scalar(value)
    if number is None:
        return None
    # Older Garmin monitoring files encode hundredths of breaths/min while FIT
    # decoders based on newer profiles may already apply the scale.
    if 100.0 < number <= 10000.0:
        number /= 100.0
    return number


def _sleep_stage(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace(" ", "_")
    if "rem" in text:
        return "rem"
    if "deep" in text:
        return "deep"
    if "light" in text:
        return "light"
    if "awake" in text or "wake" in text:
        return "awake"
    return None


def _sleep_records_from_frames(
    frames: list[tuple[str, dict[str, Any]]], *, source: str
) -> list[SleepRecord]:
    events: list[tuple[datetime, str]] = []
    assessments: list[tuple[datetime | None, dict[str, Any]]] = []
    for name, values in frames:
        if name == "sleep_level":
            stamp = _point_time(values)
            stage = _sleep_stage(_first(values, "sleep_level", "level", "stage"))
            if stamp is not None and stage is not None:
                events.append((stamp, stage))
        elif name == "sleep_assessment":
            assessments.append((_point_time(values), values))
    events.sort(key=lambda item: item[0])
    if not events and not assessments:
        return []

    sessions: list[SleepRecord] = []
    # Garmin sleep_level is transition/sample history. Split only at very large
    # gaps; normal wake periods inside one night remain part of the same record.
    groups: list[list[tuple[datetime, str]]] = []
    for event in events:
        if not groups or (event[0] - groups[-1][-1][0]).total_seconds() > 6 * 3600:
            groups.append([event])
        else:
            groups[-1].append(event)
    for group in groups[-32:]:
        if len(group) < 2:
            continue
        durations = {"awake": 0.0, "light": 0.0, "deep": 0.0, "rem": 0.0}
        for (stamp, stage), (next_stamp, _next_stage) in zip(group, group[1:]):
            seconds = max(0.0, min(3 * 3600.0, (next_stamp - stamp).total_seconds()))
            durations[stage] += seconds
        asleep = durations["light"] + durations["deep"] + durations["rem"]
        total = asleep + durations["awake"]
        if asleep <= 0:
            continue
        first_sleep = next((stamp for stamp, stage in group if stage != "awake"), group[0][0])
        last = group[-1][0]
        end = last
        sessions.append(SleepRecord(
            source=source,
            provider_domain="garmin_local",
            start=first_sleep.isoformat(),
            end=end.isoformat() if end > first_sleep else None,
            observed_at=last.isoformat(),
            duration_s=asleep,
            time_in_bed_s=total if total > 0 else None,
            awake_s=durations["awake"],
            light_sleep_s=durations["light"],
            deep_sleep_s=durations["deep"],
            rem_sleep_s=durations["rem"],
            sources=[source],
            provider_domains=["garmin_local"],
            field_sources={
                key: "garmin_local" for key in (
                    "start", "end", "duration_s", "time_in_bed_s", "awake_s",
                    "light_sleep_s", "deep_sleep_s", "rem_sleep_s",
                )
            },
        ))

    # Merge documented assessment summary fields into the closest staged night;
    # if no stage history is present, keep a sparse record for cross-provider merge.
    for stamp, values in assessments[-32:]:
        candidate = None
        if sessions and stamp is not None:
            candidate = min(
                sessions,
                key=lambda record: abs(((_dt(record.end or record.start) or stamp) - stamp).total_seconds()),
            )
        elif sessions:
            # FIT sleep_assessment has no timestamp field in the standard
            # profile. In a monitoring file it belongs to the staged sleep
            # session carried by the same file, so attach it to the newest one.
            candidate = sessions[-1]
        if candidate is None:
            candidate = SleepRecord(
                source=source,
                provider_domain="garmin_local",
                observed_at=stamp.isoformat() if stamp else None,
                sources=[source], provider_domains=["garmin_local"],
            )
            sessions.append(candidate)
        mappings = {
            "score": ("sleep_score", "overall_sleep_score", "score"),
            "average_hr": ("average_heart_rate", "avg_heart_rate", "average_hr"),
            "minimum_hr": ("lowest_heart_rate", "min_heart_rate", "minimum_heart_rate"),
            "hrv_ms": ("average_hrv", "avg_hrv", "hrv"),
            "respiratory_rate": ("average_respiration_rate", "avg_respiration_rate", "respiration_rate"),
            "spo2_percent": ("average_spo2", "avg_spo2", "spo2"),
            "recovery_score": ("sleep_recovery_score",),
            "disturbance_count": ("awakenings_count",),
        }
        for attr, keys in mappings.items():
            value = _scalar(_first(values, *keys))
            if attr == "spo2_percent":
                value = _scaled_percent(value)
            elif attr == "respiratory_rate":
                value = _scaled_respiration(value)
            if value is not None:
                if attr in {"score", "recovery_score"} and not 0 <= value <= 100:
                    continue
                if attr == "disturbance_count" and not 0 <= value <= 255:
                    continue
                setattr(candidate, attr, value)
                candidate.field_sources[attr] = "garmin_local"
        candidate.provider_values.setdefault("garmin_local", {}).update(
            {str(k)[:128]: _safe(v) for k, v in list(values.items())[:64]}
        )
    return sessions[-32:]


def health_history_from_fit(
    data: bytes,
    *,
    sensor_id: str,
    source_key: str,
    source_label: str | None = None,
) -> DeviceHistoryBatch:
    """Normalize Garmin wellness FIT messages into the universal health catalog."""
    frames = _health_frames(data)
    source = f"garmin_local:{sensor_id}:{source_key}"
    points: list[DeviceMetricPoint] = []

    def add(metric: str, value: Any, stamp: datetime | None, *, context: dict[str, Any] | None = None) -> None:
        number = _scalar(value, mean_list=True)
        if number is None or stamp is None:
            return
        points.append(DeviceMetricPoint(
            metric=metric,
            value=float(number),
            timestamp=stamp.isoformat(),
            source_type="garmin_local_ble_fit_health",
            source_entity=source_label,
            sources=(source,),
            context=tuple((str(k)[:64], _safe(v)) for k, v in list((context or {}).items())[:12]),
        ))

    for name, values in frames:
        stamp = _point_time(values)
        common_context = {"garmin_message": name}
        if name == "monitoring":
            activity_type = str(values.get("activity_type") or "")
            context = {**common_context, "activity_type": activity_type}
            add("heart_rate", _first(values, "heart_rate", "bpm"), stamp, context=context)
            steps = _first(values, "steps", "step_count")
            if steps is None and activity_type in {"walking", "running"}:
                steps = values.get("cycles")
            add("steps", steps, stamp, context={**context, "measurement_context": "current_total"})
            add("distance_m", _first(values, "distance", "distance_16"), stamp, context={**context, "measurement_context": "current_total"})
            add("calories", values.get("calories"), stamp, context={**context, "measurement_context": "current_total"})
            add("active_calories", values.get("active_calories"), stamp, context={**context, "measurement_context": "current_total"})
            active = _scalar(_first(values, "active_time", "active_time_16"))
            if active is not None:
                add("active_minutes", active / 60.0, stamp, context={**context, "measurement_context": "current_total"})
            add("activity_level", _first(values, "intensity", "activity_level"), stamp, context=context)
            add("floors_climbed", _first(values, "floors_climbed", "floors"), stamp, context={**context, "measurement_context": "current_total"})
            add("device_temperature", values.get("temperature"), stamp, context=context)
            add("device_temperature_min", values.get("temperature_min"), stamp, context=context)
            add("device_temperature_max", values.get("temperature_max"), stamp, context=context)
        elif name == "monitoring_info":
            add("basal_metabolic_rate", values.get("resting_metabolic_rate"), stamp, context=common_context)
        elif name in {"resting_heart_rate", "monitoring_hr_data"}:
            add("resting_heart_rate", _first(values, "current_day_resting_heart_rate", "daily_rhr", "resting_heart_rate"), stamp, context=common_context)
            add("heart_rate", _first(values, "heart_rate", "current_heart_rate"), stamp, context=common_context)
        elif name == "hr":
            add("heart_rate", _first(values, "heart_rate", "filtered_bpm", "bpm"), stamp, context=common_context)
        elif name == "stress_level":
            stress_stamp = _dt(values.get("stress_level_time")) or stamp
            value = _scalar(_first(values, "stress_level_value", "stress_level", "stress"))
            if value is not None and 0 <= value <= 100:
                add("stress", value, stress_stamp, context=common_context)
        elif name in {"respiration_rate", "hsa_respiration_data"}:
            value = _scaled_respiration(_first(values, "respiration_rate", "respiration", "value"))
            if value is not None and 4 <= value <= 100:
                add("respiratory_rate", value, stamp, context=common_context)
        elif name in {"spo2_data", "hsa_spo2_data"}:
            value = _scaled_percent(_first(values, "reading_spo2", "spo2", "percentage", "value"))
            context = {
                **common_context,
                "confidence": _safe(_first(values, "reading_confidence", "confidence")),
                "measurement_context": _safe(values.get("mode")),
            }
            if value is not None and 50 <= value <= 100:
                add("spo2", value, stamp, context=context)
        elif name == "hsa_heart_rate_data":
            if str(values.get("status") or "1") not in {"0", "searching"}:
                add("heart_rate", _first(values, "heart_rate", "bpm", "value"), stamp, context=common_context)
        elif name == "hsa_stress_data":
            value = _scalar(_first(values, "stress", "stress_level", "value"))
            if value is not None and 0 <= value <= 100:
                add("stress", value, stamp, context=common_context)
        elif name == "hsa_step_data":
            add("steps", _first(values, "steps", "step_count", "value"), stamp, context={**common_context, "measurement_context": "current_total"})
        elif name == "hsa_body_battery_data":
            level = _scalar(_first(values, "level", "body_battery", "body_battery_value", "value"))
            if level is not None and 0 <= level <= 100:
                add("body_battery", level, stamp, context=common_context)
            add("body_battery_charged", values.get("charged"), stamp, context={**common_context, "measurement_context": "current_total"})
            add("body_battery_drained", values.get("uncharged"), stamp, context={**common_context, "measurement_context": "current_total"})
        elif name == "hrv_status_summary":
            context = {**common_context, "hrv_status": _safe(values.get("status"))}
            add("hrv_ms", _first(values, "last_night_average", "weekly_average"), stamp, context=context)
        elif name == "hrv_value":
            add("hrv_ms", _first(values, "value", "hrv", "hrv_value"), stamp, context=common_context)
        elif name in {"hrv", "beat_intervals"}:
            value = _first(values, "time", "hrv")
            numeric = _scalar(value, mean_list=True)
            if numeric is not None and numeric < 10.0:
                numeric *= 1000.0
            add("beat_interval_ms", numeric, stamp, context=common_context)
        elif name == "weight_scale":
            for metric, keys in {
                "weight": ("weight",),
                "bmi": ("bmi",),
                "body_fat": ("percent_fat", "body_fat"),
                "body_water": ("percent_hydration", "body_water"),
                "muscle_mass": ("muscle_mass",),
                "bone_mass": ("bone_mass",),
                "visceral_fat_mass": ("visceral_fat_mass",),
                "visceral_fat_rating": ("visceral_fat_rating",),
                "basal_metabolic_rate": ("basal_met",),
                "active_metabolic_rate": ("active_met",),
                "metabolic_age": ("metabolic_age",),
            }.items():
                add(metric, _first(values, *keys), stamp, context=common_context)
        elif name == "blood_pressure":
            context = {**common_context, "status": _safe(values.get("status"))}
            add("systolic_blood_pressure", _first(values, "systolic_pressure", "systolic"), stamp, context=context)
            add("diastolic_blood_pressure", _first(values, "diastolic_pressure", "diastolic"), stamp, context=context)
            add("mean_arterial_pressure", values.get("mean_arterial_pressure"), stamp, context=context)
            add("heart_rate", values.get("heart_rate"), stamp, context=context)
        elif name == "skin_temp_overnight":
            add("skin_temperature", values.get("nightly_value"), stamp, context=common_context)
            add("skin_temperature_deviation", values.get("average_deviation"), stamp, context=common_context)
            add("skin_temperature_7d_deviation", values.get("average_7_day_deviation"), stamp, context=common_context)
        elif name == "hsa_wrist_temperature_data":
            add("skin_temperature", _first(values, "value", "wrist_temperature", "temperature"), stamp, context=common_context)
        elif name == "device_aux_battery_info":
            context = {**common_context, "battery_status": _safe(values.get("battery_status")), "battery_identifier": _safe(values.get("battery_identifier"))}
            add("device_battery_voltage", values.get("battery_voltage"), stamp, context=context)
            value = _scaled_percent(_first(values, "battery_level", "battery_percentage", "battery"))
            if value is not None and 0 <= value <= 100:
                add("battery", value, stamp, context=context)
        elif name == "max_met_data":
            context = {
                **common_context,
                "sport": _safe(values.get("sport")),
                "sub_sport": _safe(values.get("sub_sport")),
                "hr_source": _safe(values.get("hr_source")),
                "speed_source": _safe(values.get("speed_source")),
            }
            add("vo2_max", values.get("vo2_max"), stamp, context=context)

    sleep = _sleep_records_from_frames(frames, source=source)
    for record in sleep:
        start = _dt(record.start)
        end = _dt(record.end)
        if start is None or end is None or end <= start:
            continue
        samples: dict[str, list[float]] = {}
        for point in points:
            stamp = _dt(point.timestamp)
            if stamp is None or stamp < start or stamp > end:
                continue
            samples.setdefault(point.metric, []).append(float(point.value))
        if samples.get("heart_rate"):
            record.average_hr = sum(samples["heart_rate"]) / len(samples["heart_rate"])
            record.minimum_hr = min(samples["heart_rate"])
            record.field_sources["average_hr"] = "garmin_local"
            record.field_sources["minimum_hr"] = "garmin_local"
        for metric, attr in (("hrv_ms", "hrv_ms"), ("respiratory_rate", "respiratory_rate"), ("spo2", "spo2_percent")):
            values = samples.get(metric)
            if values:
                setattr(record, attr, sum(values) / len(values))
                record.field_sources[attr] = "garmin_local"
    return DeviceHistoryBatch.bounded(metric_points=points, sleep_records=sleep)


def fit_message_names(data: bytes) -> tuple[str, ...]:
    """Return a bounded message-name inventory for unsupported FIT diagnostics."""
    container = _fit_container(data)
    import fitdecode

    names: set[str] = set()
    count = 0
    with fitdecode.FitReader(io.BytesIO(container), check_crc=fitdecode.CrcCheck.RAISE) as reader:
        for frame in reader:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            count += 1
            if count > MAX_HEALTH_FRAMES:
                raise ValueError("Garmin FIT frame count exceeds safe limit")
            if len(names) < 64:
                names.add(str(frame.name)[:128])
    return tuple(sorted(names))


def fit_content_kind(data: bytes) -> str:
    """Return activity, health or unsupported from decoded FIT message evidence."""
    container = _fit_container(data)
    import fitdecode
    saw_health = False
    count = 0
    with fitdecode.FitReader(io.BytesIO(container), check_crc=fitdecode.CrcCheck.RAISE) as reader:
        for frame in reader:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            count += 1
            if count > MAX_HEALTH_FRAMES:
                raise ValueError("Garmin FIT frame count exceeds safe limit")
            name = str(frame.name)
            if name == "session":
                return "activity"
            if name in HEALTH_MESSAGE_NAMES:
                saw_health = True
    return "health" if saw_health else "unsupported"

def workout_from_fit(
    data: bytes,
    *,
    sensor_id: str,
    source_key: str,
    source_label: str | None = None,
    provider_id: str = "garmin_local",
    history_source: str = "garmin_local_ble_fit",
    source_prefix: str = "garmin_local",
) -> Workout:
    """Normalize the first completed FIT activity session to Workout.

    Garmin direct sync is the default caller, but the FIT container itself is a
    vendor-neutral interchange format.  File/export adapters can reuse the same
    bounded parser while supplying their own provenance; no external-adapter
    identity leaks into the Garmin transport implementation.
    """
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
    source = f"{source_prefix}:{sensor_id}:{source_key}"
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
        provider_domains=[provider_id],
        extra={
            "fitness_adapter": provider_id,
            "fitness_history_source": history_source,
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
            "gps_track": _gps_points(relevant),
            "gps_points": _gps_points(relevant),
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
    workout.field_sources = {key: provider_id for key in factual if getattr(workout, key) is not None}
    workout.provider_values = {provider_id: summary}
    return workout
