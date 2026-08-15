"""Stable per-profile data-source maps for the Fitness dashboard.

The dashboard must never infer ownership by scanning Home Assistant on every
render.  Each Fitness profile therefore exposes one routing sensor on each of
its four devices (Workouts, Live workout, Recovery and Evaluation). The sensor
attributes normally contain *where* a value lives. A deliberately small inline
exception exists for low-frequency facts that have no authoritative scalar HA
entity (calculated substitutes, event reconstructions and canonical corrections).
"""
from __future__ import annotations

from typing import Any, Iterable

from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    METRIC_ALTITUDE,
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
)
from .live import get_live_runtime
from .providers.evaluation import collect_provider_metrics

DATA_MAP_SCHEMA_VERSION = 3

# Inline values are an intentionally tiny exception to the routing-only map
# contract. They are allowed only when the dashboard fact has no authoritative
# scalar HA entity to read from. ``fitness_calculated`` is a substitute fact
# Fitness computes because the provider omitted it; ``source_reconstructed``
# is rebuilt exactly from source events/attributes; ``source_normalized`` is a
# corrected canonical source fact (for example impossible sleep duration).
INLINE_VALUE_SOURCE_TYPES = frozenset({
    "fitness_calculated",
    "source_reconstructed",
    "source_normalized",
})


def _route_keeps_inline_value(route: dict[str, Any]) -> bool:
    return (
        route.get("transform") == "inline"
        and route.get("source_type") in INLINE_VALUE_SOURCE_TYPES
    )
DATA_MAP_KEYS = {
    "workout_data": "workout",
    "live_data": "live",
    "recovery_data": "sleep",
    "evaluation_data": "evaluation",
}
DATA_MAP_KIND_TO_KEY = {kind: key for key, kind in DATA_MAP_KEYS.items()}

LIVE_RAW_ROUTE_KEYS = {
    "current_heart_rate": METRIC_HEART_RATE,
    "current_power": METRIC_POWER,
    "current_cadence": METRIC_CADENCE,
    "current_speed": METRIC_SPEED,
    "current_distance": METRIC_DISTANCE,
    "current_altitude": METRIC_ALTITUDE,
}

# Non-sensor entities that belong to the same profile devices and are useful to
# the dashboard.  Sensor entities are discovered from DESCRIPTIONS passed by the
# sensor platform so this table cannot accidentally re-introduce mirror sensors.
PROFILE_CONTROL_ENTITIES: dict[str, tuple[tuple[str, str], ...]] = {
    "live": (
        ("start_workout", "button"),
        ("pause_workout", "button"),
        ("resume_workout", "button"),
        ("stop_workout", "button"),
        ("workout_room", "select"),
    ),
    "workout": (
        ("session_rpe", "number"),
        ("workouts", "calendar"),
    ),
    "sleep": (),
    "evaluation": (
        ("regenerate_ai", "button"),
    ),
}


def _registry_entity_id(
    hass,
    *,
    unique_id: str,
    domains: Iterable[str],
) -> str | None:
    """Resolve an entity by unique ID without assuming its user-visible ID."""
    registry = er.async_get(hass)
    getter = getattr(registry, "async_get_entity_id", None)
    if callable(getter):
        for domain in domains:
            try:
                entity_id = getter(domain, DOMAIN, unique_id)
            except (TypeError, AttributeError):
                entity_id = None
            if entity_id:
                return entity_id

    # Test doubles and older HA registry facades may not expose
    # async_get_entity_id().  This fallback runs only when a route map is being
    # rebuilt, never on metric updates.
    entities = getattr(registry, "entities", {})
    values = entities.values() if hasattr(entities, "values") else ()
    for item in values:
        if getattr(item, "platform", None) != DOMAIN:
            continue
        if getattr(item, "unique_id", None) != unique_id:
            continue
        entity_id = getattr(item, "entity_id", None)
        if entity_id and entity_id.split(".", 1)[0] in set(domains):
            return entity_id
    return None


def _profile_entity_id(hass, entry, key: str, domain: str = "sensor") -> str | None:
    return _registry_entity_id(
        hass,
        unique_id=f"{entry.entry_id}_{key}",
        domains=(domain,),
    )


def _physical_metric_entity_id(hass, sensor_id: str, metric: str) -> str | None:
    return _registry_entity_id(
        hass,
        unique_id=f"fitness_{sensor_id}_{metric}",
        domains=("sensor",),
    )


