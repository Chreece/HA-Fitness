"""Fitbit completed-workout adapter."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from . import generic

DOMAINS = ('fitbit',)

def discover(hass: HomeAssistant, config: dict) -> list:
    """Normalize recognizable completed activities from this provider only."""
    result = generic.discover(hass, config, only_domains=set(DOMAINS))
    for workout in result:
        workout.extra["fitness_adapter"] = "fitbit"
        workout.extra["fitness_adapter_contract"] = "scoped_normalized_activity"
    return result
