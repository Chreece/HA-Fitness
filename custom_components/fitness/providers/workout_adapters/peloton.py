"""Peloton completed-workout adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import (
    distance_meters,
    duration_seconds,
    entity_value,
    find_entry,
    finite_number,
    selected_device_entries_by_domain,
    speed_m_s,
)
from ..workouts import _extract_record

DOMAINS = ("peloton",)


def _value(hass, entries, *tokens):
    entry = find_entry(hass, entries, *tokens)
    if entry is None:
        return None, None, None
    value, attrs, unit = entity_value(hass, entry)
    return value, unit, entry


def discover(hass: HomeAssistant, config: dict) -> list:
    """Bundle Peloton's per-workout sibling sensors into one Workout."""
    result = []

    for _device_id, entries in selected_device_entries_by_domain(
        hass,
        config,
        DOMAINS,
    ).items():
        start, _start_unit, start_entry = _value(
            hass, entries, "start", "time"
        )
        if start is None or start_entry is None:
            continue

        end, _end_unit, _ = _value(hass, entries, "end", "time")
        duration, duration_unit, _ = _value(hass, entries, "duration")
        distance, distance_unit, _ = _value(hass, entries, "distance")
        avg_hr, _avg_hr_unit, _ = _value(
            hass, entries, "heart", "rate", "average"
        )
        max_hr, _max_hr_unit, _ = _value(
            hass, entries, "heart", "rate", "max"
        )
        avg_cadence, _avg_cad_unit, _ = _value(
            hass, entries, "cadence", "average"
        )
        max_cadence, _max_cad_unit, _ = _value(
            hass, entries, "cadence", "max"
        )
        calories, _cal_unit, _ = _value(hass, entries, "calories")
        avg_speed, avg_speed_unit, _ = _value(
            hass, entries, "speed", "average"
        )
        max_speed, max_speed_unit, _ = _value(
            hass, entries, "speed", "max"
        )
        output_wh, _output_unit, _ = _value(
            hass, entries, "power", "output"
        )

        # The binary Workout entity owns useful workout metadata but is not in
        # the selected sensor list. Some installations also mirror these attrs
        # onto sibling states; preserve what can be discovered from sensor attrs.
        metadata = {}
        for entry in entries:
            state = hass.states.get(entry.entity_id)
            if state:
                for key in (
                    "workout_type",
                    "ride_title",
                    "ride_description",
                    "device_type",
                    "ftp",
                    "instructor",
                ):
                    if key in state.attributes and key not in metadata:
                        metadata[key] = state.attributes[key]

        raw = {
            "name": metadata.get("ride_title") or "Peloton workout",
            "sport": metadata.get("workout_type") or "workout",
            "start": start,
            "end": end,
            "duration_s": duration_seconds(duration, duration_unit or "min"),
            "distance_m": distance_meters(distance, distance_unit),
            "avg_hr": avg_hr,
            "max_hr": max_hr,
            "avg_cadence": avg_cadence,
            "max_cadence": max_cadence,
            "calories": calories,
            "average_speed_m_s": speed_m_s(avg_speed, avg_speed_unit),
            "max_speed_m_s": speed_m_s(max_speed, max_speed_unit),
            # Peloton exposes total Power Output in Wh, not average watts.
            "kilojoules": (
                finite_number(output_wh) * 3.6
                if finite_number(output_wh) is not None
                else None
            ),
            **metadata,
        }

        workout = _extract_record(
            raw,
            source=start_entry.entity_id,
            provider_domain="peloton",
        )
        if workout:
            workout.extra["fitness_adapter"] = "peloton"
            if output_wh is not None:
                workout.extra["peloton_power_output_wh"] = output_wh
            result.append(workout)

    return result
