"""Shared helpers for Fitness sleep adapters."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ...const import CONF_SLEEP_DEVICE_IDS
from ..sleep import SleepRecord, parse_datetime


@dataclass(frozen=True, slots=True)
class SleepAdapterSpec:
    """One provider-specific sleep adapter."""

    name: str
    domains: tuple[str, ...]
    aliases: dict[str, tuple[str, ...]]


def provider_domain(hass: HomeAssistant, entry) -> str:
    config_entry_id = getattr(entry, "config_entry_id", None)
    if not config_entry_id:
        return "unknown"

    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    return config_entry.domain if config_entry is not None else "unknown"


def normalized_label(hass: HomeAssistant, entry) -> str:
    state = hass.states.get(entry.entity_id)

    return " ".join(
        (
            entry.entity_id,
            entry.name or "",
            entry.original_name or "",
            str(getattr(entry, "translation_key", None) or ""),
            str(state.attributes.get("friendly_name") or "") if state else "",
        )
    ).lower().replace("-", "_").replace(" ", "_")


def selected_entries(
    hass: HomeAssistant,
    config: dict,
    *,
    domains: tuple[str, ...] | None = None,
):
    """Return sensor/binary-sensor entities from selected sleep devices."""

    device_ids = set(config.get(CONF_SLEEP_DEVICE_IDS) or [])
    registry = er.async_get(hass)

    result = []

    for entry in registry.entities.values():
        if entry.device_id not in device_ids:
            continue

        if not (
            entry.entity_id.startswith("sensor.")
            or entry.entity_id.startswith("binary_sensor.")
        ):
            continue

        domain = provider_domain(hass, entry)

        if domains is not None and domain not in domains:
            continue

        result.append(entry)

    return result


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def duration_seconds(value: Any, unit: str | None) -> float | None:
    number = _number(value)

    if number is None:
        return None

    normalized = str(unit or "").strip().lower()

    if normalized in ("ms", "millisecond", "milliseconds"):
        return number / 1000

    if normalized in ("min", "minute", "minutes"):
        return number * 60

    if normalized in ("h", "hr", "hour", "hours"):
        return number * 3600

    return number


def boolean_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value

    normalized = str(value or "").strip().lower()

    if normalized in ("on", "true", "yes", "1", "occupied", "in_bed", "sleeping"):
        return True

    if normalized in ("off", "false", "no", "0", "clear", "awake", "not_in_bed"):
        return False

    return None


_DURATION_FIELDS = {
    "duration_s",
    "time_in_bed_s",
    "awake_s",
    "light_sleep_s",
    "deep_sleep_s",
    "rem_sleep_s",
    "sleep_latency_s",
    "sleep_need_s",
    "sleep_debt_s",
}

_DATETIME_FIELDS = {
    "start",
    "end",
}

_BOOLEAN_FIELDS = {
    "in_bed",
}


def _value_for_field(hass: HomeAssistant, entry, field: str):
    state = hass.states.get(entry.entity_id)

    if state is None or state.state in ("unknown", "unavailable", ""):
        return None

    if field in _DURATION_FIELDS:
        return duration_seconds(
            state.state,
            state.attributes.get("unit_of_measurement"),
        )

    if field in _DATETIME_FIELDS:
        return parse_datetime(state.state)

    if field in _BOOLEAN_FIELDS:
        return boolean_value(state.state)

    return _number(state.state)


def discover_from_spec(
    hass: HomeAssistant,
    config: dict,
    spec: SleepAdapterSpec,
) -> SleepRecord | None:
    """Normalize one selected provider device into one latest SleepRecord."""

    entries = selected_entries(
        hass,
        config,
        domains=spec.domains,
    )

    if not entries:
        return None

    labels = {
        entry.entity_id: normalized_label(hass, entry)
        for entry in entries
    }

    values: dict[str, Any] = {}
    field_sources: dict[str, str] = {}
    provider_values: dict[str, Any] = {}

    for entry in entries:
        state = hass.states.get(entry.entity_id)

        if state is not None and state.state not in ("unknown", "unavailable", ""):
            provider_values[entry.entity_id] = {
                "state": state.state,
                "unit": state.attributes.get("unit_of_measurement"),
            }

    for field, aliases in spec.aliases.items():
        for entry in entries:
            label = labels[entry.entity_id]

            if not any(alias in label for alias in aliases):
                continue

            value = _value_for_field(hass, entry, field)

            if value is None:
                continue

            values[field] = value
            field_sources[field] = entry.entity_id
            break

    # WHOOP overview entities expose start/end in attributes rather than state.
    # The same mechanism also supports future providers with a similar contract.
    for entry in entries:
        state = hass.states.get(entry.entity_id)

        if state is None:
            continue

        label = labels[entry.entity_id]

        if "sleep_overview" not in label and "last_sleep" not in label:
            continue

        if not values.get("start"):
            values["start"] = parse_datetime(state.attributes.get("start"))
            if values["start"]:
                field_sources["start"] = entry.entity_id

        if not values.get("end"):
            values["end"] = parse_datetime(state.attributes.get("end"))
            if values["end"]:
                field_sources["end"] = entry.entity_id

    meaningful_fields = (
        "start",
        "end",
        "duration_s",
        "time_in_bed_s",
        "awake_s",
        "light_sleep_s",
        "deep_sleep_s",
        "rem_sleep_s",
        "score",
        "efficiency_percent",
        "average_hr",
        "hrv_ms",
        "respiratory_rate",
        "readiness_score",
        "recovery_score",
        "in_bed",
    )

    if not any(values.get(field) is not None for field in meaningful_fields):
        return None

    source = next(
        iter(field_sources.values()),
        entries[0].entity_id,
    )

    record = SleepRecord(
        source=source,
        provider_domain=provider_domain(hass, entries[0]),
        sources=sorted(set(field_sources.values())),
        field_sources=field_sources,
        provider_values=provider_values,
        **values,
    )

    return record


def trigger_entity_ids_for_spec(
    hass: HomeAssistant,
    config: dict,
    spec: SleepAdapterSpec,
) -> set[str]:
    """Return only entities relevant to the normalized sleep contract."""

    result: set[str] = set()

    aliases = tuple(
        alias
        for items in spec.aliases.values()
        for alias in items
    )

    for entry in selected_entries(
        hass,
        config,
        domains=spec.domains,
    ):
        label = normalized_label(hass, entry)

        if any(alias in label for alias in aliases):
            result.add(entry.entity_id)

        if "sleep_overview" in label or "last_sleep" in label:
            result.add(entry.entity_id)

    return result
