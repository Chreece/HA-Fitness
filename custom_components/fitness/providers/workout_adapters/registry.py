"""Registry for maintainable completed-workout provider support."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .base import WorkoutAdapterSpec
from . import garmin, hevy, oura, peloton, polar, strava
from . import generic

ADAPTERS: tuple[WorkoutAdapterSpec, ...] = (
    WorkoutAdapterSpec("garmin", garmin.DOMAINS, garmin.discover),
    WorkoutAdapterSpec("strava", strava.DOMAINS, strava.discover),
    WorkoutAdapterSpec("polar", polar.DOMAINS, polar.discover),
    WorkoutAdapterSpec("hevy", hevy.DOMAINS, hevy.discover),
    WorkoutAdapterSpec("peloton", peloton.DOMAINS, peloton.discover),
    WorkoutAdapterSpec("oura", oura.DOMAINS, oura.discover),
)

EXPLICIT_DOMAINS = frozenset(
    domain
    for adapter in ADAPTERS
    for domain in adapter.domains
)


def supported_adapter_domains() -> dict[str, tuple[str, ...]]:
    """Expose adapter registry for diagnostics/tests/documentation."""
    return {
        adapter.name: adapter.domains
        for adapter in ADAPTERS
    }


def discover_all(hass: HomeAssistant, config: dict) -> list:
    """Run explicit adapters first, then the generic fallback."""
    result = []
    for adapter in ADAPTERS:
        result.extend(adapter.discover(hass, config))

    # Known providers are excluded from generic parsing so one provider contract
    # has exactly one owner. Future/unknown providers remain automatically
    # eligible for the generic adapter.
    result.extend(
        generic.discover(
            hass,
            config,
            exclude_domains=set(EXPLICIT_DOMAINS),
        )
    )
    return result
