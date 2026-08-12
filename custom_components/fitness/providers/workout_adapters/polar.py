"""Polar AccessLink completed-workout adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import (
    duration_seconds,
    entry_label,
    entity_value,
    finite_number,
    selected_sensor_entries,
)
from ..workouts import _extract_record

DOMAINS = ("polar",)


def _heart_rate_fields(value):
    if isinstance(value, dict):
        return (
            value.get("average")
            or value.get("avg")
            or value.get("average_heart_rate"),
            value.get("maximum")
            or value.get("max")
            or value.get("max_heart_rate"),
        )
    return value, None


def _polar_session_rpe(attrs: dict, duration_s: float | None) -> int | None:
    """Extract Polar's documented 1-10 session RPE when AccessLink exposes it."""
    load = attrs.get("training_load_pro") or attrs.get("training-load-pro")
    if not isinstance(load, dict):
        return None

    raw = load.get("user_rpe", load.get("user-rpe"))
    numeric = finite_number(raw)
    if numeric is not None and 1 <= numeric <= 10:
        return max(1, min(10, int(round(numeric))))

    # AccessLink can expose user-rpe as an enum while also exposing Perceived
    # Load. Polar documents Perceived Load = RPE x duration_minutes, so derive
    # the exact 1-10 rating from those two fields instead of guessing enum labels.
    perceived = finite_number(load.get("perceived_load", load.get("perceived-load")))
    if perceived is not None and duration_s and duration_s > 0:
        candidate = perceived / (duration_s / 60.0)
        if 1 <= candidate <= 10:
            return max(1, min(10, int(round(candidate))))
    return None


def _tag_rpe_capability(workout):
    meta = workout.extra.setdefault("fitness_rpe", {})
    meta.setdefault("provider", "polar")
    meta.setdefault("provider_capability", "user_session_rpe_1_10")
    return workout


def discover(hass: HomeAssistant, config: dict) -> list:
    """Parse Polar's Last exercise sensor.

    Upstream exposes start_time as state and distance, duration, heart_rate,
    training_load, sport, calories, running_index and device as attributes.
    """
    result = []

    for entry in selected_sensor_entries(
        hass,
        config,
        domains=DOMAINS,
    ):
        if "last_exercise" not in entry_label(hass, entry):
            continue

        state_value, attrs, _unit = entity_value(hass, entry)
        if state_value is None:
            continue

        avg_hr, max_hr = _heart_rate_fields(attrs.get("heart_rate"))
        duration_s = duration_seconds(attrs.get("duration"))

        raw = {
            "name": attrs.get("sport") or "Polar exercise",
            "sport": attrs.get("sport"),
            "start": state_value,
            "duration_s": duration_s,
            "distance_m": attrs.get("distance"),
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "calories": attrs.get("calories"),
            "training_load": attrs.get("training_load"),
            "session_rpe": _polar_session_rpe(attrs, duration_s),
            "device_name": attrs.get("device"),
            "training_load_pro": attrs.get("training_load_pro") or attrs.get("training-load-pro"),
            # Keep Polar-specific performance metrics as provider data.
            "running_index": attrs.get("running_index"),
        }

        workout = _extract_record(
            raw,
            source=entry.entity_id,
            provider_domain="polar",
        )
        if workout:
            workout.extra["fitness_adapter"] = "polar"
            _tag_rpe_capability(workout)
            result.append(workout)

    return result
