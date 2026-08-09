"""Provider-independent completed-workout discovery and merging."""

from __future__ import annotations

from dataclasses import dataclass, asdict, field, fields
from datetime import datetime, timezone
from typing import Any
import math
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..const import CONF_WORKOUT_DEVICE_IDS


_INVALID = (None, "", "unknown", "unavailable", "none", "null")

# Keys which are useful enough to normalize into first-class Workout fields.
_FIELD_KEYS: dict[str, tuple[str, ...]] = {
    "name": (
        "activityName", "activity_name", "name", "title", "workout_name",
        "workoutName", "ride_title",
    ),
    "sport": (
        "activityType", "activity_type", "sport_type", "sportType", "type",
        "workout_type", "workoutType",
    ),
    "start": (
        "startTime", "start_time", "startTimeLocal", "start_date",
        "start_date_local", "start", "startDate", "start_time_local",
        "startTimeGMT", "date",
    ),
    "end": (
        "endTime", "end_time", "endDate", "end_date", "stop_time",
    ),
    "duration_s": (
        "duration", "duration_s", "durationSeconds", "elapsedDuration",
        "elapsed_time", "elapsedTime", "movingDuration",
    ),
    "moving_time_s": (
        "moving_time", "movingTime", "moving_time_s",
    ),
    "elapsed_time_s": (
        "elapsed_time", "elapsedTime", "elapsed_time_s",
    ),
    "distance_m": (
        "distance", "distanceMeters", "distance_m", "distance_meter",
    ),
    "avg_hr": (
        "averageHR", "averageHeartRate", "average_heartrate",
        "average_heart_rate", "avg_hr", "avgHeartRate",
    ),
    "max_hr": (
        "maxHR", "maxHeartRate", "max_heartrate", "max_heart_rate",
        "max_hr",
    ),
    "avg_power": (
        "avgPower", "averagePower", "average_watts", "averageWatts",
        "average_power", "avg_power",
    ),
    "max_power": (
        "maxPower", "max_watts", "maxWatts", "max_power",
    ),
    "weighted_power": (
        "weighted_average_watts", "weightedAverageWatts", "normalizedPower",
        "normalized_power",
    ),
    "avg_cadence": (
        "averageCadence", "average_cadence", "averageRunCadence",
        "averageRunningCadenceInStepsPerMinute", "averageBikeCadence",
        "avg_cadence",
    ),
    "max_cadence": (
        "maxCadence", "max_cadence", "maxRunningCadenceInStepsPerMinute",
    ),
    "elevation_gain_m": (
        "elevationGain", "total_elevation_gain", "elevation_gain",
        "totalElevationGain",
    ),
    "elevation_loss_m": (
        "elevationLoss", "total_elevation_loss", "elevation_loss",
    ),
    "calories": ("calories", "kilocalories", "active_calories"),
    "aerobic_training_effect": (
        "aerobicTrainingEffect", "aerobic_training_effect",
    ),
    "anaerobic_training_effect": (
        "anaerobicTrainingEffect", "anaerobic_training_effect",
    ),
    "training_effect_label": (
        "trainingEffectLabel", "training_effect_label",
    ),
    "training_load": (
        "activityTrainingLoad", "training_load", "trainingLoad",
    ),
    "moderate_minutes": (
        "moderateIntensityMinutes", "moderate_minutes",
    ),
    "vigorous_minutes": (
        "vigorousIntensityMinutes", "vigorous_minutes",
    ),
    "vo2max": (
        "vO2MaxValue", "vo2MaxValue", "vo2max", "vo2_max",
    ),
    "average_speed_m_s": (
        "averageSpeed", "average_speed", "avg_speed",
    ),
    "max_speed_m_s": ("maxSpeed", "max_speed"),
    "relative_effort": (
        "relative_effort", "relativeEffort", "suffer_score", "sufferScore",
    ),
    "kilojoules": ("kilojoules", "kJ", "kj"),
    "total_reps": ("total_reps", "totalReps", "reps"),
    "exercise_count": ("exercise_count", "exerciseCount"),
    "volume_kg": ("volume_kg", "volumeKg", "total_volume", "volume"),
    "device_name": (
        "device_name", "deviceName", "device", "source_device",
    ),
    "gear_name": (
        "gear_name", "gearName", "gear", "gear_id", "gearId",
    ),
}


