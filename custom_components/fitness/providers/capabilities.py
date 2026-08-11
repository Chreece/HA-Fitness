"""Central capability discovery for Fitness setup and runtime contracts.

A device or entity is offered by setup only when the same parser used at runtime
can understand it. This prevents configuration from advertising arbitrary Home
Assistant devices that Fitness cannot safely consume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ..const import (
    CONF_HEIGHT,
    CONF_LIVE_DEVICE_IDS,
    CONF_MAX_HR,
    CONF_RESTING_HR,
    CONF_SLEEP_DEVICE_IDS,
    CONF_THRESHOLD_HR,
    CONF_THRESHOLD_PACE,
    CONF_THRESHOLD_POWER,
    CONF_VO2MAX,
    CONF_WEIGHT,
    CONF_WORKOUT_DEVICE_IDS,
)
from .devices import discover_candidates
from .entities import convert_to_canonical
from .evaluation import workout_device_entity_ids
from .sleep_adapters.registry import EXPLICIT_DOMAINS, sleep_device_entity_ids


@dataclass(frozen=True, slots=True)
class CapabilityChoice:
    """One setup-safe device choice."""

    value: str
    label: str
    domains: tuple[str, ...] = ()
    details: tuple[str, ...] = ()

    def as_selector_option(self) -> dict[str, str]:
        suffix = f" — {', '.join(self.details)}" if self.details else ""
        return {"value": self.value, "label": f"{self.label}{suffix}"}


_PROFILE_QUANTITY = {
    CONF_WEIGHT: "weight",
    CONF_RESTING_HR: "heart_rate",
    CONF_HEIGHT: "height",
    CONF_MAX_HR: "heart_rate",
    CONF_VO2MAX: "vo2max",
    CONF_THRESHOLD_HR: "heart_rate",
    CONF_THRESHOLD_PACE: "pace",
    CONF_THRESHOLD_POWER: "power",
}

_PROFILE_ALIASES = {
    CONF_WEIGHT: ("weight", "body_weight", "body_mass"),
    CONF_RESTING_HR: ("resting_heart_rate", "resting_hr", "restingheartrate"),
    CONF_HEIGHT: ("height", "body_height"),
    CONF_MAX_HR: ("max_heart_rate", "maximum_heart_rate", "max_hr", "maximum_hr"),
    CONF_VO2MAX: ("vo2_max", "vo2max", "vo2_maximum"),
    CONF_THRESHOLD_HR: (
        "lactate_threshold_heart_rate",
        "lactate_threshold_hr",
        "threshold_heart_rate",
        "threshold_hr",
    ),
    CONF_THRESHOLD_PACE: (
        "lactate_threshold_pace",
        "threshold_pace",
        "lactate_threshold_speed",
        "threshold_speed",
    ),
    CONF_THRESHOLD_POWER: (
        "functional_threshold_power",
        "threshold_power",
        "ftp_running",
        "ftp_cycling",
        "ftp",
    ),
}



# Generic discovery must be conservative. A coincidental unit/name such as
# "distance" or "power" is not enough to turn a room sensor, appliance or
# vehicle into a Fitness source.
_LIVE_EXPLICIT_DOMAINS = {"antplus", "ant_plus", "stryd_ble"}
_LIVE_STRONG_GENERIC_METRICS = {"heart_rate"}
_LIVE_BLOCKED_DOMAINS = {"fitness", "mobile_app"}
_SLEEP_BLOCKED_GENERIC_DOMAINS = {"fitness", "mobile_app"}

_PROFILE_BLOCKED_DOMAINS = {"fitness"}
_PROFILE_BAD_TOKENS = {
    CONF_WEIGHT: (
        "lean_body_mass", "lean_mass", "fat_free_mass", "muscle_mass",
        "bone_mass", "nominal_load", "washing", "drying", "laundry",
        "payload", "load_weight", "maximum_load", "max_load",
    ),
    CONF_RESTING_HR: ("maximum", "max_", "threshold", "workout", "exercise"),
    CONF_HEIGHT: ("altitude", "elevation"),
    CONF_MAX_HR: ("resting", "threshold"),
    CONF_VO2MAX: (),
    CONF_THRESHOLD_HR: ("resting", "maximum"),
    CONF_THRESHOLD_PACE: ("current", "live"),
    CONF_THRESHOLD_POWER: ("current", "live", "battery", "plug", "consumption"),
}

_HEALTH_PROFILE_DOMAINS = {
    "garmin_connect", "withings", "fitbit", "oura", "whoop", "hevy",
    "google_fit", "health_connect", "samsung_health",
}

def _norm(value) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _device_domains(hass: HomeAssistant, device) -> tuple[str, ...]:
    entry_ids = set(getattr(device, "config_entries", None) or [])
    legacy = getattr(device, "config_entry_id", None)
    if legacy:
        entry_ids.add(legacy)
    result = set()
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None:
            result.add(entry.domain)
    return tuple(sorted(result))


def _device_name(device) -> str:
    return (
        getattr(device, "name_by_user", None)
        or getattr(device, "name", None)
        or getattr(device, "model", None)
        or device.id
    )


def _entry_label(hass: HomeAssistant, entry) -> str:
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


def _all_devices(hass: HomeAssistant):
    """Return selectable source devices, never Fitness's own output devices."""
    devices = []
    for device in dr.async_get(hass).devices.values():
        # Fitness-generated Evaluation/Live/Sleep/Workout devices are outputs,
        # never valid inputs. Excluding them centrally guarantees every setup
        # selector follows the same no-feedback-loop rule.
        if "fitness" in set(_device_domains(hass, device)):
            continue
        devices.append(device)
    return sorted(
        devices,
        key=lambda device: (_device_name(device).lower(), device.id),
    )


