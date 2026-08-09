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

        raw = {
            "name": attrs.get("sport") or "Polar exercise",
            "sport": attrs.get("sport"),
            "start": state_value,
            "duration_s": duration_seconds(attrs.get("duration")),
            "distance_m": attrs.get("distance"),
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "calories": attrs.get("calories"),
            "training_load": attrs.get("training_load"),
            "device_name": attrs.get("device"),
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
            result.append(workout)

    return result
