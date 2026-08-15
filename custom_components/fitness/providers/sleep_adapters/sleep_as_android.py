"""Sleep as Android adapter.

Native Home Assistant Sleep as Android exposes tracking and sleep-phase event
entities. Fitness reconstructs only completed sessions from Recorder history.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..sleep import SleepRecord
from .registry_types import SleepAdapterSpec

SPEC = SleepAdapterSpec("sleep_as_android", ("sleep_as_android",), {
    "duration_s": ("sleep_duration",),
    "deep_sleep_s": ("deep_sleep_duration", "deep_sleep_percent"),
    "score": ("sleep_score", "sleep_quality"),
    "average_hr": ("sleep_heart_rate",),
})

TRACKING = frozenset({"started", "stopped", "paused", "resumed"})
PHASES = frozenset({"awake", "deep_sleep", "light_sleep", "not_awake", "rem"})
STAGE_FIELD = {
    "awake": "awake_s",
    "deep_sleep": "deep_sleep_s",
    "light_sleep": "light_sleep_s",
    "rem": "rem_sleep_s",
}


def _dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _attr(item: Any, key: str) -> Any:
    attrs = item.get("attributes") if isinstance(item, dict) else getattr(item, "attributes", None)
    return attrs.get(key) if isinstance(attrs, dict) else None


def _stamp(item: Any) -> datetime | None:
    for key in ("last_updated", "last_changed", "last_reported"):
        value = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
        if (parsed := _dt(value)) is not None:
            return parsed
    return None


def _events(states: list[Any], accepted: frozenset[str]) -> list[tuple[datetime, str]]:
    out = []
    for state in states:
        event_type = str(_attr(state, "event_type") or "").lower()
        stamp = _stamp(state)
        if stamp is not None and event_type in accepted:
            out.append((stamp, event_type))
    return sorted(out)


def _completed_sessions(events):
    """Return all completed STARTED...STOPPED sessions; never an active one."""
    started = active = None
    windows = []
    completed = []
    for stamp, event_type in events:
        if event_type == "started":
            started = active = stamp
            windows = []
        elif started is None:
            continue
        elif event_type == "paused":
            if active is not None and stamp > active:
                windows.append((active, stamp))
            active = None
        elif event_type == "resumed":
            if active is None:
                active = stamp
        elif event_type == "stopped":
            if active is not None and stamp > active:
                windows.append((active, stamp))
            if stamp > started and stamp - started <= timedelta(hours=24):
                completed.append((started, stamp, list(windows)))
            started = active = None
            windows = []
    return completed


def _latest_completed_session(events):
    completed = _completed_sessions(events)
    return completed[-1] if completed else None


def _overlap_seconds(start, end, windows):
    return sum(
        max(0.0, (min(end, b) - max(start, a)).total_seconds())
        for a, b in windows if min(end, b) > max(start, a)
    )


def records_from_event_history(
    *, tracking_entity_id: str, phase_entity_id: str | None,
    tracking_states: list[Any], phase_states: list[Any],
) -> list[SleepRecord]:
    """Reconstruct every completed sleep session present in Recorder history."""
    sessions = _completed_sessions(_events(tracking_states, TRACKING))
    records: list[SleepRecord] = []
    phase_events = _events(phase_states, PHASES)
    for start, end, windows in sessions:
        if not windows:
            windows = [(start, end)]
        active_s = sum((b - a).total_seconds() for a, b in windows)
        if not 60 <= active_s <= 24 * 3600:
            continue

        phases = [event for event in phase_events if start <= event[0] <= end]
        totals = {key: 0.0 for key in ("awake_s", "light_sleep_s", "deep_sleep_s", "rem_sleep_s")}
        for i, (stamp, event_type) in enumerate(phases):
            next_stamp = phases[i + 1][0] if i + 1 < len(phases) else end
            field = STAGE_FIELD.get(event_type)
            if field and next_stamp > stamp:
                totals[field] += _overlap_seconds(stamp, next_stamp, windows)

        sleep_s = max(0.0, active_s - totals["awake_s"])
        field_sources = {"start": tracking_entity_id, "end": tracking_entity_id, "duration_s": tracking_entity_id}
        if phase_entity_id:
            field_sources.update({k: phase_entity_id for k, v in totals.items() if v > 0})
        records.append(SleepRecord(
            source=tracking_entity_id, provider_domain="sleep_as_android",
            start=start.isoformat(), end=end.isoformat(), observed_at=end.isoformat(),
            duration_s=sleep_s, awake_s=totals["awake_s"] or None,
            light_sleep_s=totals["light_sleep_s"] or None, deep_sleep_s=totals["deep_sleep_s"] or None,
            rem_sleep_s=totals["rem_sleep_s"] or None,
            sources=[tracking_entity_id] + ([phase_entity_id] if phase_entity_id else []),
            provider_domains=["sleep_as_android"], field_sources=field_sources,
            provider_values={"sleep_as_android": {
                "tracking_entity": tracking_entity_id, "phase_entity": phase_entity_id,
                "stage_method": "home_assistant_recorder_event_timeline",
                "reconstructed_fields": [
                    "duration_s",
                    *[key for key, value in totals.items() if value > 0],
                ],
                "unclassified_asleep_s": max(0.0, sleep_s - totals["light_sleep_s"] - totals["deep_sleep_s"] - totals["rem_sleep_s"]),
            }},
        ))
    return records


def record_from_event_history(
    *, tracking_entity_id: str, phase_entity_id: str | None,
    tracking_states: list[Any], phase_states: list[Any],
) -> SleepRecord | None:
    """Backward-compatible helper returning only the newest completed session."""
    records = records_from_event_history(
        tracking_entity_id=tracking_entity_id, phase_entity_id=phase_entity_id,
        tracking_states=tracking_states, phase_states=phase_states,
    )
    return records[-1] if records else None