def live_device_choices(hass: HomeAssistant) -> list[CapabilityChoice]:
    """Return only plausible fitness devices with parseable live metrics.

    Known ANT+/Stryd providers may expose any supported live metric. Unknown
    devices must contain a strongly fitness-specific signal: heart rate by
    itself, or cadence together with another exercise metric. Speed, distance,
    altitude or electrical power alone never qualify a generic HA device.
    """
    result = []
    for device in _all_devices(hass):
        domains = set(_device_domains(hass, device))
        if domains.intersection(_LIVE_BLOCKED_DOMAINS):
            continue
        config = {CONF_LIVE_DEVICE_IDS: [device.id]}
        candidates = discover_candidates(hass, config)
        metrics = {metric for metric, items in candidates.items() if items}
        if not metrics:
            continue

        explicit = bool(domains.intersection(_LIVE_EXPLICIT_DOMAINS))
        strong_generic = bool(metrics.intersection(_LIVE_STRONG_GENERIC_METRICS))
        multi_metric_fitness = (
            "cadence" in metrics
            and bool(metrics.intersection({"power", "speed", "distance"}))
        )
        if not (explicit or strong_generic or multi_metric_fitness):
            continue

        result.append(
            CapabilityChoice(
                device.id,
                _device_name(device),
                tuple(sorted(domains)),
                tuple(sorted(metrics)),
            )
        )
    return result


def workout_device_choices(hass: HomeAssistant) -> list[CapabilityChoice]:
    """Devices with entities matching the completed-workout runtime contract."""
    result = []
    for device in _all_devices(hass):
        config = {CONF_WORKOUT_DEVICE_IDS: [device.id]}
        triggers = workout_device_entity_ids(hass, config)
        if not triggers:
            continue
        domains = _device_domains(hass, device)
        details = tuple(domains) or ("generic workout",)
        result.append(CapabilityChoice(device.id, _device_name(device), domains, details))
    return result


def sleep_device_choices(hass: HomeAssistant) -> list[CapabilityChoice]:
    """Return only devices with a sleep contract Fitness will actually parse."""
    result = []
    for device in _all_devices(hass):
        config = {CONF_SLEEP_DEVICE_IDS: [device.id]}
        triggers = sleep_device_entity_ids(hass, config)
        if not triggers:
            continue
        domains = set(_device_domains(hass, device))
        explicit = bool(domains.intersection(EXPLICIT_DOMAINS))
        if not explicit and domains.intersection(_SLEEP_BLOCKED_GENERIC_DOMAINS):
            continue
        details = tuple(sorted(domains)) or ("generic sleep",)
        result.append(
            CapabilityChoice(device.id, _device_name(device), tuple(sorted(domains)), details)
        )
    return result


def supported_device_ids(hass: HomeAssistant, capability: str) -> set[str]:
    choices = {
        "live": live_device_choices,
        "workout": workout_device_choices,
        "sleep": sleep_device_choices,
    }[capability](hass)
    return {item.value for item in choices}


def profile_entity_choices(hass: HomeAssistant, field: str) -> list[dict[str, str]]:
    """Return plausible physiological entities, ranked best-first.

    Unit compatibility alone is intentionally insufficient: kilograms from a
    washing machine or power from a plug must never be offered as profile data.
    """
    quantity = _PROFILE_QUANTITY[field]
    aliases = _PROFILE_ALIASES[field]
    bad_tokens = _PROFILE_BAD_TOKENS[field]
    registry = er.async_get(hass)
    ranked: list[tuple[int, str, dict[str, str]]] = []

    for entry in registry.entities.values():
        if not entry.entity_id.startswith("sensor."):
            continue
        state = hass.states.get(entry.entity_id)
        if state is None or state.state in ("unknown", "unavailable", ""):
            continue

        domain = None
        if entry.config_entry_id:
            config_entry = hass.config_entries.async_get_entry(entry.config_entry_id)
            domain = config_entry.domain if config_entry is not None else None
        if domain in _PROFILE_BLOCKED_DOMAINS:
            continue

        label = _entry_label(hass, entry)
        if any(token in label for token in bad_tokens):
            continue
        matched = [alias for alias in aliases if alias in label]
        if not matched:
            continue

        try:
            number = float(state.state)
        except (TypeError, ValueError):
            continue
        converted, _canonical = convert_to_canonical(
            number,
            state.attributes.get("unit_of_measurement"),
            quantity,
        )
        if converted is None:
            continue

        friendly = state.attributes.get("friendly_name") or entry.original_name or entry.entity_id
        unit = state.attributes.get("unit_of_measurement")
        display = f"{friendly} — {entry.entity_id}"
        if unit:
            display += f" [{unit}]"

        # Exact physiological names outrank generic substring matches; known
        # health/fitness providers outrank unknown integrations.
        entity_tail = _norm(entry.entity_id.split(".", 1)[-1])
        friendly_norm = _norm(friendly)
        exact_alias = any(entity_tail == alias or friendly_norm == alias for alias in aliases)
        score = 100 if exact_alias else 50
        if domain in _HEALTH_PROFILE_DOMAINS:
            score += 30
        if field == CONF_WEIGHT and ("body_weight" in label or friendly_norm == "weight"):
            score += 20

        ranked.append((score, display.lower(), {"value": entry.entity_id, "label": display}))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked]
