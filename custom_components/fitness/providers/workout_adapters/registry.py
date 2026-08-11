"""Registry for maintainable completed-workout provider support."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from . import fitbit, garmin, generic, hevy, oura, peloton, polar, strava, suunto, whoop, withings
from .base import (
    WorkoutAdapterSpec,
    selected_device_ids_for_domains,
    selected_provider_domains,
)

ADAPTERS: tuple[WorkoutAdapterSpec, ...] = (
    WorkoutAdapterSpec("garmin", garmin.DOMAINS, garmin.discover),
    WorkoutAdapterSpec("strava", strava.DOMAINS, strava.discover),
    WorkoutAdapterSpec("polar", polar.DOMAINS, polar.discover),
    WorkoutAdapterSpec("hevy", hevy.DOMAINS, hevy.discover),
    WorkoutAdapterSpec("peloton", peloton.DOMAINS, peloton.discover),
    WorkoutAdapterSpec("oura", oura.DOMAINS, oura.discover),
    WorkoutAdapterSpec("whoop", whoop.DOMAINS, whoop.discover),
    WorkoutAdapterSpec("suunto", suunto.DOMAINS, suunto.discover),
    WorkoutAdapterSpec("fitbit", fitbit.DOMAINS, fitbit.discover),
    WorkoutAdapterSpec("withings", withings.DOMAINS, withings.discover),
)

EXPLICIT_DOMAINS = frozenset(
    domain for adapter in ADAPTERS for domain in adapter.domains
)


@dataclass(slots=True)
class AdapterDiagnostic:
    adapter: str
    domains: list[str]
    selected_devices: int
    explicit_workouts: int = 0
    fallback_workouts: int = 0
    status: str = "not_selected"
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_LAST_DIAGNOSTICS: dict[str, dict[str, Any]] = {}


def supported_adapter_domains() -> dict[str, tuple[str, ...]]:
    return {adapter.name: adapter.domains for adapter in ADAPTERS}


def last_adapter_diagnostics() -> dict[str, dict[str, Any]]:
    return {key: dict(value) for key, value in _LAST_DIAGNOSTICS.items()}


def _mark_fallback(items: list, adapter_name: str) -> list:
    for workout in items:
        workout.extra["fitness_adapter"] = f"{adapter_name}:generic_fallback"
        workout.extra["fitness_adapter_fallback"] = True
    return items


def discover_all(hass: HomeAssistant, config: dict) -> list:
    """Explicit adapter -> scoped generic fallback -> safe ignore."""
    global _LAST_DIAGNOSTICS

    result = []
    diagnostics: dict[str, dict[str, Any]] = {}

    for adapter in ADAPTERS:
        device_ids = selected_device_ids_for_domains(
            hass, config, adapter.domains
        )
        diag = AdapterDiagnostic(
            adapter=adapter.name,
            domains=list(adapter.domains),
            selected_devices=len(device_ids),
        )

        if not device_ids:
            diagnostics[adapter.name] = diag.as_dict()
            continue

        explicit = []
        try:
            explicit = [
                item for item in adapter.discover(hass, config)
                if item is not None
            ]
        except Exception as err:
            diag.error = f"{type(err).__name__}: {err}"

        diag.explicit_workouts = len(explicit)

        if explicit:
            diag.status = "explicit"
            result.extend(explicit)
            diagnostics[adapter.name] = diag.as_dict()
            continue

        fallback = _mark_fallback(
            generic.discover(
                hass,
                config,
                only_domains=set(adapter.domains),
                only_device_ids=device_ids,
            ),
            adapter.name,
        )
        diag.fallback_workouts = len(fallback)

        if fallback:
            diag.status = "generic_fallback"
            result.extend(fallback)
        else:
            diag.status = "no_usable_workout"

        diagnostics[adapter.name] = diag.as_dict()

    selected_domains = selected_provider_domains(hass, config)
    unknown_device_ids = {
        device_id
        for device_id, domains in selected_domains.items()
        if domains.isdisjoint(EXPLICIT_DOMAINS)
    }

    generic_unknown = []
    if unknown_device_ids:
        generic_unknown = generic.discover(
            hass,
            config,
            exclude_domains=set(EXPLICIT_DOMAINS),
            only_device_ids=unknown_device_ids,
        )
        for workout in generic_unknown:
            workout.extra.setdefault("fitness_adapter", "generic")
        result.extend(generic_unknown)

    diagnostics["generic"] = {
        "adapter": "generic",
        "domains": sorted({
            domain
            for device_id in unknown_device_ids
            for domain in selected_domains.get(device_id, set())
        }),
        "selected_devices": len(unknown_device_ids),
        "explicit_workouts": 0,
        "fallback_workouts": len(generic_unknown),
        "status": (
            "generic" if generic_unknown
            else ("no_usable_workout" if unknown_device_ids else "not_selected")
        ),
        "error": None,
    }

    _LAST_DIAGNOSTICS = diagnostics
    return result
