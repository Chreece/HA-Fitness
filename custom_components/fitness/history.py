"""Validated canonical longitudinal history for HA-Fitness."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import mean
from typing import Any

MIN_TIMESTAMP = datetime(2000, 1, 1, tzinfo=timezone.utc)
MAX_POINTS_PER_METRIC = 120

# Broad corruption guards only; these are not health/reference ranges.
METRIC_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "vo2max": (5.0, 100.0),
    "resting_hr": (20.0, 220.0),
    "weight": (20.0, 500.0),
    "weight_kg": (20.0, 500.0),
    "hrv_weekly": (1.0, 500.0),
    "hrv_last_night": (1.0, 500.0),
    "fitness_age": (5.0, 120.0),
    "threshold_hr": (30.0, 240.0),
    "threshold_speed": (0.05, 20.0),
    "threshold_pace": (30.0, 3600.0),
    "threshold_power": (1.0, 3000.0),
    "ftp_running": (1.0, 3000.0),
    "power_to_weight_running": (0.05, 20.0),
    "training_readiness": (0.0, 100.0),
    "sleep_score": (0.0, 100.0),
    # Direct-device longitudinal wellness metrics.  Bounds are intentionally
    # broad corruption guards, not medical/reference ranges.
    "heart_rate": (20.0, 260.0),
    "max_hr": (20.0, 260.0),
    "min_hr": (20.0, 260.0),
    "max_heart_rate": (20.0, 260.0),
    "min_heart_rate": (20.0, 260.0),
    "resting_heart_rate": (20.0, 220.0),
    "hrv_ms": (1.0, 1000.0),
    "beat_interval_ms": (200.0, 3000.0),
    "spo2": (50.0, 100.0),
    "skin_temperature": (10.0, 55.0),
    "skin_temperature_min": (10.0, 55.0),
    "skin_temperature_max": (10.0, 55.0),
    "body_temperature": (20.0, 50.0),
    "device_temperature": (-40.0, 100.0),
    "steps": (0.0, 250000.0),
    "moderate_minutes": (0.0, 1440.0),
    "vigorous_minutes": (0.0, 1440.0),
    "distance_m": (0.0, 500000.0),
    "calories": (0.0, 30000.0),
    "stress": (0.0, 255.0),
    "body_battery": (0.0, 100.0),
    "body_battery_charged": (-1000.0, 1000.0),
    "body_battery_drained": (-1000.0, 1000.0),
    "vo2_max": (5.0, 100.0),
    "active_calories": (0.0, 30000.0),
    "basal_metabolic_rate": (0.0, 10000.0),
    "active_metabolic_rate": (0.0, 30000.0),
    "metabolic_age": (0.0, 150.0),
    "visceral_fat_mass": (0.0, 100.0),
    "visceral_fat_rating": (0.0, 100.0),
    "floors_climbed": (0.0, 1000.0),
    "systolic_blood_pressure": (40.0, 300.0),
    "diastolic_blood_pressure": (20.0, 200.0),
    "mean_arterial_pressure": (20.0, 250.0),
    "skin_temperature_deviation": (-20.0, 20.0),
    "skin_temperature_7d_deviation": (-20.0, 20.0),
    "device_temperature_min": (-80.0, 120.0),
    "device_temperature_max": (-80.0, 120.0),
    "activity_level": (0.0, 255.0),
    "activity_minutes": (0.0, 1440.0),
    "active_minutes": (0.0, 1440.0),
    "respiratory_rate": (1.0, 100.0),
    "battery": (0.0, 100.0),
    "device_battery_voltage": (0.0, 20.0),
    "charging": (0.0, 1.0),
    "wear_state": (0.0, 1.0),
    "bmi": (5.0, 100.0),
    "body_fat": (0.0, 100.0),
    "body_water": (0.0, 100.0),
    "muscle_mass": (0.0, 300.0),
    "bone_mass": (0.0, 30.0),
}

def parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif value is None:
        return None
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            try:
                number = float(raw)
                if number > 10_000_000_000:
                    number /= 1000.0
                dt = datetime.fromtimestamp(number, tz=timezone.utc)
            except (TypeError, ValueError, OverflowError, OSError):
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def validate_timestamp(value: Any, now: datetime) -> tuple[datetime | None, str | None]:
    dt = parse_timestamp(value)
    if dt is None:
        return None, "invalid_timestamp"
    if dt < MIN_TIMESTAMP:
        return None, "timestamp_before_2000"
    if dt > now + timedelta(days=1):
        return None, "future_timestamp"
    return dt, None

def validate_value(metric: str, value: Any) -> tuple[float | None, str | None]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, "non_numeric"
    if not isfinite(number):
        return None, "non_finite"
    low, high = METRIC_BOUNDS.get(metric, (None, None))
    if low is not None and number < low:
        return None, "below_corruption_bound"
    if high is not None and number > high:
        return None, "above_corruption_bound"
    return number, None

def validate_series(metric: str, raw: list[dict[str, Any]] | None, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    rejected: dict[str, int] = {}
    def reject(reason: str):
        rejected[reason] = rejected.get(reason, 0) + 1
    by_day: dict[object, dict[str, Any]] = {}
    for item in raw or []:
        if not isinstance(item, dict):
            reject("invalid_record"); continue
        dt, err = validate_timestamp(item.get("timestamp") or item.get("start"), now)
        if err:
            reject(err); continue
        value, err = validate_value(metric, item.get("value"))
        if err:
            reject(err); continue
        point = {
            "timestamp": dt.isoformat(), "value": value,
            "source_type": str(item.get("source_type") or "fitness_canonical"),
            "source_entity": item.get("source_entity") or item.get("entity_id"),
            "sources": list(item.get("sources") or []),
            "imported": bool(item.get("imported")),
        }
        day = dt.date()
        old = by_day.get(day)
        # Freshness is authoritative. Source type/import status only break an
        # exact timestamp tie; stale integration/merged values must never
        # overwrite a newer direct-device measurement from the same day.
        source_type = point["source_type"]
        source_tie = (
            source_type.startswith("direct_"),
            source_type == "fitness_merged_current",
            not source_type.startswith("integration:"),
            not point["imported"],
        )
        rank = (dt.timestamp(), *source_tie)
        if old is not None:
            old_dt = parse_timestamp(old["timestamp"])
            old_source_type = old["source_type"]
            old_tie = (
                old_source_type.startswith("direct_"),
                old_source_type == "fitness_merged_current",
                not old_source_type.startswith("integration:"),
                not old["imported"],
            )
            old_rank = (old_dt.timestamp(), *old_tie)
            reject("duplicate_day")
            if rank <= old_rank:
                continue
        by_day[day] = point
    points = sorted(by_day.values(), key=lambda p: p["timestamp"])[-MAX_POINTS_PER_METRIC:]
    audit = {
        "raw_samples": len(raw or []), "valid_samples": len(points),
        "rejected_samples": sum(rejected.values()), "rejection_reasons": dict(sorted(rejected.items())),
    }
    return points, audit

def remember(metric_history, metric, value, timestamp, *, source_type, source_entity=None, sources=None, imported=False, now=None):
    bucket = metric_history.setdefault(metric, [])
    bucket.append({"timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
                   "value": value, "source_type": source_type, "source_entity": source_entity,
                   "sources": list(sources or []), "imported": imported})
    points, audit = validate_series(metric, bucket, now)
    metric_history[metric] = points
    return audit

def ingest_recorder(metric_history, metric, periods, source_entity, now=None):
    bucket = metric_history.setdefault(metric, [])
    for row in periods or []:
        if not isinstance(row, dict):
            bucket.append({"timestamp": None, "value": None, "source_type": "recorder_bootstrap", "imported": True})
            continue
        value = row.get("mean") if row.get("mean") is not None else row.get("state")
        bucket.append({"timestamp": row.get("start"), "value": value, "source_type": "recorder_bootstrap",
                       "source_entity": source_entity, "sources": [source_entity], "imported": True})
    points, audit = validate_series(metric, bucket, now)
    metric_history[metric] = points
    return audit

def summarize(metric: str, raw, now=None):
    now = now or datetime.now(timezone.utc)
    points, audit = validate_series(metric, raw, now)
    dated = [(parse_timestamp(p["timestamp"]), float(p["value"])) for p in points]
    def window(days):
        cutoff = now.date() - timedelta(days=days - 1)
        return [(dt, value) for dt, value in dated if cutoff <= dt.date() <= now.date()]
    v7, v28, v90 = window(7), window(28), window(90)
    recent14 = window(14)
    pstart, pend = now.date()-timedelta(days=27), now.date()-timedelta(days=14)
    prior14 = [(dt,v) for dt,v in dated if pstart <= dt.date() <= pend]
    trend = None
    if len(recent14) >= 10 and len(prior14) >= 10:
        prior = mean(v for _,v in prior14)
        if prior:
            trend = (mean(v for _,v in recent14)-prior)/abs(prior)*100
    slope = None
    if len(v90) >= 30:
        x0=v90[0][0]; xs=[(dt-x0).total_seconds()/86400 for dt,_ in v90]; ys=[v for _,v in v90]
        xb,yb=mean(xs),mean(ys); denom=sum((x-xb)**2 for x in xs)
        if denom and yb:
            slope=sum((x-xb)*(y-yb) for x,y in zip(xs,ys))/denom*30/abs(yb)*100
    out = dict(audit)
    out.update({
        "history_valid": bool(points), "data_source": "fitness_canonical_history",
        "days_available": len(points), "days_7d": len(v7), "days_28d": len(v28), "days_90d": len(v90),
        "minimum_7d": 5, "minimum_28d": 21, "minimum_90d": 60,
        "mean_7d": round(mean(v for _,v in v7),3) if len(v7)>=5 else None,
        "mean_28d": round(mean(v for _,v in v28),3) if len(v28)>=21 else None,
        "mean_90d": round(mean(v for _,v in v90),3) if len(v90)>=60 else None,
        "trend_14_vs_previous_14_percent": round(trend,2) if trend is not None else None,
        "slope_percent_per_30d": round(slope,3) if slope is not None else None,
        "latest_daily_mean": round(points[-1]["value"],3) if points else None,
        "oldest_sample": points[0]["timestamp"] if points else None, "newest_sample": points[-1]["timestamp"] if points else None,
        "daily": [{"start":p["timestamp"], "value":round(p["value"],4), "source_type":p["source_type"],
                   "source_entity":p["source_entity"], "sources":p["sources"]} for p in points[-90:]],
    })
    return out

def summarize_all(metric_history, now=None):
    summaries={}; audits={}
    for metric in sorted(metric_history):
        points,audit=validate_series(metric, metric_history.get(metric), now)
        metric_history[metric]=points
        summaries[metric]=summarize(metric, points, now)
        audits[metric]={k:summaries[metric].get(k) for k in ("history_valid","data_source","raw_samples","valid_samples","rejected_samples","rejection_reasons","days_available","days_7d","days_28d","days_90d","oldest_sample","newest_sample")}
    return summaries,audits

def validate_workout(workout, now=None):
    now=now or datetime.now(timezone.utc)
    _,err=validate_timestamp(getattr(workout,"start",None),now)
    if err: return err
    for name, allow_zero, max_value in (("duration_s",False,86400),("distance_m",True,None),("banister_trimp",True,None)):
        value=getattr(workout,name,None)
        if value is None: continue
        try: value=float(value)
        except (TypeError,ValueError): return f"invalid_{name}"
        if not isfinite(value) or value < 0 or (not allow_zero and value <= 0) or (max_value and value > max_value): return f"invalid_{name}"
    return None

def validate_sleep(record, now=None):
    now=now or datetime.now(timezone.utc)
    start=parse_timestamp(getattr(record,"start",None)); end=parse_timestamp(getattr(record,"end",None))
    if start is None or end is None: return "incomplete_sleep"
    _,err=validate_timestamp(start,now)
    if err: return err
    _,err=validate_timestamp(end,now)
    if err: return err
    if end <= start or end-start > timedelta(hours=24): return "invalid_sleep_interval"
    duration=getattr(record,"duration_s",None)
    if duration is not None:
        try: duration=float(duration)
        except (TypeError,ValueError): return "invalid_sleep_duration"
        if not isfinite(duration) or duration <= 0 or duration > 86400: return "invalid_sleep_duration"
    return None
