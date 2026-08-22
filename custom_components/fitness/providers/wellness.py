"""Conservative wellness import from profile-owned supported HA integrations.

This bridge intentionally imports only entities that belong to a provider device
already assigned to the Fitness profile. It never scans arbitrary Home Assistant
sensors into a user's wellness history.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..const import CONF_SLEEP_DEVICE_IDS, CONF_WORKOUT_DEVICE_IDS
from ..device_adapters.history import DeviceHistoryBatch, DeviceMetricPoint

SUPPORTED_WELLNESS_DOMAINS = frozenset({
    "garmin_connect", "fitbit", "withings", "oura", "whoop", "suunto",
    "google_fit", "health_connect", "samsung_health", "polar",
})

# Exact normalized aliases only.  This is deliberately strict: an unrelated
# entity whose friendly name happens to contain "steps" must never become a
# personal Fitness health source.
WELLNESS_ALIASES: dict[str, frozenset[str]] = {
    "steps": frozenset({"steps", "daily_steps", "step_count", "daily_step_count"}),
    "distance_m": frozenset({"daily_distance", "distance_walked", "distance"}),
    "calories": frozenset({"calories", "daily_calories", "total_calories"}),
    "active_calories": frozenset({"active_calories", "daily_active_calories"}),
    "active_minutes": frozenset({"active_minutes", "daily_active_minutes"}),
    "moderate_minutes": frozenset({"moderate_minutes", "moderate_intensity_minutes"}),
    "vigorous_minutes": frozenset({"vigorous_minutes", "vigorous_intensity_minutes"}),
    "floors_climbed": frozenset({"floors_climbed", "floors"}),
    "resting_heart_rate": frozenset({"resting_heart_rate", "resting_hr", "daily_resting_heart_rate"}),
    "hrv_ms": frozenset({"hrv", "hrv_ms", "heart_rate_variability"}),
    "respiratory_rate": frozenset({"respiratory_rate", "respiration_rate"}),
    "spo2": frozenset({"spo2", "blood_oxygen", "oxygen_saturation"}),
    "stress": frozenset({"stress", "stress_level"}),
    "body_battery": frozenset({"body_battery", "body_battery_level"}),
    "sleep_score": frozenset({"sleep_score"}),
    "vo2_max": frozenset({"vo2_max", "vo2max"}),
    "weight": frozenset({"weight", "body_weight", "body_mass"}),
    "bmi": frozenset({"bmi"}),
    "body_fat": frozenset({"body_fat", "body_fat_percentage"}),
    "body_water": frozenset({"body_water", "body_water_percentage"}),
    "muscle_mass": frozenset({"muscle_mass"}),
    "bone_mass": frozenset({"bone_mass"}),
}

ADDITIVE = frozenset({
    "steps", "distance_m", "calories", "active_calories", "active_minutes",
    "moderate_minutes", "vigorous_minutes", "floors_climbed",
})


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _domain(hass: HomeAssistant, config_entry_id: str | None) -> str:
    entry = hass.config_entries.async_get_entry(config_entry_id) if config_entry_id else None
    return str(entry.domain) if entry is not None else ""


def _keys(registry_entry, state) -> set[str]:
    values = {
        _norm(getattr(registry_entry, "translation_key", None)),
        _norm(getattr(registry_entry, "name", None)),
        _norm(getattr(registry_entry, "original_name", None)),
        _norm(str(registry_entry.entity_id).split(".", 1)[-1]),
        _norm(state.attributes.get("friendly_name") if state else None),
    }
    expanded = set(values)
    for value in tuple(values):
        for prefix in (
            "garmin_connect_", "garmin_", "fitbit_", "withings_", "oura_",
            "whoop_", "suunto_", "google_fit_", "health_connect_",
            "samsung_health_", "polar_",
        ):
            if value.startswith(prefix):
                expanded.add(value[len(prefix):])
    return {item for item in expanded if item}


def _metric_for(keys: set[str]) -> str | None:
    for metric, aliases in WELLNESS_ALIASES.items():
        if keys.intersection(aliases):
            return metric
    return None


def _canonical_value(metric: str, value: float, unit: Any) -> float:
    unit_key = _norm(unit)
    if metric == "distance_m":
        if unit_key in {"km", "kilometer", "kilometers"}:
            return value * 1000.0
        if unit_key in {"mi", "mile", "miles"}:
            return value * 1609.344
    if metric == "weight" and unit_key in {"lb", "lbs", "pound", "pounds"}:
        return value * 0.45359237
    return value


def _parse_measurement_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif value is None:
        return None
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            try:
                number = float(raw)
                if number > 10_000_000_000:
                    number /= 1000.0
                result = datetime.fromtimestamp(number, tz=timezone.utc)
            except (TypeError, ValueError, OverflowError, OSError):
                return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _measurement_timestamp(state) -> datetime:
    """Prefer the provider's measurement timestamp, then the value-change time.

    ``State.last_updated`` can move merely because attributes refreshed, so it
    must not make an old provider value outrank a newer direct-device sample.
    """
    for key in (
        "measurement_time", "measured_at", "measurement_timestamp",
        "sample_time", "sample_timestamp", "timestamp", "updated_at", "last_updated",
    ):
        parsed = _parse_measurement_time(state.attributes.get(key))
        if parsed is not None:
            return parsed
    changed = _parse_measurement_time(getattr(state, "last_changed", None))
    if changed is not None:
        return changed
    updated = _parse_measurement_time(getattr(state, "last_updated", None))
    return updated or datetime.now(timezone.utc)


def discover_profile_wellness(hass: HomeAssistant, config: dict[str, Any]) -> DeviceHistoryBatch:
    """Return wellness points from supported provider devices owned by profile."""
    allowed_devices = {
        str(device_id)
        for field in (CONF_WORKOUT_DEVICE_IDS, CONF_SLEEP_DEVICE_IDS)
        for device_id in (config.get(field) or [])
        if device_id
    }
    if not allowed_devices:
        return DeviceHistoryBatch()

    registry = er.async_get(hass)
    points: list[DeviceMetricPoint] = []
    for reg in registry.entities.values():
        if not str(reg.entity_id).startswith("sensor."):
            continue
        if not reg.device_id or str(reg.device_id) not in allowed_devices:
            continue
        domain = _domain(hass, reg.config_entry_id)
        if domain not in SUPPORTED_WELLNESS_DOMAINS:
            continue
        state = hass.states.get(reg.entity_id)
        if state is None or str(state.state).lower() in {"", "unknown", "unavailable", "none"}:
            continue
        metric = _metric_for(_keys(reg, state))
        if metric is None:
            continue
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            continue
        value = _canonical_value(metric, value, state.attributes.get("unit_of_measurement"))
        context = (("measurement_context", "current_total"),) if metric in ADDITIVE else ()
        points.append(DeviceMetricPoint(
            metric=metric,
            value=value,
            timestamp=_measurement_timestamp(state).isoformat(),
            source_type=f"integration:{domain}",
            source_entity=reg.entity_id,
            sources=(domain,),
            context=context,
        ))
    return DeviceHistoryBatch.bounded(metric_points=points)
