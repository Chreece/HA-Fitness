"""Documented Bangle.js NUS/Health/Recorder normalization primitives."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import io
import json
import math
from typing import Any, Iterable

from ...providers.sleep import SleepRecord
from ...providers.workouts import Workout
from ..history import DeviceHistoryBatch, DeviceMetricPoint

NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
RESULT_PREFIX = "FITNESS_BANGLE:"
MAX_HEALTH_ROWS = 2048
MAX_WORKOUTS = 32
MAX_TRACK_POINTS = 256


def bangle_identity(name: str | None, service_uuids: Iterable[str]) -> dict[str, Any] | None:
    services = {str(value).strip().lower() for value in (service_uuids or ())}
    advertised = str(name or "").strip()
    # NUS is generic; require Bangle's documented local-name family too so a
    # random UART peripheral can never be claimed as a watch.
    if NUS_SERVICE_UUID not in services or not advertised.lower().startswith("bangle.js"):
        return None
    return {
        "archive_adapter": "bangle_js",
        "archive_compatible": True,
        "workout_archive": True,
        "manufacturer": "Espruino",
        "fitness_vendor_identity": "banglejs",
        "model": advertised,
        "smart_device_default_type": "smartwatch",
        "bangle_protocol": "nus_health_recorder_v1",
    }


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _iso_ms(value: Any) -> str | None:
    number = _finite(value)
    if number is None:
        return None
    # Bangle JS sends Date.getTime() milliseconds in our export expression.
    try:
        return datetime.fromtimestamp(number / 1000.0, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def health_batch(rows: Iterable[dict[str, Any]], *, sensor_id: str) -> DeviceHistoryBatch:
    points: list[DeviceMetricPoint] = []
    source_type = "direct_banglejs_health"
    for row in list(rows)[:MAX_HEALTH_ROWS]:
        if not isinstance(row, dict):
            continue
        stamp = _iso_ms(row.get("t"))
        if stamp is None:
            continue
        context_items: list[tuple[str, Any]] = []
        activity = str(row.get("activity") or "").strip()
        if activity:
            context_items.append(("activity", activity.lower()))
        charging = row.get("charging")
        if isinstance(charging, bool):
            context_items.append(("charging", charging))
        context = tuple(context_items)
        mappings = (
            ("steps", row.get("steps")),
            ("heart_rate", row.get("bpm")),
            ("min_heart_rate", row.get("bpmMin")),
            ("max_heart_rate", row.get("bpmMax")),
            ("battery", row.get("battery")),
            ("body_temperature", row.get("temperature")),
        )
        for metric, raw in mappings:
            value = _finite(raw)
            if value is None:
                continue
            if metric.endswith("heart_rate") and not 20 <= value <= 260:
                continue
            if metric == "battery" and not 0 <= value <= 100:
                continue
            points.append(DeviceMetricPoint(metric, value, stamp, source_type, sensor_id, (sensor_id,), context))
        if isinstance(charging, bool):
            points.append(DeviceMetricPoint("charging", 1.0 if charging else 0.0, stamp, source_type, sensor_id, (sensor_id,), context))
        if activity in {"NOT_WORN", "WALKING", "EXERCISE", "LIGHT_SLEEP", "DEEP_SLEEP"}:
            worn = 0.0 if activity == "NOT_WORN" else 1.0
            points.append(DeviceMetricPoint("wear_state", worn, stamp, source_type, sensor_id, (sensor_id,), context))
    # Bangle Health explicitly stores LIGHT_SLEEP and DEEP_SLEEP in 10-minute
    # records. Reconstruct bounded contiguous sleep blocks without inventing
    # REM/awake stages that the Health database does not contain.
    sleep_rows: list[tuple[datetime, str, float | None]] = []
    for row in list(rows)[:MAX_HEALTH_ROWS]:
        if not isinstance(row, dict) or row.get("activity") not in {"LIGHT_SLEEP", "DEEP_SLEEP"}:
            continue
        stamp = _iso_ms(row.get("t"))
        if stamp is None:
            continue
        try:
            dt = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        sleep_rows.append((dt, str(row.get("activity")), _finite(row.get("bpm"))))
    sleep_rows.sort(key=lambda item: item[0])
    records: list[SleepRecord] = []
    group: list[tuple[datetime, str, float | None]] = []
    def flush() -> None:
        if not group:
            return
        start = group[0][0]
        end = group[-1][0] + timedelta(minutes=10)
        light = sum(600 for _, state, _ in group if state == "LIGHT_SLEEP")
        deep = sum(600 for _, state, _ in group if state == "DEEP_SLEEP")
        hrs = [hr for _, _, hr in group if hr is not None and 20 <= hr <= 260]
        records.append(SleepRecord(
            source=f"banglejs:{sensor_id}:{start.date().isoformat()}",
            provider_domain="direct_banglejs",
            start=start.isoformat(),
            end=end.isoformat(),
            observed_at=end.isoformat(),
            duration_s=(end - start).total_seconds(),
            time_in_bed_s=(end - start).total_seconds(),
            light_sleep_s=float(light),
            deep_sleep_s=float(deep),
            average_hr=(sum(hrs) / len(hrs) if hrs else None),
            minimum_hr=(min(hrs) if hrs else None),
            in_bed=True,
            sources=[sensor_id],
            provider_domains=["direct_banglejs"],
        ))
        group.clear()
    for item in sleep_rows:
        if group and item[0] - group[-1][0] > timedelta(minutes=20):
            flush()
        group.append(item)
    flush()
    return DeviceHistoryBatch.bounded(metric_points=points, sleep_records=records)


def _csv_number(row: dict[str, str], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            result = _finite(value)
            if result is not None:
                return result
    return None


def workout_from_recorder_csv(text: str, *, sensor_id: str, filename: str) -> Workout | None:
    reader = csv.DictReader(io.StringIO(str(text or "")))
    rows = [row for _, row in zip(range(20000), reader) if isinstance(row, dict)]
    if not rows:
        return None
    timed: list[tuple[float, dict[str, str]]] = []
    for row in rows:
        epoch = _csv_number(row, "Time")
        if epoch is not None and epoch > 0:
            timed.append((epoch, row))
    if not timed:
        return None
    timed.sort(key=lambda item: item[0])
    start_epoch, first = timed[0]
    end_epoch, _last = timed[-1]
    hrs = [v for _, row in timed if (v := _csv_number(row, "HR", "Heart Rate", "HeartRate")) is not None and 20 <= v <= 260]
    powers = [v for _, row in timed if (v := _csv_number(row, "Power")) is not None]
    cadences = [v for _, row in timed if (v := _csv_number(row, "Cadence")) is not None]
    distances = [v for _, row in timed if (v := _csv_number(row, "Distance")) is not None]
    track: list[list[float]] = []
    for _, row in timed:
        lat = _csv_number(row, "Latitude")
        lon = _csv_number(row, "Longitude")
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        p = [round(lat, 6), round(lon, 6)]
        if not track or p != track[-1]:
            track.append(p)
    if len(track) > MAX_TRACK_POINTS:
        last = len(track) - 1
        track = [track[round(i * last / (MAX_TRACK_POINTS - 1))] for i in range(MAX_TRACK_POINTS)]
    metadata: dict[str, Any] = {}
    raw_meta = first.get("Metadata")
    if raw_meta:
        try:
            parsed = json.loads(raw_meta)
            if isinstance(parsed, dict):
                metadata = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    sport = str(metadata.get("activity") or "").strip() or None
    duration = max(0.0, end_epoch - start_epoch)
    start = datetime.fromtimestamp(start_epoch, tz=timezone.utc).isoformat()
    end = datetime.fromtimestamp(end_epoch, tz=timezone.utc).isoformat()
    distance_m = max(distances) if distances else None
    if distance_m is None and track:
        distance_m = None  # keep factual: do not synthesize from sampled GPS points
    extra = {
        "history_source": "banglejs_recorder_csv",
        "source_entity": sensor_id,
        "recorder_filename": str(filename)[:128],
        "gps_track": track,
        "metadata": {str(k)[:64]: v for k, v in list(metadata.items())[:32]},
    }
    return Workout(
        source=f"banglejs:{sensor_id}:{filename}",
        name=(f"Bangle.js {sport}" if sport else "Bangle.js workout"),
        sport=sport,
        start=start,
        end=end,
        duration_s=duration,
        elapsed_time_s=duration,
        distance_m=distance_m,
        avg_hr=(sum(hrs) / len(hrs) if hrs else None),
        max_hr=(max(hrs) if hrs else None),
        avg_power=(sum(powers) / len(powers) if powers else None),
        max_power=(max(powers) if powers else None),
        avg_cadence=(sum(cadences) / len(cadences) if cadences else None),
        max_cadence=(max(cadences) if cadences else None),
        start_latitude=(track[0][0] if track else None),
        start_longitude=(track[0][1] if track else None),
        device_name="Bangle.js",
        sample_count=len(timed),
        sources=[sensor_id],
        provider_domains=["banglejs"],
        extra=extra,
    )
