"""Oura completed-workout adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import (
    distance_meters,
    duration_seconds,
    entity_value,
    find_entry,
    selected_device_entries_by_domain,
)
from ..workouts import _dt, _extract_record

DOMAINS = ("oura",)


def _first_timestamp_from_attrs(attrs: dict):
    for key in (
        "start_datetime",
        "start_time",
        "start",
        "timestamp",
        "date",
        "day",
    ):
        if key in attrs and _dt(attrs[key]) is not None:
            return attrs[key]
    return None


def discover(hass: HomeAssistant, config: dict) -> list:
    """Bundle Oura's latest-workout sensors when a real start timestamp exists.

    Oura exposes type, duration, distance, calories and intensity as sibling
    sensors. Fitness refuses to invent a workout timestamp; if the installed
    Oura version does not expose one in state attributes, the generic
    evaluation metrics still remain usable but no completed workout is created.
    """
    result = []

    for _device_id, entries in selected_device_entries_by_domain(
        hass,
        config,
        DOMAINS,
    ).items():
        type_entry = find_entry(hass, entries, "last", "workout", "type")
        if type_entry is None:
            continue

        workout_type, type_attrs, _unit = entity_value(hass, type_entry)
        if workout_type is None:
            continue

        start = _first_timestamp_from_attrs(type_attrs)
        if start is None:
            # Search attributes of sibling latest-workout entities too.
            for entry in entries:
                if "last_workout" not in entry.entity_id:
                    continue
                state = hass.states.get(entry.entity_id)
                if state:
                    start = _first_timestamp_from_attrs(dict(state.attributes))
                    if start is not None:
                        break

        if start is None:
            continue

        duration_entry = find_entry(
            hass, entries, "last", "workout", "duration"
        )
        distance_entry = find_entry(
            hass, entries, "last", "workout", "distance"
        )
        calories_entry = find_entry(
            hass, entries, "last", "workout", "calories"
        )
        intensity_entry = find_entry(
            hass, entries, "last", "workout", "intensity"
        )

        raw = {
            "name": str(workout_type),
            "sport": str(workout_type),
            "start": start,
        }

        if duration_entry:
            value, _attrs, unit = entity_value(hass, duration_entry)
            raw["duration_s"] = duration_seconds(value, unit or "min")
        if distance_entry:
            value, _attrs, unit = entity_value(hass, distance_entry)
            raw["distance_m"] = distance_meters(value, unit)
        if calories_entry:
            value, _attrs, _unit = entity_value(hass, calories_entry)
            raw["calories"] = value
        if intensity_entry:
            value, _attrs, _unit = entity_value(hass, intensity_entry)
            raw["oura_intensity"] = value

        workout = _extract_record(
            raw,
            source=type_entry.entity_id,
            provider_domain="oura",
        )
        if workout:
            workout.extra["fitness_adapter"] = "oura"
            result.append(workout)

    return result