@dataclass(slots=True)
class Workout:
    source: str
    name: str | None = None
    sport: str | None = None
    start: str | None = None
    end: str | None = None
    duration_s: float | None = None
    moving_time_s: float | None = None
    elapsed_time_s: float | None = None
    distance_m: float | None = None
    avg_hr: float | None = None
    max_hr: float | None = None
    avg_power: float | None = None
    max_power: float | None = None
    weighted_power: float | None = None
    avg_cadence: float | None = None
    max_cadence: float | None = None
    elevation_gain_m: float | None = None
    elevation_loss_m: float | None = None
    calories: float | None = None
    aerobic_training_effect: float | None = None
    anaerobic_training_effect: float | None = None
    training_effect_label: str | None = None
    training_load: float | None = None
    moderate_minutes: float | None = None
    vigorous_minutes: float | None = None
    vo2max: float | None = None
    average_speed_m_s: float | None = None
    max_speed_m_s: float | None = None
    relative_effort: float | None = None
    kilojoules: float | None = None
    total_reps: float | None = None
    exercise_count: float | None = None
    volume_kg: float | None = None
    device_name: str | None = None
    gear_name: str | None = None
    sample_count: int | None = None

    # Scientifically/descriptively derived Fitness workout fields.
    banister_trimp: float | None = None
    trimp_per_hour: float | None = None
    mechanical_work_kj: float | None = None
    aerobic_efficiency: float | None = None
    aerobic_efficiency_kind: str | None = None
    aerobic_decoupling_percent: float | None = None
    hrr_10s: float | None = None
    hrr_30s: float | None = None
    hrr_60s: float | None = None
    hrr_120s: float | None = None
    time_very_light_s: float | None = None
    time_light_s: float | None = None
    time_moderate_s: float | None = None
    time_vigorous_s: float | None = None
    time_near_maximal_s: float | None = None

    # Merge/provenance fields.
    sources: list[str] = field(default_factory=list)
    provider_domains: list[str] = field(default_factory=list)
    field_sources: dict[str, str] = field(default_factory=dict)
    provider_values: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _valid(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() not in _INVALID
    return v is not None


def _num(v):
    if not _valid(v):
        return None
    try:
        value = float(v)
        if not math.isfinite(value):
            return None
        return value
    except (TypeError, ValueError):
        return None


def _dt(v):
    if not _valid(v):
        return None
    if isinstance(v, datetime):
        dt = v
    else:
        text = str(v).strip()
        try:
            n = float(text)
            if n > 10_000_000_000:
                n /= 1000
            dt = datetime.fromtimestamp(n, tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _get(attrs: dict[str, Any], *keys):
    normalized = {_norm_key(k): v for k, v in attrs.items()}
    for key in keys:
        value = normalized.get(_norm_key(key))
        if _valid(value):
            return value
    return None


def _provider_domain(hass: HomeAssistant, entry) -> str:
    if not getattr(entry, "config_entry_id", None):
        return "unknown"
    config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
    return config_entry.domain if config_entry is not None else "unknown"


def _safe_extra_value(value):
    """Keep recorder-friendly scalar/list/dict values and drop huge blobs."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 1000:
            return value[:1000] + "…"
        return value
    if isinstance(value, (list, tuple)):
        if len(value) > 50:
            return f"<list:{len(value)} items>"
        return [_safe_extra_value(v) for v in value]
    if isinstance(value, dict):
        if len(value) > 50:
            return f"<dict:{len(value)} keys>"
        return {
            str(k): _safe_extra_value(v)
            for k, v in value.items()
        }
    return str(value)[:500]


def _normalize_duration(value, key: str | None = None) -> float | None:
    v = _num(value)
    if v is None:
        return None
    key_norm = _norm_key(key or "")
    if "minute" in key_norm or key_norm.endswith("min"):
        return v * 60.0
    # Hevy last_workout_duration sensor commonly reports minutes.
    if "workoutduration" in key_norm and v < 1000:
        return v * 60.0
    return v


def _extract_record(
    raw: dict[str, Any],
    *,
    source: str,
    provider_domain: str,
    source_state=None,
) -> Workout | None:
    """Normalize one activity/workout-like dictionary."""
    if not isinstance(raw, dict):
        return None

    start_raw = _get(raw, *_FIELD_KEYS["start"])
    start_dt = _dt(start_raw)

    # Some activity integrations put a timestamp in entity state.
    if start_dt is None and source_state is not None:
        start_dt = _dt(source_state.state)

    # A completed workout must have a start time; this prevents daily summary
    # sensors and planned workouts from being mistaken for activities.
    if start_dt is None:
        return None

    kwargs: dict[str, Any] = {
        "source": source,
        "start": start_dt.isoformat(),
        "sources": [source],
        "provider_domains": [provider_domain],
    }

    consumed: set[str] = set()
    normalized_raw = {_norm_key(k): (k, v) for k, v in raw.items()}

    for field_name, aliases in _FIELD_KEYS.items():
        if field_name == "start":
            continue

        matched_key = None
        value = None
        for alias in aliases:
            item = normalized_raw.get(_norm_key(alias))
            if item is not None and _valid(item[1]):
                matched_key, value = item
                consumed.add(str(matched_key))
                break

        if value is None:
            continue

        if field_name in ("name", "sport", "training_effect_label", "device_name", "gear_name"):
            kwargs[field_name] = str(value)
        elif field_name == "end":
            end_dt = _dt(value)
            kwargs[field_name] = end_dt.isoformat() if end_dt else None
        elif field_name in ("duration_s", "moving_time_s", "elapsed_time_s"):
            kwargs[field_name] = _normalize_duration(value, matched_key)
        else:
            kwargs[field_name] = _num(value)

    # If duration is absent but moving/elapsed exists, use it as the generic duration.
    if kwargs.get("duration_s") is None:
        kwargs["duration_s"] = (
            kwargs.get("moving_time_s")
            or kwargs.get("elapsed_time_s")
        )

    # Preserve provider-specific fields so mismatches never disappear.
    extra = {}
    for key, value in raw.items():
        if str(key) in consumed:
            continue
        if _valid(value):
            extra[str(key)] = _safe_extra_value(value)

    kwargs["extra"] = extra
    kwargs["provider_values"] = {
        provider_domain: {
            str(k): _safe_extra_value(v)
            for k, v in raw.items()
            if _valid(v)
        }
    }

    workout = Workout(**kwargs)

    # At least one meaningful activity signal besides the timestamp.
    if not any(
        getattr(workout, name) is not None
        for name in (
            "name", "sport", "duration_s", "distance_m", "avg_hr",
            "avg_power", "calories", "volume_kg", "total_reps",
        )
    ):
        return None

    return workout


def _activity_dicts(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """Find nested activity/workout dictionaries and recent-activity lists."""
    result: list[dict[str, Any]] = []

    for key, value in attrs.items():
        nk = _norm_key(key)

        if isinstance(value, dict) and any(
            token in nk
            for token in ("activity", "workout", "exercise", "session")
        ):
            result.append(value)

        if isinstance(value, list) and any(
            token in nk
            for token in (
                "activities", "activitylist", "workouts",
                "workoutlist", "exercises", "sessions",
            )
        ):
            result.extend(
                item for item in value
                if isinstance(item, dict)
            )

    return result


def _generic_activity_entities(
    hass: HomeAssistant,
    config: dict,
) -> list[Workout]:
    """Parse activity-like entities from any selected workout device."""
    device_ids = set(config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    registry = er.async_get(hass)
    workouts: list[Workout] = []

    for entry in registry.entities.values():
        if entry.device_id not in device_ids:
            continue
        if not entry.entity_id.startswith("sensor."):
            continue

        state = hass.states.get(entry.entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            continue

        label = (
            f"{entry.entity_id} {entry.name or ''} "
            f"{entry.original_name or ''}"
        ).lower()

        # Never treat schedules/plans/aggregate totals/routes as completed workouts.
        if any(token in label for token in (
            "scheduled", "planned", "next_workout", "workout_plan",
            "summary", "year_to_date", "all_time", "recent_total",
            "route", "polyline", "gear_distance",
        )):
            continue

        attrs = dict(state.attributes)
        provider = _provider_domain(hass, entry)

        # Provider entities often expose the activity directly as attributes.
        if any(token in label for token in (
            "last_activity", "latest_activity", "activity",
            "last_workout", "latest_workout",
        )):
            candidate = _extract_record(
                attrs,
                source=entry.entity_id,
                provider_domain=provider,
                source_state=state,
            )
            if candidate:
                if candidate.name is None and _valid(state.state):
                    candidate.name = str(state.state)
                workouts.append(candidate)

        # Also inspect nested/list data contracts (Garmin last_activities,
        # Oura workouts, Polar exercises, etc.).
        for raw in _activity_dicts(attrs):
            candidate = _extract_record(
                raw,
                source=entry.entity_id,
                provider_domain=provider,
            )
            if candidate:
                workouts.append(candidate)

    return workouts


def _bundle_sibling_entities(
    hass: HomeAssistant,
    config: dict,
) -> list[Workout]:
    """Parse providers that split the last workout across sibling sensors.

    This directly supports Hevy-style layouts and gives similar integrations a
    generic path without provider-specific code.
    """
    device_ids = set(config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    registry = er.async_get(hass)
    result: list[Workout] = []

    by_device: dict[str, list] = {}
    for entry in registry.entities.values():
        if (
            entry.device_id in device_ids
            and entry.entity_id.startswith("sensor.")
        ):
            by_device.setdefault(entry.device_id, []).append(entry)

    for device_id, entries in by_device.items():
        values: dict[str, tuple[Any, Any, str]] = {}
        provider = "unknown"

        for entry in entries:
            state = hass.states.get(entry.entity_id)
            if state is None or state.state in ("unknown", "unavailable"):
                continue
            provider = _provider_domain(hass, entry)
            label = _norm_key(
                f"{entry.entity_id} {entry.name or ''} "
                f"{entry.original_name or ''}"
            )
            values[label] = (
                state.state,
                state.attributes,
                entry.entity_id,
            )

        def find_value(*tokens):
            for label, item in values.items():
                if all(_norm_key(token) in label for token in tokens):
                    return item
            return None

        start_item = (
            find_value("last", "workout", "start")
            or find_value("last", "activity", "start")
            or find_value("workout", "date")
        )
        title_item = (
            find_value("last", "workout")
            or find_value("last", "activity")
        )

        if start_item is None:
            continue

        start_dt = _dt(start_item[0])
        if start_dt is None:
            continue

        raw: dict[str, Any] = {
            "start": start_dt.isoformat(),
        }
        source = start_item[2]

        if title_item is not None:
            raw["name"] = title_item[0]
            source = title_item[2]
            attrs = title_item[1] or {}
            for key in ("exercise_count", "total_reps", "volume_kg"):
                if key in attrs:
                    raw[key] = attrs[key]

        sibling_map = {
            ("last", "workout", "duration"): "duration_minutes",
            ("last", "workout", "volume"): "volume_kg",
            ("last", "activity", "duration"): "duration_s",
            ("last", "activity", "distance"): "distance_m",
            ("last", "activity", "calories"): "calories",
        }
        for tokens, key in sibling_map.items():
            item = find_value(*tokens)
            if item is not None:
                raw[key] = item[0]

        # Normalize explicit duration_minutes before generic extractor.
        if "duration_minutes" in raw:
            raw["duration_s"] = _num(raw.pop("duration_minutes")) * 60.0

        candidate = _extract_record(
            raw,
            source=source,
            provider_domain=provider,
        )
        if candidate:
            result.append(candidate)

    return result


def discover_external_workouts(
    hass: HomeAssistant,
    config: dict,
) -> list[Workout]:
    """Discover completed workouts from all selected workout-source devices."""
    candidates = (
        _generic_activity_entities(hass, config)
        + _bundle_sibling_entities(hass, config)
    )

    # De-duplicate identical parses from the same source/list entity.
    seen = set()
    unique = []
    for workout in candidates:
        key = (
            workout.source,
            workout.start,
            workout.name,
            workout.sport,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(workout)

    return unique


def _sport_key(value: str | None) -> str:
    text = _norm_key(value or "workout")
    aliases = {
        "run": "running",
        "virtualrun": "running",
        "trailrun": "running",
        "ride": "cycling",
        "virtualride": "cycling",
        "mountainbikeride": "cycling",
        "gravelride": "cycling",
        "ebikeride": "cycling",
        "weighttraining": "strength",
        "strengthtraining": "strength",
        "workout": "workout",
    }
    return aliases.get(text, text or "workout")


def workout_identity(workout: Workout) -> tuple[str, int] | None:
    dt = _dt(workout.start)
    if dt is None:
        return None
    return (_sport_key(workout.sport), int(dt.timestamp()) // 300)


def _same_real_workout(a: Workout, b: Workout) -> bool:
    adt = _dt(a.start)
    bdt = _dt(b.start)
    if adt is None or bdt is None:
        return False

    # Same activity should start within five minutes. Sport mismatch is tolerated
    # when one provider only says generic "workout".
    if abs((adt - bdt).total_seconds()) > 300:
        return False

    sa = _sport_key(a.sport)
    sb = _sport_key(b.sport)
    return sa == sb or "workout" in (sa, sb) or not sa or not sb


def _richness(workout: Workout) -> int:
    score = 0
    for f in fields(Workout):
        if f.name in (
            "source", "sources", "provider_domains",
            "field_sources", "provider_values", "extra",
        ):
            continue
        if getattr(workout, f.name) is not None:
            score += 1
    score += min(len(workout.extra), 10)
    return score


def merge_workouts(group: list[Workout]) -> Workout:
    """Merge all representations of one physical workout without losing data."""
    ordered = sorted(group, key=_richness, reverse=True)
    primary = ordered[0]

    merged = Workout(
        source=primary.source,
        sources=[],
        provider_domains=[],
        provider_values={},
        field_sources={},
        extra={},
    )

    scalar_fields = [
        f.name for f in fields(Workout)
        if f.name not in (
            "source", "sources", "provider_domains",
            "field_sources", "provider_values", "extra",
        )
    ]

    for workout in ordered:
        if workout.source not in merged.sources:
            merged.sources.append(workout.source)
        for domain in workout.provider_domains:
            if domain not in merged.provider_domains:
                merged.provider_domains.append(domain)

        for domain, data in workout.provider_values.items():
            merged.provider_values.setdefault(domain, {}).update(data)

        for key, value in workout.extra.items():
            namespaced = f"{workout.provider_domains[0] if workout.provider_domains else 'provider'}.{key}"
            merged.extra.setdefault(namespaced, value)

        for field_name in scalar_fields:
            value = getattr(workout, field_name)
            if value is None:
                continue

            current = getattr(merged, field_name)
            provider = (
                workout.provider_domains[0]
                if workout.provider_domains else workout.source
            )

            # Keep first (richest provider) as canonical, but retain all
            # disagreements in provider_values + field_sources.
            if current is None:
                setattr(merged, field_name, value)
                merged.field_sources[field_name] = provider
            elif current != value:
                merged.provider_values.setdefault(
                    provider, {}
                )[f"normalized_{field_name}"] = value

    merged.source = (
        merged.sources[0]
        if len(merged.sources) == 1
        else "merged:" + ",".join(merged.provider_domains or merged.sources)
    )
    return merged


def merged_workouts(workouts: list[Workout]) -> list[Workout]:
    """Cluster candidates into physical workouts and merge each cluster."""
    groups: list[list[Workout]] = []

    for workout in sorted(
        workouts,
        key=lambda w: _dt(w.start) or datetime.min.replace(tzinfo=timezone.utc),
    ):
        placed = False
        for group in groups:
            if any(_same_real_workout(workout, existing) for existing in group):
                group.append(workout)
                placed = True
                break
        if not placed:
            groups.append([workout])

    return [merge_workouts(group) for group in groups]


def newest(workouts: list[Workout]) -> Workout | None:
    merged = merged_workouts(workouts)

    def key(w: Workout):
        return _dt(w.start) or datetime.min.replace(tzinfo=timezone.utc)

    return max(merged, key=key) if merged else None
