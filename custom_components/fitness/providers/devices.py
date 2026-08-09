"""Live metric discovery from selected devices or automatic ANT+ devices."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ..const import (
    ANTPLUS_DOMAINS,
    CONF_LIVE_DEVICE_IDS,
    LIVE_METRICS,
    METRIC_ALTITUDE,
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
)


@dataclass(slots=True)
class MetricSource:
    metric: str
    entity_id: str
    device_id: str | None
    score: int
    available_numeric: bool


def _domain(hass: HomeAssistant, config_entry_id: str | None) -> str | None:
    if not config_entry_id:
        return None
    entry = hass.config_entries.async_get_entry(config_entry_id)
    return entry.domain if entry else None


def _auto_antplus_devices(hass: HomeAssistant) -> list[str]:
    registry = dr.async_get(hass)
    ids: list[str] = []
    for device in registry.devices.values():
        entry_id = getattr(device, "config_entry_id", None)
        if _domain(hass, entry_id) in ANTPLUS_DOMAINS:
            ids.append(device.id)
            continue
        entries = getattr(device, "config_entries", None) or []
        if any(_domain(hass, eid) in ANTPLUS_DOMAINS for eid in entries):
            ids.append(device.id)
    return ids


def source_device_ids(hass: HomeAssistant, config: dict) -> list[str]:
    selected = list(config.get(CONF_LIVE_DEVICE_IDS) or [])
    return selected or _auto_antplus_devices(hass)


def _text(hass: HomeAssistant, entry: er.RegistryEntry) -> str:
    state = hass.states.get(entry.entity_id)
    values = [
        entry.entity_id,
        entry.name or "",
        entry.original_name or "",
        str(state.attributes.get("friendly_name") or "") if state else "",
    ]
    return " ".join(values).lower().replace(" ", "_").replace("-", "_")


def _unit(hass: HomeAssistant, entry: er.RegistryEntry) -> str:
    state = hass.states.get(entry.entity_id)
    if not state:
        return ""
    return str(state.attributes.get("unit_of_measurement") or "").lower().strip()


def _device_class(hass: HomeAssistant, entry: er.RegistryEntry) -> str:
    dc = entry.device_class or entry.original_device_class
    if dc:
        return str(dc).lower()
    state = hass.states.get(entry.entity_id)
    return str(state.attributes.get("device_class") or "").lower() if state else ""


def _available(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    if not state or state.state in ("unknown", "unavailable", ""):
        return False
    try:
        float(state.state)
        return True
    except (TypeError, ValueError):
        return False


def _score(hass: HomeAssistant, entry: er.RegistryEntry, metric: str) -> int:
    text = _text(hass, entry)
    unit = _unit(hass, entry)
    dc = _device_class(hass, entry)
    score = 0

    if metric == METRIC_HEART_RATE:
        if dc in ("heart_rate", "heart rate"):
            score += 100
        if unit in ("bpm", "beats/min", "beats/minute"):
            score += 80
        if any(x in text for x in ("heart_rate", "heartrate", "hrm", "pulse")):
            score += 45

    elif metric == METRIC_POWER:
        if dc == "power":
            score += 100
        if unit in ("w", "watt", "watts"):
            score += 75
        if "power" in text or "watt" in text:
            score += 40
        if any(x in text for x in ("battery", "signal", "rssi")):
            score -= 120

    elif metric == METRIC_CADENCE:
        if dc == "cadence":
            score += 100
        if unit in ("rpm", "spm", "steps/min", "steps/minute"):
            score += 65
        if "cadence" in text:
            score += 45

    elif metric == METRIC_SPEED:
        if dc == "speed":
            score += 100
        if unit in ("km/h", "kph", "mph", "m/s"):
            score += 75
        if "speed" in text or "velocity" in text:
            score += 40

    elif metric == METRIC_DISTANCE:
        if dc == "distance":
            score += 100
        if unit in ("m", "km", "mi", "mile", "miles"):
            score += 40
        if "distance" in text or "odometer" in text:
            score += 45
        if any(x in text for x in ("altitude", "elevation", "stride_length")):
            score -= 70

    elif metric == METRIC_ALTITUDE:
        if dc == "altitude":
            score += 100
        if any(x in text for x in ("altitude", "elevation")):
            score += 70
        if unit in ("m", "ft"):
            score += 20

    return score


def discover_candidates(hass: HomeAssistant, config: dict) -> dict[str, list[MetricSource]]:
    device_ids = set(source_device_ids(hass, config))
    registry = er.async_get(hass)
    result = {metric: [] for metric in LIVE_METRICS}

    for entry in registry.entities.values():
        if entry.device_id not in device_ids:
            continue
        if not entry.entity_id.startswith("sensor."):
            continue

        for metric in LIVE_METRICS:
            score = _score(hass, entry, metric)
            if score >= 50:
                result[metric].append(
                    MetricSource(
                        metric=metric,
                        entity_id=entry.entity_id,
                        device_id=entry.device_id,
                        score=score,
                        available_numeric=_available(hass, entry.entity_id),
                    )
                )

    for items in result.values():
        items.sort(
            key=lambda x: (-int(x.available_numeric), -x.score, x.entity_id)
        )
    return result


def discover_sources(hass: HomeAssistant, config: dict) -> dict[str, MetricSource]:
    return {
        metric: items[0]
        for metric, items in discover_candidates(hass, config).items()
        if items
    }


def all_live_candidate_entity_ids(hass: HomeAssistant, config: dict) -> list[str]:
    ids = {
        item.entity_id
        for items in discover_candidates(hass, config).values()
        for item in items
    }
    return sorted(ids)
