"""Hevy strength-workout adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import (
    duration_seconds,
    entity_value,
    find_entry,
    selected_device_entries_by_domain,
)
from ..workouts import _extract_record

DOMAINS = ("hevy",)


def discover(hass: HomeAssistant, config: dict) -> list:
    """Parse Hevy aggregate Last Workout sibling sensors."""
    result = []

    for _device_id, entries in selected_device_entries_by_domain(
        hass,
        config,
        DOMAINS,
    ).items():
        start_entry = find_entry(hass, entries, "last", "workout", "start")
        title_entry = find_entry(hass, entries, "last", "workout")
        duration_entry = find_entry(hass, entries, "last", "workout", "duration")
        volume_entry = find_entry(hass, entries, "last", "workout", "volume")

        if start_entry is None:
            continue

        start, _attrs, _unit = entity_value(hass, start_entry)
        if start is None:
            continue

        title = None
        title_attrs = {}
        source = start_entry.entity_id
        if title_entry is not None:
            title, title_attrs, _ = entity_value(hass, title_entry)
            source = title_entry.entity_id

        raw = {
            "name": title or "Hevy workout",
            "sport": "strength",
            "start": start,
            "exercise_count": title_attrs.get("exercise_count"),
            "total_reps": title_attrs.get("total_reps"),
        }

        if duration_entry is not None:
            value, _attrs, unit = entity_value(hass, duration_entry)
            raw["duration_s"] = duration_seconds(value, unit or "min")

        if volume_entry is not None:
            value, _attrs, _unit = entity_value(hass, volume_entry)
            raw["volume_kg"] = value

        workout = _extract_record(
            raw,
            source=source,
            provider_domain="hevy",
        )
        if workout:
            workout.extra["fitness_adapter"] = "hevy"
            result.append(workout)

    return result
