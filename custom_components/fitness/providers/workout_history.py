"""Historical workout import helpers for Fitness."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .workouts import Workout, _activity_dicts, _dt, _extract_record, merged_workouts


def _entry_for_entity(hass: HomeAssistant, entity_id: str):
    return er.async_get(hass).async_get(entity_id)


def _provider_domain(hass: HomeAssistant, entity_id: str) -> str:
    entry = _entry_for_entity(hass, entity_id)
    if entry is None or not entry.config_entry_id:
        return "unknown"
    config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
    return str(config_entry.domain) if config_entry else "unknown"


def _label(hass: HomeAssistant, entity_id: str) -> str:
    entry = _entry_for_entity(hass, entity_id)
    if entry is None:
        return entity_id.lower()
    return " ".join(str(v) for v in (entity_id, entry.name, entry.original_name) if v).lower()


def _tag(workout: Workout, entity_id: str, provider: str) -> Workout:
    workout.sources = list(dict.fromkeys([*(workout.sources or []), f"recorder:{entity_id}"]))
    if provider != "unknown":
        workout.provider_domains = list(dict.fromkeys([*(workout.provider_domains or []), provider]))
    workout.extra.setdefault("fitness_history_source", "home_assistant_recorder")
    workout.extra.setdefault("fitness_history_entity_id", entity_id)
    return workout


def workouts_from_recorder_history(hass: HomeAssistant, config: dict, history: dict[str, list[State]]) -> list[Workout]:
    """Parse old snapshots from the selected completed-workout entities."""
    del config
    candidates: list[Workout] = []
    for entity_id, states in (history or {}).items():
        provider = _provider_domain(hass, entity_id)
        label = _label(hass, entity_id)
        for state in states or []:
            if not isinstance(state, State):
                continue
            attrs = dict(state.attributes or {})
            for raw in _activity_dicts(attrs):
                workout = _extract_record(raw, source=entity_id, provider_domain=provider)
                if workout and workout.start:
                    candidates.append(_tag(workout, entity_id, provider))
            # Latest-activity sensors (for example Strava) become a historical
            # stream in Recorder as their attributes are replaced over time.
            workout = _extract_record(
                attrs, source=entity_id, provider_domain=provider, source_state=state
            )
            if workout and workout.start:
                candidates.append(_tag(workout, entity_id, provider))
            # Timestamp-state entities are accepted only when their identity
            # explicitly says workout/activity start/date; this avoids epoch-1970
            # ghosts from numeric summary sensors.
            if any(token in label for token in ("workout start", "activity start", "workout date", "last workout date")):
                start = _dt(state.state)
                if start is not None:
                    candidates.append(_tag(Workout(source=entity_id, start=start.isoformat(), sport="workout"), entity_id, provider))
    return merged_workouts(candidates)


def _selected_provider_config_entries(hass: HomeAssistant, config: dict, domain: str) -> set[str]:
    from .evaluation import workout_device_entity_ids
    result = set()
    registry = er.async_get(hass)
    for entity_id in workout_device_entity_ids(hass, config):
        entry = registry.async_get(entity_id)
        if entry is None or not entry.config_entry_id:
            continue
        config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
        if config_entry and config_entry.domain == domain:
            result.add(config_entry.entry_id)
    return result


def _hevy_workout(raw: dict[str, Any], source: str) -> Workout | None:
    payload = dict(raw)
    payload.setdefault("sport", "strength")
    payload.setdefault("name", payload.get("title") or "Hevy workout")
    if payload.get("duration_minutes") is not None and payload.get("duration_s") is None:
        try:
            payload["duration_s"] = float(payload["duration_minutes"]) * 60.0
        except (TypeError, ValueError):
            pass
    workout = _extract_record(payload, source=source, provider_domain="hevy")
    if workout:
        workout.extra.setdefault("fitness_adapter", "hevy_history")
        # Preserve the rich exercise/set payload for calendar and future analysis.
        for key in ("exercises", "muscle_groups", "primary_muscle_groups", "secondary_muscle_groups"):
            if key in raw:
                workout.extra.setdefault(key, raw[key])
    return workout


async def async_provider_history_workouts(hass: HomeAssistant, config: dict) -> list[Workout]:
    """Fetch historical workouts from providers that expose a HA history API."""
    result: list[Workout] = []

    # Hevy exposes a response-returning get_workout_history action (1-90 days).
    if hass.services.has_service("hevy", "get_workout_history"):
        for config_entry_id in _selected_provider_config_entries(hass, config, "hevy"):
            try:
                response = await hass.services.async_call(
                    "hevy",
                    "get_workout_history",
                    {"config_entry_id": config_entry_id, "days": 90},
                    blocking=True,
                    return_response=True,
                )
            except Exception:
                continue
            for raw in (response or {}).get("workouts", []) or []:
                if not isinstance(raw, dict):
                    continue
                workout = _hevy_workout(raw, f"hevy_history:{config_entry_id}")
                if workout and workout.start:
                    result.append(workout)

    return merged_workouts(result)
