"""Canonical workout calendar for Fitness."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .calendar_strings import tr
from .const import CONF_PROFILE_NAME, DOMAIN
from .entity import device_info
from .providers.workouts import Workout, _dt, _sport_key


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FitnessWorkoutCalendar(manager, entry)])


def _fmt_duration(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = max(0, int(round(float(seconds))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _event_times(workout: Workout) -> tuple[datetime, datetime] | None:
    start = _dt(workout.start)
    if start is None:
        return None
    end = _dt(workout.end)
    if end is None and workout.duration_s:
        end = start + timedelta(seconds=float(workout.duration_s))
    if end is None or end <= start:
        end = start + timedelta(minutes=1)
    return start, end


def _event_uid(entry_id: str, workout: Workout) -> str | None:
    """Create a stable-enough UID for one canonical physical workout.

    The same five-minute start bucket used by Fitness announcement identity is
    intentionally source-independent, so Garmin/Strava enrichment does not
    create a new calendar event UID.
    """
    start = _dt(workout.start)
    if start is None:
        return None
    return f"fitness-{entry_id}-t5-{int(start.timestamp()) // 300}"


def _location(workout: Workout) -> str | None:
    """Return the workout start point when explicit start GPS exists."""
    lat = workout.start_latitude
    lon = workout.start_longitude
    if lat is None or lon is None:
        return None
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return f"{lat:.6f}, {lon:.6f}"


def _sport_name(workout: Workout, language: str) -> str:
    sport = _sport_key(workout.sport)
    if sport:
        translated = tr(language, sport)
        if translated != sport:
            return translated
        return sport.replace("_", " ").title()
    return tr(language, "workout")


def _summary(workout: Workout, language: str) -> str:
    if workout.name and str(workout.name).strip():
        return str(workout.name).strip()
    return _sport_name(workout, language)


def _description(workout: Workout, language: str) -> str:
    """Return a concise localized calendar description.

    CalendarEvent does not support arbitrary rendered per-event attributes.
    Full structured measurements remain in the canonical Fitness workout model
    and Fitness dashboard; the calendar carries only a useful compact summary.
    """
    values: list[str] = [_sport_name(workout, language)]

    duration = _fmt_duration(workout.duration_s)
    if duration:
        values.append(f"{tr(language, 'duration')}: {duration}")
    if workout.distance_m is not None:
        values.append(f"{tr(language, 'distance')}: {float(workout.distance_m) / 1000:.2f} km")
    if workout.avg_hr is not None:
        values.append(f"{tr(language, 'avg_hr')}: {round(float(workout.avg_hr))} bpm")
    if workout.avg_power is not None:
        values.append(f"{tr(language, 'avg_power')}: {round(float(workout.avg_power))} W")
    if workout.calories is not None:
        values.append(f"{tr(language, 'calories')}: {round(float(workout.calories))} kcal")

    values.extend(["", tr(language, "details")])
    return "\n".join(values)


class FitnessWorkoutCalendar(CalendarEntity):
    """Canonical merged Fitness workout history."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:calendar-heart"
    _attr_supported_features = CalendarEntityFeature.DELETE_EVENT

    def __init__(self, manager, entry):
        self.manager = manager
        self.entry = entry
        profile = str(
            entry.options.get(
                CONF_PROFILE_NAME,
                entry.data.get(CONF_PROFILE_NAME, entry.title),
            )
            or entry.title
        )
        self.language = str(manager.config.get("language") or "en")
        self._attr_name = f"{profile} {tr(self.language, 'workouts')}"
        self._attr_unique_id = f"{entry.entry_id}_workouts"
        self._attr_device_info = device_info(entry, "workout")

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.manager.add_workout_history_listener(self._handle_manager_update)
        )

    def _handle_manager_update(self):
        self.async_write_ha_state()
        self.async_update_event_listeners()

    def _events(self) -> list[CalendarEvent]:
        events = []
        for workout in self.manager.local_workouts():
            times = _event_times(workout)
            uid = _event_uid(self.entry.entry_id, workout)
            if times is None or uid is None:
                continue
            start, end = times
            events.append(
                CalendarEvent(
                    start=start,
                    end=end,
                    summary=_summary(workout, self.language),
                    description=_description(workout, self.language),
                    location=_location(workout),
                    uid=uid,
                )
            )
        return sorted(events, key=lambda event: event.start)

    @property
    def event(self):
        now = dt_util.now()
        for event in self._events():
            if event.end >= now:
                return event
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        return [
            event
            for event in self._events()
            if event.end > start_date and event.start < end_date
        ]

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete one canonical workout and prevent provider re-import."""
        del recurrence_id, recurrence_range
        deleted = await self.manager.async_delete_calendar_workout(uid, self.entry.entry_id)
        if deleted:
            self.async_write_ha_state()
            await self.async_update_event_listeners()