def _fitness_owned_routes(hass, entry, kind: str, descriptions) -> dict[str, dict[str, Any]]:
    """Return routes for entities genuinely owned by a profile device."""
    routes: dict[str, dict[str, Any]] = {}
    for desc in descriptions:
        if desc.kind != kind or desc.key in DATA_MAP_KEYS:
            continue
        entity_id = _profile_entity_id(hass, entry, desc.key)
        if entity_id:
            routes[desc.key] = {
                "entity_id": entity_id,
                "transform": "state",
                "source_type": "fitness",
            }

    for key, domain in PROFILE_CONTROL_ENTITIES.get(kind, ()):
        entity_id = _profile_entity_id(hass, entry, key, domain)
        if entity_id:
            routes[key] = {
                "entity_id": entity_id,
                "transform": "state",
                "source_type": "fitness_control",
            }
    return routes


def _live_raw_routes(hass, manager, entry) -> dict[str, dict[str, Any]]:
    """Route raw live metrics to the actual entity feeding this profile."""
    runtime = get_live_runtime(hass)
    active_sources = runtime.measurement_sources.get(entry.entry_id, {})
    selected_ids = runtime.selected_sensor_ids(entry)
    sensors = runtime.sensors_for_profile(entry)
    routes: dict[str, dict[str, Any]] = {}

    # Legacy/provider entity sources remain valid fallback inputs for profiles
    # that do not use Fitness physical sensors.
    manager_sources = getattr(manager, "_live_sources_cache", {}) or {}

    for dashboard_key, metric in LIVE_RAW_ROUTE_KEYS.items():
        sensor_id = active_sources.get(metric)
        if sensor_id is not None:
            sensor_id = runtime.resolve_sensor_id(sensor_id)

        if sensor_id is None:
            # While idle there is no profile measurement owner.  Select only from
            # physical sensors explicitly assigned to this profile. Prefer a
            # sensor that already produced the metric, then an available sensor
            # advertising that capability.
            candidates = []
            for sensor in sensors:
                sid = runtime.resolve_sensor_id(sensor.sensor_id)
                has_value = metric in runtime.sensor_values.get(sid, {})
                has_capability = metric in set(sensor.capabilities or ())
                available = bool(sensor.available)
                if has_value or has_capability:
                    candidates.append((has_value, available, sid))
            if candidates:
                candidates.sort(reverse=True)
                sensor_id = candidates[0][2]

        entity_id = (
            _physical_metric_entity_id(hass, sensor_id, metric)
            if sensor_id is not None
            else None
        )
        source_type = "physical_sensor"
        if not entity_id:
            source = manager_sources.get(metric)
            entity_id = getattr(source, "entity_id", None)
            source_type = "source_entity"

        if entity_id:
            routes[dashboard_key] = {
                "entity_id": entity_id,
                "transform": "state",
                "field": metric,
                "source_type": source_type,
            }
    return routes


def _evaluation_input_routes(hass, manager) -> dict[str, dict[str, Any]]:
    """Return provider/profile input routes without building Evaluation output."""
    # Importing the public dashboard constants here would create a module cycle,
    # so keep this small routing vocabulary local and stable.
    source_fields: dict[str, tuple[str, str | None]] = {
        "vo2max": ("vo2max", "mL/kg/min"),
        "resting_hr": ("resting_hr", "bpm"),
        "hrv_last_night": ("hrv_last_night", "ms"),
        "hrv_weekly": ("hrv_weekly", "ms"),
        "weight": ("weight_kg", "kg"),
        "training_readiness": ("training_readiness", None),
        "provider_sleep_score": ("sleep_score", None),
    }
    provider = collect_provider_metrics(hass, manager.config)
    config_fallbacks = {
        "vo2max": "vo2max",
        "resting_hr": "resting_hr",
        "weight": "weight",
    }
    routes: dict[str, dict[str, Any]] = {}
    for dashboard_key, (provider_key, unit) in source_fields.items():
        entity_id = provider.get(f"{provider_key}_entity")
        if not entity_id and dashboard_key in config_fallbacks:
            configured = manager.config.get(config_fallbacks[dashboard_key])
            if isinstance(configured, str) and "." in configured:
                entity_id = configured.strip()
            elif configured is not None:
                # A profile-entered number is Fitness-owned configuration, not a
                # mirror of another integration. Expose it only as a routing
                # fallback so the dashboard can retain the previous display.
                routes[dashboard_key] = {
                    "transform": "configured",
                    "field": provider_key,
                    "unit": unit,
                    "source_type": "fitness_config",
                    "configured_value": configured,
                }
                continue
        if entity_id and hass.states.get(entity_id) is not None:
            routes[dashboard_key] = {
                "entity_id": entity_id,
                "transform": "state",
                "field": provider_key,
                "unit": unit,
                "source_type": "source",
            }
    return routes


