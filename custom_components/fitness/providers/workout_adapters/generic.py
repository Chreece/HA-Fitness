"""Generic completed-workout adapter for unknown/future integrations."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from ..workouts import _bundle_sibling_entities, _generic_activity_entities


def discover(
    hass: HomeAssistant,
    config: dict,
    *,
    exclude_domains: set[str] | None = None,
) -> list:
    """Use Fitness' schema/label heuristics for integrations without adapters."""
    return (
        _generic_activity_entities(
            hass,
            config,
            exclude_domains=exclude_domains,
        )
        + _bundle_sibling_entities(
            hass,
            config,
            exclude_domains=exclude_domains,
        )
    )
