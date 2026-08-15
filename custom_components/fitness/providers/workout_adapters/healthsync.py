"""HealthSync / Apple Health completed-workout adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import (
    entry_label,
    entity_value,
    finite_number,
    selected_device_entries_by_domain,
)
from ..workouts import _extract_record

DOMAINS = ("healthsync",)


def _unique_id(entry) -> str:
    return str(getattr(entry, "unique_id", "") or "").casefold()


def _slot_index(entry) -> int | None:
    unique_id = _unique_id(entry)
    marker = "_workout_slot_"
    if marker not in unique_id:
        return None
    try:
        return int(unique_id.rsplit(marker, 1)[1])
    except (TypeError, ValueError):
        return None


def _from_slot(hass: HomeAssistant, entry):
    state_value, attrs, _unit = entity_value(hass, entry)
    if state_value is None:
        return None
    raw = {
        "name": state_value,
        "sport": state_value,
        "start": attrs.get("started_at"),
        "end": attrs.get("ended_at"),
        "duration_min": attrs.get("duration_min"),
        "distance_m": attrs.get("distance_m"),
        "calories": attrs.get("calories"),
    }
    workout = _extract_record(
        raw,
        source=entry.entity_id,
        provider_domain="healthsync",
    )
    if workout:
        workout.extra.setdefault("fitness_adapter", "healthsync")
        workout.extra.setdefault("healthsync_contract", "recent_workout_slot")
        workout.extra.setdefault("healthsync_slot", _slot_index(entry))
    return workout


def _last_summary(hass: HomeAssistant, entries: list):
    type_entry = None
    duration_entry = None
    distance_entry = None
    calories_entry = None
    for entry in entries:
        unique_id = _unique_id(entry)
        label = entry_label(hass, entry)
        if unique_id.endswith("_last_workout_type") or "last_workout_type" in label:
            type_entry = entry
        elif unique_id.endswith("_last_workout_duration") or "last_workout_duration" in label:
            duration_entry = entry
        elif unique_id.endswith("_last_workout_distance") or "last_workout_distance" in label:
            distance_entry = entry
        elif unique_id.endswith("_last_workout_calories") or "last_workout_calories" in label:
            calories_entry = entry

    if type_entry is None:
        return None
    type_value, type_attrs, _unit = entity_value(hass, type_entry)
    if type_value is None:
        return None

    raw = {
        "name": type_value,
        "sport": type_value,
        "start": type_attrs.get("started_at"),
        "end": type_attrs.get("ended_at"),
    }

    for entry, key in (
        (duration_entry, "duration_min"),
        (distance_entry, "distance_m"),
        (calories_entry, "calories"),
    ):
        if entry is None:
            continue
        state_value, _attrs, _unit = entity_value(hass, entry)
        number = finite_number(state_value)
        if number is not None:
            raw[key] = number

    workout = _extract_record(
        raw,
        source=type_entry.entity_id,
        provider_domain="healthsync",
    )
    if workout:
        workout.extra.setdefault("fitness_adapter", "healthsync")
        workout.extra.setdefault("healthsync_contract", "last_workout_summary")
    return workout


def discover(hass: HomeAssistant, config: dict) -> list:
    """Read HealthSync's recent-workout slots or latest summary."""
    result = []
    for _device_id, entries in selected_device_entries_by_domain(
        hass, config, DOMAINS
    ).items():
        slots = sorted(
            (entry for entry in entries if _slot_index(entry) is not None),
            key=lambda entry: _slot_index(entry) or 0,
        )
        parsed_slots = 0
        for entry in slots:
            workout = _from_slot(hass, entry)
            if workout is not None:
                result.append(workout)
                parsed_slots += 1

        # The slots are richer and represent up to ten distinct recent
        # workouts. Fall back to the scalar latest-workout quartet before a
        # slot exists *or* while restored slot entities are temporarily
        # unavailable during Home Assistant startup.
        if parsed_slots == 0:
            workout = _last_summary(hass, entries)
            if workout is not None:
                result.append(workout)
    return result
