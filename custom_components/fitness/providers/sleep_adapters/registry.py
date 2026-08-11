"""Provider-specific and generic normalized sleep adapters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

from homeassistant.helpers import entity_registry as er

from ...const import CONF_SLEEP_DEVICE_IDS
from ..sleep import SleepRecord, newest_sleep


@dataclass(frozen=True, slots=True)
class SleepAdapterSpec:
    name: str
    domains: tuple[str, ...]
    fields: dict[str, tuple[str, ...]]


SPECS: tuple[SleepAdapterSpec, ...] = (
    SleepAdapterSpec("garmin", ("garmin_connect",), {
        "duration_s": ("total_sleep_duration", "sleep_duration"),
        "awake_s": ("awake_duration",),
        "light_sleep_s": ("light_sleep",),
        "deep_sleep_s": ("deep_sleep",),
        "rem_sleep_s": ("rem_sleep",),
        "score": ("sleep_score",),
        "hrv_ms": ("hrv_last_night_average", "hrv_last_night"),
        "sleep_need_s": ("sleep_need",),
        "start": ("bedtime",),
        "end": ("wake_time",),
    }),
    SleepAdapterSpec("oura", ("oura",), {
        "duration_s": ("total_sleep_duration",),
        "time_in_bed_s": ("time_in_bed",),
        "awake_s": ("awake_time",),
        "light_sleep_s": ("light_sleep_duration",),
        "deep_sleep_s": ("deep_sleep_duration",),
        "rem_sleep_s": ("rem_sleep_duration",),
        "sleep_latency_s": ("sleep_latency",),
        "score": ("sleep_score",),
        "efficiency_percent": ("sleep_efficiency",),
        "average_hr": ("average_sleep_heart_rate",),
        "minimum_hr": ("lowest_sleep_heart_rate",),
        "hrv_ms": ("average_sleep_hrv",),
        "readiness_score": ("readiness_score",),
        "start": ("bedtime_start",),
        "end": ("bedtime_end",),
    }),
    SleepAdapterSpec("fitbit", ("fitbit",), {
        "duration_s": ("minutes_asleep", "minutesasleep", "sleep_duration"),
        "time_in_bed_s": ("time_in_bed", "timeinbed"),
        "awake_s": ("minutes_awake", "minutesawake"),
        "sleep_latency_s": ("minutes_to_fall_asleep", "minutestofallasleep"),
        "efficiency_percent": ("sleep_efficiency", "efficiency"),
        "disturbance_count": ("awakenings_count", "awakeningscount"),
    }),
    SleepAdapterSpec("withings", ("withings",), {
        "deep_sleep_s": ("sleep_deep_duration",),
        "light_sleep_s": ("sleep_light_duration",),
        "rem_sleep_s": ("sleep_rem_duration",),
        "awake_s": ("sleep_wakeup_duration",),
        "sleep_latency_s": ("sleep_tosleep_duration",),
        "score": ("sleep_score",),
        "average_hr": ("sleep_heart_rate_average",),
        "respiratory_rate": ("sleep_respiratory_average",),
        "disturbance_count": ("sleep_wakeup_count",),
        "in_bed": ("in_bed",),
    }),
    SleepAdapterSpec("whoop", ("whoop",), {
        "score": ("sleep_performance",),
        "efficiency_percent": ("sleep_efficiency",),
        "time_in_bed_s": ("time_in_bed", "total_in_bed_time"),
        "awake_s": ("awake_time", "total_awake_time"),
        "light_sleep_s": ("light_sleep", "total_light_sleep_time"),
        "deep_sleep_s": ("sws_time", "slow_wave_sleep", "total_slow_wave_sleep_time"),
        "rem_sleep_s": ("rem_sleep", "total_rem_sleep_time"),
        "respiratory_rate": ("respiratory_rate",),
        "sleep_cycle_count": ("sleep_cycle",),
        "disturbance_count": ("disturbance",),
        "sleep_need_s": ("sleep_need", "baseline_need"),
        "sleep_debt_s": ("sleep_debt",),
        "recovery_score": ("recovery_score",),
        "hrv_ms": ("hrv",),
        "average_hr": ("resting_heart_rate",),
        "spo2_percent": ("spo2",),
    }),
    SleepAdapterSpec("suunto", ("suunto",), {
        "duration_s": ("sleep_duration", "total_sleep"),
        "deep_sleep_s": ("deep_sleep",),
        "rem_sleep_s": ("rem_sleep",),
        "awake_s": ("awake_time",),
        "score": ("sleep_score",),
        "hrv_ms": ("hrv",),
        "average_hr": ("sleep_heart_rate", "resting_heart_rate"),
        "recovery_score": ("recovery_score",),
    }),
    SleepAdapterSpec("sleepiq", ("sleepiq",), {
        "duration_s": ("sleep_duration",),
        "score": ("sleep_score", "sleep_number"),
        "average_hr": ("heart_rate_avg", "heart_rate_average"),
        "hrv_ms": ("hrv",),
        "respiratory_rate": ("respiratory_rate_avg", "respiratory_rate_average"),
        "in_bed": ("is_in_bed", "in_bed"),
    }),
    SleepAdapterSpec("eight_sleep", ("eight_sleep", "eightsleep"), {
        "duration_s": ("sleep_duration",),
        "score": ("sleep_score",),
        "time_in_bed_s": ("time_in_bed",),
        "deep_sleep_s": ("deep_sleep",),
        "light_sleep_s": ("light_sleep",),
        "rem_sleep_s": ("rem_sleep",),
        "awake_s": ("awake",),
        "average_hr": ("heart_rate",),
        "hrv_ms": ("hrv",),
        "respiratory_rate": ("respiratory_rate",),
        "in_bed": ("bed_presence", "in_bed"),
    }),
    SleepAdapterSpec("sleep_as_android", ("sleep_as_android",), {
        # HACS variants may expose aggregate sensors. Core HA mainly exposes
        # event entities; those are handled below as a basic start/stop record.
        "duration_s": ("sleep_duration",),
        "deep_sleep_s": ("deep_sleep_duration", "deep_sleep_percent"),
        "score": ("sleep_score", "sleep_quality"),
        "average_hr": ("sleep_heart_rate",),
    }),
)

EXPLICIT_DOMAINS = frozenset(domain for spec in SPECS for domain in spec.domains)
DURATION_FIELDS = {
    "duration_s", "time_in_bed_s", "awake_s", "light_sleep_s",
    "deep_sleep_s", "rem_sleep_s", "sleep_latency_s", "sleep_need_s",
    "sleep_debt_s",
}
GENERIC_FIELDS = {
    "duration_s": ("sleep_duration", "total_sleep_duration", "minutes_asleep"),
    "time_in_bed_s": ("time_in_bed",),
    "awake_s": ("awake_duration", "awake_time", "minutes_awake"),
    "light_sleep_s": ("light_sleep",),
    "deep_sleep_s": ("deep_sleep", "slow_wave_sleep"),
    "rem_sleep_s": ("rem_sleep",),
    "sleep_latency_s": ("sleep_latency", "time_to_sleep"),
    "score": ("sleep_score", "sleep_quality"),
    "efficiency_percent": ("sleep_efficiency",),
    "average_hr": ("sleep_heart_rate", "average_sleep_heart_rate"),
    "hrv_ms": ("sleep_hrv", "average_sleep_hrv"),
    "respiratory_rate": ("sleep_respiratory", "respiratory_rate"),
    "spo2_percent": ("sleep_spo2", "spo2"),
    "readiness_score": ("readiness_score",),
    "recovery_score": ("recovery_score",),
    "start": ("sleep_start", "bedtime_start"),
    "end": ("sleep_end", "wake_time", "bedtime_end"),
    "in_bed": ("in_bed", "bed_presence"),
}


def _domain(hass, entry):
    ce = hass.config_entries.async_get_entry(entry.config_entry_id) if entry.config_entry_id else None
    return ce.domain if ce else None


def _label(hass, entry):
    state = hass.states.get(entry.entity_id)
    return " ".join((
        entry.entity_id,
        entry.name or "",
        entry.original_name or "",
        str(getattr(entry, "translation_key", None) or ""),
        str(state.attributes.get("friendly_name") or "") if state else "",
    )).lower().replace("-", "_").replace(" ", "_")


def _alias_matches(label: str, alias: str) -> bool:
    """Match a normalized alias as a complete underscore-delimited phrase.

    This deliberately prevents aliases such as ``wake_time`` from matching
    ``awake_time``. The old substring matching could interpret a duration as a
    timestamp and produce dates near the Unix epoch.
    """
    normalized_label = f"_{label.strip('_')}_"
    normalized_alias = f"_{str(alias).strip('_')}_"
    return normalized_alias in normalized_label


def _num(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _duration(value, unit):
    number = _num(value)
    normalized = str(unit or "").lower()
    if number is None:
        return None
    if normalized in ("min", "minute", "minutes"):
        return number * 60
    if normalized in ("h", "hr", "hour", "hours"):
        return number * 3600
    if normalized in ("ms", "millisecond", "milliseconds"):
        return number / 1000
    return number


def _timestamp(value):
    if value in (None, "", "unknown", "unavailable"):
        return None
    text = str(value).strip()
    try:
        number = float(text)
        if number > 10_000_000_000:
            number /= 1000
        # Modern sleep timestamps must be real calendar timestamps. Values
        # below 2000-01-01 are almost certainly durations/time-of-day values
        # from provider entities and must never become 1970 dates.
        if 946_684_800 <= number <= 4_102_444_800:
            return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()
        return None
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.isoformat()
    except ValueError:
        return None


def _value(hass, entry, field):
    state = hass.states.get(entry.entity_id)
    if not state or state.state in ("unknown", "unavailable", ""):
        return None
    if field in DURATION_FIELDS:
        value = _duration(state.state, state.attributes.get("unit_of_measurement"))
        # Fitbit minute fields occasionally omit their unit metadata.
        if value is not None and "minute" in _label(hass, entry) and not state.attributes.get("unit_of_measurement"):
            value *= 60
        return value
    if field == "in_bed":
        normalized = state.state.lower()
        if normalized in ("on", "true", "yes", "1", "occupied", "sleeping", "in_bed"):
            return True
        if normalized in ("off", "false", "no", "0", "clear", "awake", "not_in_bed"):
            return False
        return None
    if field in ("start", "end"):
        return _timestamp(state.state)
    return _num(state.state)


def selected_entries(hass, config):
    ids = set(config.get(CONF_SLEEP_DEVICE_IDS) or [])
    registry = er.async_get(hass)
    return [
        entry for entry in registry.entities.values()
        if entry.device_id in ids
        and entry.entity_id.startswith(("sensor.", "binary_sensor.", "event."))
    ]


def _spec_for_domain(domain: str | None) -> SleepAdapterSpec | None:
    for spec in SPECS:
        if domain in spec.domains:
            return spec
    return None


def _sleep_tracking_event(hass, entry) -> bool:
    if _domain(hass, entry) != "sleep_as_android" or not entry.entity_id.startswith("event."):
        return False
    label = _label(hass, entry)
    return "sleep_tracking" in label


def _matching_fields(hass, entry, fields_map):
    label = _label(hass, entry)
    return [field for field, aliases in fields_map.items() if any(_alias_matches(label, alias) for alias in aliases)]


def sleep_device_entity_ids(hass, config):
    """Only return entities that the sleep parser can consume."""
    result = set()
    by_device: dict[str, list] = {}
    for entry in selected_entries(hass, config):
        if entry.device_id:
            by_device.setdefault(entry.device_id, []).append(entry)

    for _device_id, entries in by_device.items():
        domains = {_domain(hass, entry) for entry in entries}
        explicit = any(domain in EXPLICIT_DOMAINS for domain in domains)
        generic_hits = set()
        for entry in entries:
            spec = _spec_for_domain(_domain(hass, entry))
            fields_map = spec.fields if spec else GENERIC_FIELDS
            matched = _matching_fields(hass, entry, fields_map)
            if matched:
                result.add(entry.entity_id)
                generic_hits.update(matched)
            if _sleep_tracking_event(hass, entry):
                result.add(entry.entity_id)
                generic_hits.add("tracking_event")
        # Unknown providers require a real sleep contract rather than a single
        # coincidental HR/SpO2-like entity.
        if not explicit and len(generic_hits) < 2:
            for entry in entries:
                result.discard(entry.entity_id)
    return sorted(result)


def _parse_provider(hass, entries, domain, fields_map) -> SleepRecord | None:
    values = {}
    sources = {}
    raw = {}
    for entry in entries:
        state = hass.states.get(entry.entity_id)
        if state is not None:
            raw[entry.entity_id] = {
                "state": state.state,
                "attributes": dict(state.attributes),
            }
    for field, aliases in fields_map.items():
        candidates = []
        for entry in entries:
            label = _label(hass, entry)
            if any(_alias_matches(label, alias) for alias in aliases):
                value = _value(hass, entry, field)
                if value is not None:
                    candidates.append((entry.entity_id, value))
        if candidates:
            entity_id, value = sorted(candidates)[0]
            values[field] = value
            sources[field] = entity_id

    # Overview-style entities may put timing in attributes.
    for entry in entries:
        state = hass.states.get(entry.entity_id)
        if state is None:
            continue
        label = _label(hass, entry)
        if "sleep_overview" in label or "last_sleep" in label:
            for field, names in (("start", ("start", "start_time")), ("end", ("end", "end_time"))):
                if field in values:
                    continue
                for name in names:
                    parsed = _timestamp(state.attributes.get(name))
                    if parsed:
                        values[field] = parsed
                        sources[field] = entry.entity_id
                        break

    observed = [
        getattr(hass.states.get(entry.entity_id), "last_updated", None)
        for entry in entries
        if hass.states.get(entry.entity_id) is not None
    ]
    observed = [item for item in observed if item is not None]
    if observed:
        values["observed_at"] = max(observed).isoformat()

    meaningful = {
        key for key, value in values.items()
        if value is not None and key not in {"in_bed", "observed_at"}
    }
    if not meaningful and values.get("in_bed") is None:
        return None

    # Reject internally impossible awake values. Some broad Garmin entities
    # named "Awake duration" describe the day rather than the last sleep.
    asleep_duration = values.get("duration_s")
    awake_duration = values.get("awake_s")
    if (
        asleep_duration is not None
        and awake_duration is not None
        and awake_duration > asleep_duration
    ):
        values.pop("awake_s", None)
        sources.pop("awake_s", None)

    source = next(iter(sources.values()), entries[0].entity_id)
    return SleepRecord(
        source=source,
        provider_domain=domain or "generic",
        sources=sorted(set(sources.values()) or {source}),
        provider_domains=[domain or "generic"],
        field_sources=dict(sources),
        provider_values={domain or "generic": raw},
        **values,
    )


def discover_sleep_records(hass, config) -> list[SleepRecord]:
    """Parse all selected sleep devices; merging happens after parsing."""
    entries = selected_entries(hass, config)
    by_device: dict[str, list] = {}
    for entry in entries:
        if entry.device_id:
            by_device.setdefault(entry.device_id, []).append(entry)

    records = []
    for _device_id, device_entries in by_device.items():
        domains = {_domain(hass, entry) for entry in device_entries}
        explicit_specs = [spec for spec in SPECS if set(spec.domains).intersection(domains)]
        if explicit_specs:
            for spec in explicit_specs:
                own = [entry for entry in device_entries if _domain(hass, entry) in spec.domains]
                record = _parse_provider(hass, own, next(iter(set(spec.domains).intersection(domains)), spec.name), spec.fields)
                if record is not None:
                    records.append(record)
        else:
            record = _parse_provider(hass, device_entries, next(iter(domains), "generic"), GENERIC_FIELDS)
            if record is not None and len(record.field_sources) >= 2:
                records.append(record)
    return records


def latest_sleep(hass, config):
    return newest_sleep(discover_sleep_records(hass, config))


def supported_adapter_domains() -> dict[str, tuple[str, ...]]:
    return {spec.name: spec.domains for spec in SPECS}
