"""Strava Home Assistant completed-workout adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import entry_label, entity_value, selected_sensor_entries
from ..workouts import _activity_dicts, _extract_record, _valid

DOMAINS = ("ha_strava", "strava")


def discover(hass: HomeAssistant, config: dict) -> list:
    """Parse latest-activity sensors created per selected Strava activity type."""
    result = []

    for entry in selected_sensor_entries(
        hass,
        config,
        domains=DOMAINS,
    ):
        label = entry_label(hass, entry)
        if any(
            token in label
            for token in (
                "summary",
                "recent",
                "year_to_date",
                "all_time",
                "gear",
            )
        ):
            continue
        if "activity" not in label:
            continue

        state_value, attrs, _unit = entity_value(hass, entry)
        if state_value is None:
            continue

        workout = _extract_record(
            attrs,
            source=entry.entity_id,
            provider_domain="ha_strava",
            source_state=hass.states.get(entry.entity_id),
        )
        if workout:
            if workout.name is None and _valid(state_value):
                workout.name = str(state_value)
            workout.extra.setdefault("fitness_adapter", "strava")
            result.append(workout)

        for raw in _activity_dicts(attrs):
            nested = _extract_record(
                raw,
                source=entry.entity_id,
                provider_domain="ha_strava",
            )
            if nested:
                nested.extra.setdefault("fitness_adapter", "strava")
                result.append(nested)

    return result
