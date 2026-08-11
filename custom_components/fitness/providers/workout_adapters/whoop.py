"""WHOOP completed-workout adapter."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import entry_label, selected_sensor_entries
from ..workouts import _extract_record

DOMAINS = ("whoop",)


def discover(hass: HomeAssistant, config: dict) -> list:
    """Normalize WHOOP last-workout overview entities when present."""
    result = []
    for entry in selected_sensor_entries(hass, config, domains=DOMAINS):
        label = entry_label(hass, entry)
        if "workout_overview" not in label and "last_workout" not in label:
            continue
        state = hass.states.get(entry.entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            continue
        raw = dict(state.attributes)
        raw.setdefault("name", raw.get("sport_name") or state.state)
        raw.setdefault("sport", raw.get("sport_name") or raw.get("sport"))
        candidate = _extract_record(
            raw,
            source=entry.entity_id,
            provider_domain="whoop",
            source_state=state,
        )
        if candidate is not None:
            candidate.extra["fitness_adapter"] = "whoop"
            result.append(candidate)
    return result
