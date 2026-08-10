"""Extract long-term fitness/recovery metrics from selected workout devices."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..const import CONF_WORKOUT_DEVICE_IDS


def _num(value: Any) -> float | None:
    try:
        if value is None or value in ("unknown", "unavailable", ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _state(hass: HomeAssistant, entity_id: str):
    return hass.states.get(entity_id)


def _find_by_tokens(hass: HomeAssistant, config: dict, tokens: tuple[str, ...]):
    device_ids = set(config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    registry = er.async_get(hass)
    matches = []
    for entry in registry.entities.values():
        if entry.device_id not in device_ids:
            continue
        text = " ".join(
            (
                entry.entity_id,
                entry.name or "",
                entry.original_name or "",
            )
        ).lower()
        if all(token in text for token in tokens):
            state = _state(hass, entry.entity_id)
            if state is not None:
                matches.append((entry.entity_id, state))
    return matches


def _first_numeric(hass: HomeAssistant, config: dict, *token_sets):
    for tokens in token_sets:
        for entity_id, state in _find_by_tokens(hass, config, tokens):
            value = _num(state.state)
            if value is not None:
                return value, entity_id, dict(state.attributes)
    return None, None, {}


def _first_state(hass: HomeAssistant, config: dict, *token_sets):
    for tokens in token_sets:
        for entity_id, state in _find_by_tokens(hass, config, tokens):
            if state.state not in ("unknown", "unavailable", "", None):
                return state.state, entity_id, dict(state.attributes)
    return None, None, {}


def collect_provider_metrics(hass: HomeAssistant, config: dict) -> dict:
    """Return normalized long-term metrics from all selected workout devices."""
    result: dict[str, Any] = {}

    mappings = {
        "vo2max": (
            ("vo2_max",),
            ("vo2", "max"),
        ),
        "resting_hr": (
            ("resting_heart_rate",),
            ("resting", "heart"),
        ),
        "weight_kg": (
            ("weight",),
        ),
        "hrv_weekly": (
            ("hrv_weekly_average",),
            ("hrv", "weekly"),
        ),
        "hrv_last_night": (
            ("hrv_last_night_average",),
            ("hrv", "last_night"),
        ),
        "fitness_age": (
            ("fitness_age",),
        ),
        "threshold_hr": (
            ("lactate_threshold_heart_rate",),
            ("threshold", "heart"),
        ),
        "threshold_speed": (
            ("lactate_threshold_speed",),
            ("threshold", "speed"),
        ),
        "ftp_running": (
            ("ftp_running",),
            ("ftp", "running"),
        ),
        "power_to_weight_running": (
            ("power_to_weight_running",),
            ("power_to_weight", "running"),
        ),
        "training_readiness": (
            ("training_readiness",),
        ),
        "sleep_score": (
            ("sleep_score",),
        ),
    }

    for key, token_sets in mappings.items():
        value, entity_id, attrs = _first_numeric(hass, config, *token_sets)
        if value is not None:
            result[key] = value
            result[f"{key}_entity"] = entity_id
            result[f"{key}_attrs"] = attrs

    hrv_state, hrv_entity, hrv_attrs = _first_state(
        hass, config, ("hrv_status",)
    )
    if hrv_state is not None:
        result["hrv_provider_status"] = hrv_state
        result["hrv_provider_status_entity"] = hrv_entity
        baseline = hrv_attrs.get("baseline")
        if isinstance(baseline, dict):
            result["hrv_baseline_low"] = _num(
                baseline.get("balancedLow") or baseline.get("balanced_low")
            )
            result["hrv_baseline_high"] = _num(
                baseline.get("balancedUpper") or baseline.get("balanced_upper")
            )
        else:
            result["hrv_baseline_low"] = _num(
                hrv_attrs.get("balancedLow") or hrv_attrs.get("balanced_low")
            )
            result["hrv_baseline_high"] = _num(
                hrv_attrs.get("balancedUpper") or hrv_attrs.get("balanced_upper")
            )

    status, entity_id, attrs = _first_state(
        hass, config, ("training_status",)
    )
    if status is not None:
        result["provider_training_status"] = status
        result["provider_training_status_entity"] = entity_id

        # Garmin currently nests acute/chronic load in training-status attributes.
        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield str(k), v
                    yield from walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    yield from walk(v)

        flat = list(walk(attrs))
        for key, value in flat:
            low = key.lower()
            if low == "dailytrainingloadacute":
                result["acute_load"] = _num(value)
            elif low == "dailytrainingloadchronic":
                result["chronic_load"] = _num(value)
            elif low == "dailyacutechronicworkloadratio":
                result["acute_chronic_ratio"] = _num(value)

    return result


def workout_device_entity_ids(hass: HomeAssistant, config: dict) -> list[str]:
    """Return entities capable of signalling a completed-workout change.

    Do not subscribe to every sensor belonging to a selected workout device.
    Large provider devices such as Garmin Connect can expose hundreds of
    frequently changing wellness sensors. Those updates are unrelated to
    completed workouts and must not wake the Fitness workout-discovery path.
    """
    device_ids = set(config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    registry = er.async_get(hass)

    trigger_tokens = (
        "activity",
        "activities",
        "workout",
        "workouts",
        "exercise",
        "exercises",
        "session",
        "sessions",
    )

    excluded_tokens = (
        "scheduled",
        "planned",
        "next_workout",
        "workout_plan",
        "route",
        "polyline",
        "gear_distance",
    )

    result: set[str] = set()

    for entry in registry.entities.values():
        if entry.device_id not in device_ids:
            continue
        if not entry.entity_id.startswith("sensor."):
            continue

        label = " ".join(
            (
                entry.entity_id,
                entry.name or "",
                entry.original_name or "",
            )
        ).lower().replace(" ", "_").replace("-", "_")

        if any(token in label for token in excluded_tokens):
            continue

        if any(token in label for token in trigger_tokens):
            result.add(entry.entity_id)

    return sorted(result)
