"""HealthSync / Apple Health completed-sleep adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from .registry_types import SleepAdapterSpec
from ..sleep import SleepRecord

DOMAINS = ("healthsync",)

# HealthSync exposes one duration sensor whose attributes contain the four
# Apple Health sleep stages, plus two local-clock timestamp sensors whose full
# datetimes live in a ``timestamp`` attribute.
SPEC = SleepAdapterSpec(
    "healthsync",
    DOMAINS,
    {
        "duration_s": ("sleep_duration", "sleep_last_night", "last_night"),
        "awake_s": ("sleep_duration", "sleep_last_night", "last_night"),
        "light_sleep_s": ("sleep_duration", "sleep_last_night", "last_night"),
        "deep_sleep_s": ("sleep_duration", "sleep_last_night", "last_night"),
        "rem_sleep_s": ("sleep_duration", "sleep_last_night", "last_night"),
        "start": ("sleep_onset", "fell_asleep"),
        "end": ("sleep_wake", "woke_up"),
    },
)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _duration_seconds(value: Any, unit: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    normalized = str(unit or "").strip().casefold()
    if normalized in {"h", "hr", "hour", "hours"}:
        return number * 3600.0
    if normalized in {"min", "minute", "minutes"}:
        return number * 60.0
    if normalized in {"ms", "millisecond", "milliseconds"}:
        return number / 1000.0
    return number


def _timestamp(value: Any) -> str | None:
    if value in (None, "", "unknown", "unavailable"):
        return None
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value).strip()
        try:
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.isoformat()


def _unique_id(entry) -> str:
    return str(getattr(entry, "unique_id", "") or "").casefold()


def _label(hass, entry) -> str:
    state = hass.states.get(entry.entity_id)
    return " ".join(
        str(value or "")
        for value in (
            entry.entity_id,
            getattr(entry, "name", None),
            getattr(entry, "original_name", None),
            getattr(entry, "translation_key", None),
            state.attributes.get("friendly_name") if state else None,
        )
    ).casefold().replace("-", "_").replace(" ", "_")


def _find(entries: list, hass, *, unique_suffix: str, labels: tuple[str, ...]):
    for entry in entries:
        if _unique_id(entry).endswith(unique_suffix):
            return entry
    for entry in entries:
        label = _label(hass, entry)
        if any(token in label for token in labels):
            return entry
    return None


def discover(hass, entries: list) -> SleepRecord | None:
    """Parse HealthSync's latest completed Apple Health sleep snapshot."""
    if not entries:
        return None

    sleep_entry = _find(
        entries,
        hass,
        unique_suffix="_sleep_duration",
        labels=("sleep_last_night", "sleep_duration"),
    )
    onset_entry = _find(
        entries,
        hass,
        unique_suffix="_sleep_onset",
        labels=("fell_asleep", "sleep_onset"),
    )
    wake_entry = _find(
        entries,
        hass,
        unique_suffix="_sleep_wake",
        labels=("woke_up", "sleep_wake"),
    )

    values: dict[str, Any] = {}
    sources: dict[str, str] = {}
    field_routes: dict[str, dict[str, str]] = {}
    raw: dict[str, Any] = {}
    observed = []

    if sleep_entry is not None:
        state = hass.states.get(sleep_entry.entity_id)
        if state is not None and state.state not in ("unknown", "unavailable", ""):
            raw[sleep_entry.entity_id] = {
                "state": state.state,
                "attributes": dict(state.attributes),
            }
            duration_s = _duration_seconds(
                state.state,
                state.attributes.get("unit_of_measurement"),
            )
            if duration_s is not None:
                values["duration_s"] = duration_s
                sources["duration_s"] = sleep_entry.entity_id
                field_routes["duration_s"] = {
                    "entity_id": sleep_entry.entity_id,
                    "transform": "state",
                }

            stage_fields = {
                "awake_s": "awake_minutes",
                "light_sleep_s": "core_minutes",
                "deep_sleep_s": "deep_minutes",
                "rem_sleep_s": "rem_minutes",
            }
            for field_name, attribute in stage_fields.items():
                minutes = _number(state.attributes.get(attribute))
                if minutes is None:
                    continue
                values[field_name] = minutes * 60.0
                sources[field_name] = sleep_entry.entity_id
                field_routes[field_name] = {
                    "entity_id": sleep_entry.entity_id,
                    "attribute": attribute,
                    "transform": "identity",
                    "unit": "min",
                }
            if getattr(state, "last_updated", None) is not None:
                observed.append(state.last_updated)

    for field_name, entry in (("start", onset_entry), ("end", wake_entry)):
        if entry is None:
            continue
        state = hass.states.get(entry.entity_id)
        if state is None:
            continue
        raw[entry.entity_id] = {
            "state": state.state,
            "attributes": dict(state.attributes),
        }
        parsed = _timestamp(state.attributes.get("timestamp"))
        if parsed is not None:
            values[field_name] = parsed
            sources[field_name] = entry.entity_id
        if getattr(state, "last_updated", None) is not None:
            observed.append(state.last_updated)

    if observed:
        values["observed_at"] = max(observed).isoformat()

    if not any(values.get(field) is not None for field in (
        "duration_s", "awake_s", "light_sleep_s", "deep_sleep_s", "rem_sleep_s",
        "start", "end",
    )):
        return None

    source = (
        sleep_entry.entity_id if sleep_entry is not None
        else next(iter(sources.values()), entries[0].entity_id)
    )
    return SleepRecord(
        source=source,
        provider_domain="healthsync",
        sources=list(dict.fromkeys(sources.values() or [source])),
        provider_domains=["healthsync"],
        field_sources=dict(sources),
        provider_values={
            "healthsync": {
                "raw": raw,
                "field_routes": field_routes,
                "contract": "apple_health_latest_sleep_snapshot",
            }
        },
        **values,
    )
