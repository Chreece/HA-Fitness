"""Provider-independent completed-workout discovery and merging."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta, timezone
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
        "activityType", "activity_type", "sport", "sport_type", "sportType",
        "type", "workout_type", "workoutType",
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
    "session_rpe": (
        "rpe", "RPE", "session_rpe", "sessionRpe",
        "ratingOfPerceivedExertion", "rating_of_perceived_exertion",
        "perceivedEffort", "perceived_effort",
        "perceivedExertion", "perceived_exertion",
        "activityRPE", "activity_rpe",
        "directWorkoutRpe", "direct_workout_rpe",
        "selfEvaluation", "self_evaluation",
    ),
    "kilojoules": ("kilojoules", "kJ", "kj"),
    "total_reps": ("total_reps", "totalReps", "reps"),
    "exercise_count": ("exercise_count", "exerciseCount"),
    "volume_kg": ("volume_kg", "volumeKg", "total_volume", "volume"),
    "start_latitude": (
        "startLatitude", "start_latitude", "startLat", "start_lat",
        "startingLatitude", "starting_latitude",
    ),
    "start_longitude": (
        "startLongitude", "start_longitude", "startLon", "startLng",
        "start_lon", "start_lng", "startingLongitude", "starting_longitude",
    ),
    "device_name": (
        "device_name", "deviceName", "device", "source_device",
    ),
    "gear_name": (
        "gear_name", "gearName", "gear", "gear_id", "gearId",
    ),
}


FITNESS_LIVE_SOURCE = "fitness_live_capture"
FITNESS_CALCULATED_SOURCE = "fitness_calculated"


def workout_is_fitness_owned(workout: "Workout | None") -> bool:
    """Return whether Fitness itself created the physical workout record.

    Provider/watch records may later enrich a live-captured workout. Ownership
    must survive every merge/canonicalization pass, so the original live source
    is checked transitively through ``sources`` rather than relying on the
    synthetic current ``source`` value (for example ``merged:garmin``).
    """
    if workout is None:
        return False
    return (
        workout.source == FITNESS_LIVE_SOURCE
        or FITNESS_LIVE_SOURCE in (workout.sources or [])
        or FITNESS_LIVE_SOURCE in (workout.provider_values or {})
        or FITNESS_LIVE_SOURCE in set((workout.field_sources or {}).values())
        # ``sample_count`` is written only by Fitness Live capture. It also
        # lets this release repair ownership for canonical records produced by
        # older merge code that already dropped the original source list.
        or workout.sample_count is not None
    )


def fitness_owned_workout_value(workout: "Workout | None", field_name: str):
    """Return the value Fitness itself captured/owned for one workout field.

    A canonical workout can be enriched by Garmin/Strava/etc. The canonical
    value may therefore belong to an upstream provider. Fitness-owned HA
    entities must never mirror that provider value. During merge we retain the
    normalized live-capture value under ``provider_values`` so the original
    Fitness measurement remains available even after provider enrichment.
    """
    if not workout_is_fitness_owned(workout):
        return None
    assert workout is not None

    # The canonical title is identity metadata for the Fitness-owned workout.
    # It may be improved by a provider after matching without turning the
    # underlying workout into an externally owned record.
    if field_name == "name":
        return workout.name or workout.sport or "Workout"

    if field_name == "session_rpe":
        meta = (workout.extra or {}).get("fitness_rpe")
        if isinstance(meta, dict) and meta.get("active_source") == "user_override":
            return workout.session_rpe

    live_values = (workout.provider_values or {}).get(FITNESS_LIVE_SOURCE)
    if isinstance(live_values, dict):
        key = f"normalized_{field_name}"
        if key in live_values:
            return live_values[key]

    source = (workout.field_sources or {}).get(field_name)
    if source in {FITNESS_LIVE_SOURCE, FITNESS_CALCULATED_SOURCE}:
        return getattr(workout, field_name, None)
    if workout.source == FITNESS_LIVE_SOURCE:
        return getattr(workout, field_name, None)
    return None


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
    session_rpe: float | None = None
    session_rpe_load: float | None = None
    session_rpe_load_vs_28d_percent: float | None = None
    fitness_aerobic_load: float | None = None
    fitness_high_intensity_load: float | None = None
    strength_total_sets: float | None = None
    strength_best_estimated_1rm_kg: float | None = None
    strength_progression_percent: float | None = None
    kilojoules: float | None = None
    total_reps: float | None = None
    exercise_count: float | None = None
    volume_kg: float | None = None
    start_latitude: float | None = None
    start_longitude: float | None = None
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

    # Personal longitudinal comparison. These fields never replace the factual
    # workout measurements above; they describe the session relative to the
    # user's own historical baseline.
    comparable_workout_count: int | None = None
    efficiency_vs_baseline_percent: float | None = None
    decoupling_vs_baseline_percent: float | None = None
    avg_hr_vs_baseline_bpm: float | None = None
    avg_power_vs_baseline_percent: float | None = None
    avg_speed_vs_baseline_percent: float | None = None
    trimp_vs_recent_mean_percent: float | None = None
    load_context: str | None = None
    personal_context_summary: str | None = None

    # Merge/provenance fields.
    sources: list[str] = field(default_factory=list)
    provider_domains: list[str] = field(default_factory=list)
    field_sources: dict[str, str] = field(default_factory=dict)
    provider_values: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        """Serialize without recursively deep-copying provider payloads.

        ``dataclasses.asdict`` recursively walks every nested value. Workout
        provenance may contain large provider dictionaries/lists, so doing that
        for every historical workout can monopolize Home Assistant's MainThread.
        Workout instances are treated as immutable snapshots after merge; shallow
        copies of their top-level containers are sufficient for persistent state.
        """
        result: dict[str, Any] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, dict):
                if item.name == "provider_values":
                    result[item.name] = {
                        str(key): dict(nested) if isinstance(nested, dict) else nested
                        for key, nested in value.items()
                    }
                else:
                    result[item.name] = dict(value)
            elif isinstance(value, list):
                result[item.name] = list(value)
            else:
                result[item.name] = value
        return result


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


# Providers/adapters with a documented user-entered *session* RPE.
# This intentionally excludes algorithmic strain/load scores and per-set RPE.
SESSION_RPE_PROVIDER_CAPABILITIES = {
    "garmin_connect": "user_session_rpe_1_10",
    "polar": "user_session_rpe_1_10",
}


def session_rpe_provider_capability(provider_domain: str | None) -> str | None:
    """Return documented session-RPE capability for a provider domain."""
    return SESSION_RPE_PROVIDER_CAPABILITIES.get(str(provider_domain or ""))


def _normalize_session_rpe(value: Any, key: str | None = None) -> int | None:
    """Normalize a genuine session RPE to Fitness' integer 1-10 scale.

    Garmin Connect data seen in third-party clients may expose directWorkoutRpe
    on a 0-100 representation (70 means 7/10).  Other explicit RPE fields are
    expected to be on a 1-10 scale.  Nested self-evaluation objects are also
    supported.  We never reinterpret provider strain/training-effect scores as
    subjective RPE.
    """
    if isinstance(value, dict):
        preferred = (
            "directWorkoutRpe", "direct_workout_rpe",
            "perceivedEffort", "perceived_effort",
            "perceivedExertion", "perceived_exertion",
            "ratingOfPerceivedExertion", "rating_of_perceived_exertion",
            "sessionRpe", "session_rpe", "rpe", "RPE",
        )
        normalized = {_norm_key(k): (k, v) for k, v in value.items()}
        for candidate in preferred:
            item = normalized.get(_norm_key(candidate))
            if item is None:
                continue
            result = _normalize_session_rpe(item[1], item[0])
            if result is not None:
                return result
        return None

    numeric = _num(value)
    if numeric is None:
        return None

    key_norm = _norm_key(key or "")
    if "directworkoutrpe" in key_norm and 10 < numeric <= 100:
        numeric /= 10.0

    if not 1 <= numeric <= 10:
        return None
    return max(1, min(10, int(round(numeric))))


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


_SPORT_ALIASES = {
    "run": "running",
    "running": "running",
    "trail_run": "running",
    "trail_running": "running",
    "treadmill_running": "running",
    "treadmill_run": "running",
    "jog": "running",
    "jogging": "running",
    "cycling": "cycling",
    "bike": "cycling",
    "biking": "cycling",
    "ride": "cycling",
    "swimming": "swimming",
    "swim": "swimming",
    "walking": "walking",
    "walk": "walking",
    "hiking": "hiking",
    "hike": "hiking",
    "strength_training": "strength",
    "strength": "strength",
    "weight_training": "strength",
}


def _sport_token(value: Any) -> str | None:
    """Extract a canonical sport token, including nested provider objects."""
    if value is None:
        return None
    if isinstance(value, dict):
        preferred = (
            "sportTypeKey", "sport_type_key", "activityTypeKey",
            "activity_type_key", "typeKey", "type_key", "key",
            "sport", "activityType", "activity_type", "name",
        )
        for key in preferred:
            if key in value and (token := _sport_token(value[key])):
                return token
        for nested in value.values():
            if isinstance(nested, (dict, list, tuple)) and (token := _sport_token(nested)):
                return token
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            if (token := _sport_token(item)):
                return token
        return None

    text = str(value).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if normalized in _SPORT_ALIASES:
        return _SPORT_ALIASES[normalized]
    for alias, canonical in _SPORT_ALIASES.items():
        if re.search(rf"(?:^|_){re.escape(alias)}(?:_|$)", normalized):
            return canonical
    return normalized or None


def workout_sport_kind(workout: "Workout | None") -> str | None:
    """Infer sport from the already-merged normalized Fitness workout."""
    if workout is None:
        return None
    if (sport := _sport_token(workout.sport)) in set(_SPORT_ALIASES.values()):
        return sport

    # Provider data remains provenance, but is useful for classifying the
    # physical workout when a provider nests sport metadata (Garmin:
    # sportType -> sportTypeKey -> running).
    for container in (workout.provider_values, workout.extra):
        if isinstance(container, dict):
            stack = [container]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    for key, value in item.items():
                        key_norm = re.sub(r"[^a-z0-9]+", "", str(key).lower())
                        if key_norm in {
                            "sport", "sporttype", "sporttypekey",
                            "activitytype", "activitytypekey",
                            "workouttype", "workouttypekey",
                        }:
                            token = _sport_token(value)
                            if token in set(_SPORT_ALIASES.values()):
                                return token
                        if isinstance(value, (dict, list, tuple)):
                            stack.append(value)
                elif isinstance(item, (list, tuple)):
                    stack.extend(item)

    # Last conservative fallback: workout title/name. This helps integrations
    # that expose "Morning Run" but no explicit sport field.
    if workout.name:
        token = _sport_token(workout.name)
        if token in set(_SPORT_ALIASES.values()):
            return token
    return None


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

        if field_name == "sport":
            # Preserve simple provider sport values verbatim for provenance and
            # compatibility. Only unwrap structured/nested provider objects
            # (for example Garmin sportType.sportTypeKey).
            kwargs[field_name] = (
                (_sport_token(value) or str(value))
                if isinstance(value, (dict, list, tuple))
                else str(value)
            )
        elif field_name in ("name", "training_effect_label", "device_name", "gear_name"):
            kwargs[field_name] = str(value)
        elif field_name == "end":
            end_dt = _dt(value)
            kwargs[field_name] = end_dt.isoformat() if end_dt else None
        elif field_name in ("duration_s", "moving_time_s", "elapsed_time_s"):
            kwargs[field_name] = _normalize_duration(value, matched_key)
        elif field_name == "session_rpe":
            kwargs[field_name] = _normalize_session_rpe(value, matched_key)
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

    if kwargs.get("session_rpe") is not None:
        extra["fitness_rpe"] = {
            "active_source": "provider",
            "provider": provider_domain,
            "provider_capability": session_rpe_provider_capability(provider_domain),
            "normalized_rpe": int(round(kwargs["session_rpe"])),
        }
    elif (capability := session_rpe_provider_capability(provider_domain)) is not None:
        extra["fitness_rpe"] = {
            "active_source": "missing_provider_value",
            "provider": provider_domain,
            "provider_capability": capability,
        }

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
    *,
    exclude_domains: set[str] | None = None,
    only_domains: set[str] | None = None,
    only_device_ids: set[str] | None = None,
) -> list[Workout]:
    """Parse activity-like entities from any selected workout device."""
    device_ids = set(config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    registry = er.async_get(hass)
    workouts: list[Workout] = []

    for entry in registry.entities.values():
        if entry.device_id not in device_ids:
            continue
        if only_device_ids is not None and entry.device_id not in only_device_ids:
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
        if exclude_domains and provider in exclude_domains:
            continue
        if only_domains is not None and provider not in only_domains:
            continue

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
    *,
    exclude_domains: set[str] | None = None,
    only_domains: set[str] | None = None,
    only_device_ids: set[str] | None = None,
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
        if entry.device_id not in device_ids:
            continue
        if only_device_ids is not None and entry.device_id not in only_device_ids:
            continue
        if not entry.entity_id.startswith("sensor."):
            continue
        by_device.setdefault(entry.device_id, []).append(entry)

    for device_id, entries in by_device.items():
        values: dict[str, tuple[Any, Any, str]] = {}
        provider = "unknown"

        for entry in entries:
            state = hass.states.get(entry.entity_id)
            if state is None or state.state in ("unknown", "unavailable"):
                continue
            provider = _provider_domain(hass, entry)
            if exclude_domains and provider in exclude_domains:
                continue
            if only_domains is not None and provider not in only_domains:
                continue
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
    """Discover completed workouts through explicit + generic adapters."""
    # Imported lazily to keep Workout/_extract_record available to adapter
    # modules without creating a module-import cycle.
    from .workout_adapters.registry import discover_all

    candidates = discover_all(hass, config)

    # De-duplicate identical adapter parses, keeping the richest representation.
    unique: dict[tuple, Workout] = {}
    for workout in candidates:
        key = (
            workout.source,
            workout.start,
            workout.name,
            workout.sport,
        )
        current = unique.get(key)
        if current is None or _richness(workout) > _richness(current):
            unique[key] = workout

    return list(unique.values())


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
    """Return a coarse identity useful for diagnostics, not merge decisions."""
    dt = _dt(workout.start)
    if dt is None:
        return None
    # One-minute buckets are deliberately finer than the old five-minute
    # bucket. Actual merging uses _same_real_workout() below.
    return (_sport_key(workout.sport), int(dt.timestamp()) // 60)


def _sports_compatible(a: Workout, b: Workout) -> bool:
    """Require compatible sports while treating live-capture inference as provisional.

    A Fitness live capture may begin with only HR/general sensors. Its temporary
    sport label must never block a later authoritative watch/provider record for
    the same physical workout from merging. Time/duration/end evidence still has
    to pass the normal conservative workout matching rules.
    """
    sa = _sport_key(a.sport)
    sb = _sport_key(b.sport)

    if sa == sb:
        return True

    generic = {"", "workout", "activity", "exercise", "session"}
    if sa in generic or sb in generic:
        return True

    a_live = workout_is_fitness_owned(a)
    b_live = workout_is_fitness_owned(b)
    return a_live != b_live


def _relative_difference(
    a: float | None,
    b: float | None,
) -> float | None:
    if a is None or b is None:
        return None
    try:
        av = abs(float(a))
        bv = abs(float(b))
    except (TypeError, ValueError):
        return None

    reference = max(av, bv)
    if reference <= 0:
        return 0.0 if av == bv else None
    return abs(av - bv) / reference


def _duration_compatible(a: Workout, b: Workout) -> bool | None:
    """Compare duration when both providers expose it.

    Returns:
      True  -> compatible
      False -> hard conflict
      None  -> insufficient data
    """
    if a.duration_s is None or b.duration_s is None:
        return None

    da = float(a.duration_s)
    db = float(b.duration_s)
    difference = abs(da - db)
    reference = max(abs(da), abs(db), 1.0)

    # Provider elapsed/moving-time semantics commonly differ slightly.
    # Permit 2 minutes or 8%, whichever is larger.
    tolerance = max(120.0, reference * 0.08)
    return difference <= tolerance


def _distance_compatible(a: Workout, b: Workout) -> bool | None:
    """Compare distance when both providers expose it."""
    if a.distance_m is None or b.distance_m is None:
        return None

    da = float(a.distance_m)
    db = float(b.distance_m)
    # Provider placeholders such as 0 km mean "not recorded", not a hard
    # contradiction against a live sensor that did record distance.
    if da <= 0 or db <= 0:
        return None
    difference = abs(da - db)
    reference = max(abs(da), abs(db), 1.0)

    # GPS/platform processing can differ. Keep this conservative:
    # 250 metres or 5%, whichever is larger.
    tolerance = max(250.0, reference * 0.05)
    return difference <= tolerance


def _end_time_compatible(a: Workout, b: Workout) -> bool | None:
    """Compare explicit end timestamps when both providers expose them."""
    if not a.end or not b.end:
        return None
    adt = _dt(a.end)
    bdt = _dt(b.end)
    if adt is None or bdt is None:
        return None
    return abs((adt - bdt).total_seconds()) <= 180


def _same_real_workout(a: Workout, b: Workout) -> bool:
    """Conservatively decide whether two records describe one physical workout.

    Matching is intentionally asymmetric in evidence:
    - start times farther apart require stronger supporting agreement
    - explicit contradictions in sport/duration/distance/end time reject a merge
    - two records with almost identical start times can still merge when one
      provider exposes little detail
    """
    adt = _dt(a.start)
    bdt = _dt(b.start)
    if adt is None or bdt is None:
        return False

    start_delta = abs((adt - bdt).total_seconds())

    # Never merge records whose reported starts differ by more than 5 minutes.
    if start_delta > 300:
        return False

    # Distinct known sports are a hard conflict.
    if not _sports_compatible(a, b):
        return False

    duration_match = _duration_compatible(a, b)
    distance_match = _distance_compatible(a, b)
    end_match = _end_time_compatible(a, b)

    a_live = workout_is_fitness_owned(a)
    b_live = workout_is_fitness_owned(b)
    # A live capture and a watch/provider activity starting within 90 seconds are
    # overwhelmingly likely to be two views of the same physical session.
    # Provider duration semantics can differ (elapsed vs moving vs live timer),
    # so start-time coincidence is intentionally stronger evidence for this pair.
    if a_live != b_live and start_delta <= 90 and distance_match is not False:
        return True

    # Any strong contradictory measurement rejects the merge.
    if duration_match is False:
        return False
    if distance_match is False:
        return False
    if end_match is False:
        return False

    supporting_matches = sum(
        value is True
        for value in (
            duration_match,
            distance_match,
            end_match,
        )
    )

    # Within 30 seconds, providers are close enough in start time that a
    # compatible sport is sufficient when richer fields are unavailable.
    if start_delta <= 30:
        return True

    # 30-90 seconds: require at least one agreeing independent characteristic.
    if start_delta <= 90:
        return supporting_matches >= 1

    # 90-180 seconds: require two independent agreements, unless only one of
    # duration/distance/end is jointly available and it agrees very strongly.
    if start_delta <= 180:
        if supporting_matches >= 2:
            return True

        available = [
            value
            for value in (
                duration_match,
                distance_match,
                end_match,
            )
            if value is not None
        ]
        if len(available) == 1 and available[0] is True:
            # The lone evidence must be tight, not just within normal tolerance.
            if a.duration_s is not None and b.duration_s is not None:
                diff = _relative_difference(a.duration_s, b.duration_s)
                return diff is not None and diff <= 0.02
            if a.distance_m is not None and b.distance_m is not None:
                diff = _relative_difference(a.distance_m, b.distance_m)
                return diff is not None and diff <= 0.02
        return False

    # 3-5 minutes is unusual for the same workout. Merge only with very strong
    # agreement in at least two independent characteristics.
    if supporting_matches < 2:
        return False

    tight_duration = True
    if a.duration_s is not None and b.duration_s is not None:
        diff = _relative_difference(a.duration_s, b.duration_s)
        tight_duration = diff is not None and diff <= 0.03

    tight_distance = True
    if a.distance_m is not None and b.distance_m is not None:
        diff = _relative_difference(a.distance_m, b.distance_m)
        tight_distance = diff is not None and diff <= 0.03

    return tight_duration and tight_distance


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
        # Preserve original provenance transitively. A previously canonicalized
        # merged workout has a synthetic ``source`` (``merged:...``) but its
        # ``sources`` list contains the real origins. Re-merging must never
        # collapse that list and lose ``fitness_live_capture`` ownership.
        provenance_sources = list(workout.sources or [])
        if not provenance_sources and workout.source:
            provenance_sources = [workout.source]
        if workout_is_fitness_owned(workout) and FITNESS_LIVE_SOURCE not in provenance_sources:
            provenance_sources.append(FITNESS_LIVE_SOURCE)
        for source in provenance_sources:
            if source not in merged.sources:
                merged.sources.append(source)
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
                (workout.field_sources or {}).get(field_name)
                or (workout.provider_domains[0] if workout.provider_domains else workout.source)
            )

            # Retain Fitness's own normalized live-capture facts even when an
            # external provider is richer/canonical. These values back only
            # Fitness-owned workout entities; they are never used to mirror an
            # upstream provider.
            if workout.source == FITNESS_LIVE_SOURCE:
                merged.provider_values.setdefault(FITNESS_LIVE_SOURCE, {})[
                    f"normalized_{field_name}"
                ] = value

            # Keep first (richest provider) as canonical, but retain all
            # disagreements in provider_values + field_sources.
            if current is None:
                setattr(merged, field_name, value)
                merged.field_sources[field_name] = provider
            elif current != value:
                merged.provider_values.setdefault(
                    provider, {}
                )[f"normalized_{field_name}"] = value

    # Promote the canonical RPE provenance out of namespaced provider extras so
    # the Workout card/number entity can show the provider value as its editable
    # base even after multiple provider representations were merged.
    rpe_provider = merged.field_sources.get("session_rpe")
    if merged.session_rpe is not None:
        for workout in ordered:
            provider = workout.provider_domains[0] if workout.provider_domains else workout.source
            if provider != rpe_provider or workout.session_rpe is None:
                continue
            meta = (workout.extra or {}).get("fitness_rpe") if isinstance(workout.extra, dict) else None
            if isinstance(meta, dict):
                merged.extra["fitness_rpe"] = dict(meta)
                break
        if "fitness_rpe" not in merged.extra:
            merged.extra["fitness_rpe"] = {
                "active_source": "provider",
                "provider": rpe_provider,
                "provider_capability": session_rpe_provider_capability(rpe_provider),
                "normalized_rpe": int(round(merged.session_rpe)),
            }
    else:
        for provider in merged.provider_domains:
            capability = session_rpe_provider_capability(provider)
            if capability is not None:
                merged.extra["fitness_rpe"] = {
                    "active_source": "missing_provider_value",
                    "provider": provider,
                    "provider_capability": capability,
                }
                break

    # When a live capture and a provider/watch representation describe the same
    # workout, provider identity fields are authoritative while Fitness-owned
    # calculated fields from the live capture remain available. This prevents a
    # provisional "Evening Workout/Ride" label from replacing an explicit
    # provider sport/name after sync.
    live_records = [item for item in ordered if workout_is_fitness_owned(item)]
    external_records = [item for item in ordered if item not in live_records]
    if live_records and external_records:
        explicit = next(
            (item for item in external_records if _sport_key(item.sport) not in {"", "workout", "activity", "exercise", "session"}),
            external_records[0],
        )
        if explicit.sport:
            merged.sport = explicit.sport
            merged.field_sources["sport"] = (
                explicit.provider_domains[0] if explicit.provider_domains else explicit.source
            )
        if explicit.name:
            merged.name = explicit.name
            merged.field_sources["name"] = (
                explicit.provider_domains[0] if explicit.provider_domains else explicit.source
            )

    # RPE has explicit precedence independent of generic richness: a user
    # override wins, otherwise an adapter/provider RPE is the editable base.
    rpe_candidates = []
    for item in ordered:
        if item.session_rpe is None:
            continue
        meta = item.extra.get("fitness_rpe") if isinstance(item.extra, dict) else None
        active_source = meta.get("active_source") if isinstance(meta, dict) else None
        priority = 3 if active_source == "user_override" else 2 if active_source == "provider" else 1
        rpe_candidates.append((priority, item))
    if rpe_candidates:
        _, chosen_rpe = max(rpe_candidates, key=lambda pair: pair[0])
        merged.session_rpe = int(round(float(chosen_rpe.session_rpe)))
        provider = chosen_rpe.provider_domains[0] if chosen_rpe.provider_domains else chosen_rpe.source
        merged.field_sources["session_rpe"] = provider
        meta = chosen_rpe.extra.get("fitness_rpe") if isinstance(chosen_rpe.extra, dict) else None
        if isinstance(meta, dict):
            merged.extra["fitness_rpe"] = dict(meta)

    merged.source = (
        merged.sources[0]
        if len(merged.sources) == 1
        else "merged:" + ",".join(merged.provider_domains or merged.sources)
    )
    return merged


def merged_workouts(workouts: list[Workout]) -> list[Workout]:
    """Cluster candidates into physical workouts and merge each cluster.

    Workout identity can never match when start times differ by more than five
    minutes. Keep only still-eligible groups in the comparison set instead of
    comparing every historical workout with every older group. This preserves
    complete-link clustering while making long histories approximately linear
    when sessions are separated in time.
    """
    groups: list[list[Workout]] = []
    active_groups: list[list[Workout]] = []

    for workout in sorted(
        workouts,
        key=lambda w: _dt(w.start) or datetime.min.replace(tzinfo=timezone.utc),
    ):
        current_start = _dt(workout.start)
        if current_start is None:
            # Records without a usable start can never match _same_real_workout.
            groups.append([workout])
            continue

        cutoff = current_start - timedelta(seconds=300)
        active_groups = [
            group
            for group in active_groups
            if (last_start := _dt(group[-1].start)) is not None
            and last_start >= cutoff
        ]

        placed = False
        for group in active_groups:
            # Complete-link clustering: a new record must agree with every
            # member already in the group. This prevents transitive chain
            # merges such as A≈B and B≈C accidentally merging A+B+C when A and
            # C are actually separate workouts.
            if all(
                _same_real_workout(workout, existing)
                for existing in group
            ):
                group.append(workout)
                placed = True
                break
        if not placed:
            group = [workout]
            groups.append(group)
            active_groups.append(group)

    return [merge_workouts(group) for group in groups]


def newest(workouts: list[Workout]) -> Workout | None:
    """Return the newest canonical workout without merging all history.

    A workout can only merge with another representation whose start is within
    five minutes. Therefore only the final five-minute window can possibly
    affect which canonical workout is newest; older records cannot merge into
    or overtake it.
    """
    dated = [(start, workout) for workout in workouts if (start := _dt(workout.start)) is not None]
    if not dated:
        return None

    latest_start = max(start for start, _workout in dated)
    cutoff = latest_start - timedelta(seconds=300)
    candidates = [workout for start, workout in dated if start >= cutoff]
    merged = merged_workouts(candidates)
    return max(
        merged,
        key=lambda w: _dt(w.start) or datetime.min.replace(tzinfo=timezone.utc),
    ) if merged else None