def build_profile_routes(hass, manager, entry, kind: str, descriptions) -> dict[str, dict[str, Any]]:
    """Build one profile-device route table.

    The returned mapping is a routing contract. Source-owned values remain
    pointers to their real HA entities. A small class of *substitute facts* that
    Fitness calculates only because the source omitted that fact may carry an
    inline value; these are never materialized as separate Fitness entities.
    """
    routes = _fitness_owned_routes(hass, entry, kind, descriptions)

    if kind == "live":
        routes.update(_live_raw_routes(hass, manager, entry))
        return routes

    if kind == "workout":
        # Route factual latest-workout fields to the provider that owns each
        # field. For a Fitness Live-created workout, fields actually captured by
        # Fitness route back to the legitimate Fitness workout entities.
        from .dashboard import _workout_source_metrics

        profile_entities = {
            key: route["entity_id"]
            for key, route in routes.items()
            if route.get("entity_id")
        }
        latest = manager.latest_workout()
        source_routes = _workout_source_metrics(
            hass, manager, latest, profile_entities
        )
        for key, route in source_routes.items():
            # Persist an inline value only for a genuine Fitness fallback fact.
            # Canonical/provider values remain on their source entities and are
            # deliberately not copied into the map sensor.
            keep_value = _route_keeps_inline_value(route)
            routes[key] = {
                field: value
                for field, value in route.items()
                if field != "value" or keep_value
            }
        return routes

    if kind == "sleep":
        from .dashboard import _sleep_source_metrics

        latest = manager.latest_sleep()
        source_routes = _sleep_source_metrics(hass, latest)
        for key, route in source_routes.items():
            # Persist an inline value only for a genuine Fitness fallback fact.
            # Canonical/provider values remain on their source entities and are
            # deliberately not copied into the map sensor.
            keep_value = _route_keeps_inline_value(route)
            routes[key] = {
                field: value
                for field, value in route.items()
                if field != "value" or keep_value
            }
        return routes

    if kind == "evaluation":
        routes.update(_evaluation_input_routes(hass, manager))
        return routes

    return routes


def routes_to_attributes(kind: str, routes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Flatten route metadata into stable Home Assistant sensor attributes."""
    attrs: dict[str, Any] = {
        "schema_version": DATA_MAP_SCHEMA_VERSION,
        "map_kind": "recovery" if kind == "sleep" else kind,
        "mapped_keys": sorted(routes),
        "route_count": len(routes),
    }
    direct_count = 0
    for key in sorted(routes):
        route = routes[key]
        entity_id = route.get("entity_id")
        if entity_id:
            attrs[f"{key}_source"] = entity_id
            direct_count += 1
        for suffix, field in (
            ("attribute", "attribute"),
            ("transform", "transform"),
            ("unit", "unit"),
            ("field", "field"),
            ("source_type", "source_type"),
            ("configured_value", "configured_value"),
            ("method", "method"),
        ):
            value = route.get(field)
            if value is not None:
                attrs[f"{key}_{suffix}"] = value

        # Inline values are allowed only for low-frequency substitute facts that
        # Fitness calculated because the source did not provide that field. This
        # is intentionally *not* a general value mirror mechanism.
        if (
            _route_keeps_inline_value(route)
            and route.get("value") is not None
        ):
            attrs[f"{key}_value"] = route["value"]
    attrs["direct_source_count"] = direct_count
    return attrs


def routes_from_attributes(attributes: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Reconstruct route objects from one data-map sensor state."""
    attributes = attributes or {}
    keys = attributes.get("mapped_keys") or []
    if not isinstance(keys, (list, tuple, set)):
        return {}
    routes: dict[str, dict[str, Any]] = {}
    for raw_key in keys:
        key = str(raw_key)
        route: dict[str, Any] = {}
        source = attributes.get(f"{key}_source")
        if source:
            route["entity_id"] = source
        for suffix, field in (
            ("attribute", "attribute"),
            ("transform", "transform"),
            ("unit", "unit"),
            ("field", "field"),
            ("source_type", "source_type"),
            ("configured_value", "configured_value"),
            ("method", "method"),
            ("value", "value"),
        ):
            value = attributes.get(f"{key}_{suffix}")
            if value is not None:
                route[field] = value
        if route:
            routes[key] = route
    return routes
