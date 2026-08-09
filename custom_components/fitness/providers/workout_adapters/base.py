"""Shared helpers for completed-workout provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import re
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ...const import CONF_WORKOUT_DEVICE_IDS


@dataclass(frozen=True, slots=True)
class WorkoutAdapterSpec:
    """Metadata for one provider-specific adapter."""

    name: str
    domains: tuple[str, ...]
    discover: Callable[[HomeAssistant, dict], list]


def provider_domain(hass: HomeAssistant, entry) -> str:
    """Return the config-entry domain behind an entity registry entry."""
    config_entry_id = getattr(entry, "config_entry_id", None)
    if not config_entry_id:
        return "unknown"
    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    return config_entry.domain if config_entry is not None else "unknown"


def selected_sensor_entries(
    hass: HomeAssistant,
    config: dict,
    *,
    domains: tuple[str, ...] | None = None,
    exclude_domains: set[str] | None = None,
):
    """Return selected workout-device sensor registry entries."""
    device_ids = set(config.get(CONF_WORKOUT_DEVICE_IDS) or [])
    registry = er.async_get(hass)
    result = []

    for entry in registry.entities.values():
        if entry.device_id not in device_ids:
            continue
        if not entry.entity_id.startswith("sensor."):
            continue

        domain = provider_domain(hass, entry)
        if domains is not None and domain not in domains:
            continue
        if exclude_domains and domain in exclude_domains:
            continue
        result.append(entry)

    return result


def selected_device_entries_by_domain(
    hass: HomeAssistant,
    config: dict,
    domains: tuple[str, ...],
) -> dict[str, list]:
    """Group selected sensor entities by device for one provider family."""
    result: dict[str, list] = {}
    for entry in selected_sensor_entries(
        hass,
        config,
        domains=domains,
    ):
        if entry.device_id:
            result.setdefault(entry.device_id, []).append(entry)
    return result


def selected_device_ids_for_domains(
    hass: HomeAssistant,
    config: dict,
    domains: tuple[str, ...],
) -> set[str]:
    """Return selected workout device IDs belonging to provider domains."""
    return set(selected_device_entries_by_domain(hass, config, domains))


def selected_provider_domains(
    hass: HomeAssistant,
    config: dict,
) -> dict[str, set[str]]:
    """Map selected workout device ID to config-entry domains."""
    result: dict[str, set[str]] = {}
    for entry in selected_sensor_entries(hass, config):
        if entry.device_id:
            result.setdefault(entry.device_id, set()).add(
                provider_domain(hass, entry)
            )
    return result


def entry_label(hass: HomeAssistant, entry) -> str:
    state = hass.states.get(entry.entity_id)
    return " ".join(
        (
            entry.entity_id,
            entry.name or "",
            entry.original_name or "",
            str(state.attributes.get("friendly_name") or "") if state else "",
        )
    ).lower().replace("-", "_").replace(" ", "_")


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


# math is imported down here intentionally to keep the public helper section short.
import math


_ISO_DURATION = re.compile(
    r"^P"
    r"(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?"
    r")?$",
    re.IGNORECASE,
)


def duration_seconds(value: Any, unit: str | None = None) -> float | None:
    """Normalize numeric or ISO-8601 duration to seconds."""
    if value is None:
        return None

    if isinstance(value, str):
        match = _ISO_DURATION.fullmatch(value.strip())
        if match:
            parts = {
                key: float(number or 0)
                for key, number in match.groupdict().items()
            }
            return (
                parts["days"] * 86400
                + parts["hours"] * 3600
                + parts["minutes"] * 60
                + parts["seconds"]
            )

    number = finite_number(value)
    if number is None:
        return None

    normalized = str(unit or "").strip().lower()
    if normalized in ("min", "minute", "minutes"):
        return number * 60
    if normalized in ("h", "hr", "hour", "hours"):
        return number * 3600
    return number


def distance_meters(value: Any, unit: str | None = None) -> float | None:
    number = finite_number(value)
    if number is None:
        return None
    normalized = str(unit or "").strip().lower()
    if normalized in ("km", "kilometer", "kilometers"):
        return number * 1000
    if normalized in ("mi", "mile", "miles"):
        return number * 1609.344
    if normalized in ("ft", "foot", "feet"):
        return number * 0.3048
    return number


def speed_m_s(value: Any, unit: str | None = None) -> float | None:
    number = finite_number(value)
    if number is None:
        return None
    normalized = str(unit or "").strip().lower()
    if normalized in ("km/h", "kmh", "kph"):
        return number / 3.6
    if normalized in ("mph", "mi/h"):
        return number * 0.44704
    return number


def entity_value(hass: HomeAssistant, entry):
    """Return state, attributes and unit for an entity."""
    state = hass.states.get(entry.entity_id)
    if state is None or state.state in ("unknown", "unavailable", ""):
        return None, {}, None
    return (
        state.state,
        dict(state.attributes),
        state.attributes.get("unit_of_measurement"),
    )


def find_entry(hass: HomeAssistant, entries: list, *tokens: str):
    """Find one entity whose normalized label contains all tokens."""
    normalized_tokens = tuple(
        token.lower().replace("-", "_").replace(" ", "_")
        for token in tokens
    )
    for entry in entries:
        label = entry_label(hass, entry)
        if all(token in label for token in normalized_tokens):
            return entry
    return None
