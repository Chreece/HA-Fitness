"""Garmin Connect completed-workout adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import entry_label, entity_value, selected_sensor_entries
from ..workouts import _activity_dicts, _extract_record, _valid

DOMAINS = ("garmin_connect",)


def _tag_rpe_capability(workout):
    """Record that Garmin supports user-entered 1-10 session RPE upstream."""
    meta = workout.extra.setdefault("fitness_rpe", {})
    meta.setdefault("provider", "garmin_connect")
    meta.setdefault("provider_capability", "user_session_rpe_1_10")
    return workout


def discover(hass: HomeAssistant, config: dict) -> list:
    """Read Garmin's Last Activity and Last Activities contracts."""
    result = []

    for entry in selected_sensor_entries(
        hass,
        config,
        domains=DOMAINS,
    ):
        state_value, attrs, _unit = entity_value(hass, entry)
        if state_value is None:
            continue

        label = entry_label(hass, entry)

        if "last_activities" in label:
            for raw in _activity_dicts(attrs):
                workout = _extract_record(
                    raw,
                    source=entry.entity_id,
                    provider_domain="garmin_connect",
                )
                if workout:
                    workout.extra.setdefault(
                        "fitness_adapter",
                        "garmin",
                    )
                    _tag_rpe_capability(workout)
                    result.append(workout)
            continue

        if "last_activity" in label:
            workout = _extract_record(
                attrs,
                source=entry.entity_id,
                provider_domain="garmin_connect",
                source_state=hass.states.get(entry.entity_id),
            )
            if workout:
                if workout.name is None and _valid(state_value):
                    workout.name = str(state_value)
                workout.extra.setdefault("fitness_adapter", "garmin")
                _tag_rpe_capability(workout)
                result.append(workout)

            for raw in _activity_dicts(attrs):
                nested = _extract_record(
                    raw,
                    source=entry.entity_id,
                    provider_domain="garmin_connect",
                )
                if nested:
                    nested.extra.setdefault("fitness_adapter", "garmin")
                    _tag_rpe_capability(nested)
                    result.append(nested)

    return result
