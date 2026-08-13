"""Read-only workout calendar for Fitness."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

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


def _line(label: str, value: Any, suffix: str = "") -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, float):
        value = round(value, 2)
    return f"{label}: {value}{suffix}"


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


def _summary(workout: Workout) -> str:
    if workout.name and str(workout.name).strip():
        return str(workout.name).strip()
    sport = _sport_key(workout.sport)
    return sport.replace("_", " ").title() if sport else "Workout"


def _description(workout: Workout) -> str:
    lines: list[str] = []
    sport = (workout.sport or "Workout").replace("_", " ").title()
    lines.append(sport)
    lines.append("")

    basic = [
        _line("Duration", _fmt_duration(workout.duration_s)),
        _line("Moving time", _fmt_duration(workout.moving_time_s)),
        _line("Distance", round(workout.distance_m / 1000, 3) if workout.distance_m is not None else None, " km"),
        _line("Average speed", round(workout.average_speed_m_s * 3.6, 2) if workout.average_speed_m_s is not None else None, " km/h"),
        _line("Maximum speed", round(workout.max_speed_m_s * 3.6, 2) if workout.max_speed_m_s is not None else None, " km/h"),
        _line("Calories", workout.calories, " kcal"),
        _line("Elevation gain", workout.elevation_gain_m, " m"),
        _line("Elevation loss", workout.elevation_loss_m, " m"),
    ]
    lines.extend(x for x in basic if x)

    sections = [
        ("Heart rate", [
            _line("Average", workout.avg_hr, " bpm"),
            _line("Maximum", workout.max_hr, " bpm"),
        ]),
        ("Power", [
            _line("Average", workout.avg_power, " W"),
            _line("Maximum", workout.max_power, " W"),
            _line("Weighted", workout.weighted_power, " W"),
        ]),
        ("Cadence", [
            _line("Average", workout.avg_cadence),
            _line("Maximum", workout.max_cadence),
        ]),
        ("Strength", [
            _line("Exercises", workout.exercise_count),
            _line("Sets", workout.strength_total_sets),
            _line("Repetitions", workout.total_reps),
            _line("Volume", workout.volume_kg, " kg"),
            _line("Best estimated 1RM", workout.strength_best_estimated_1rm_kg, " kg"),
        ]),
        ("Fitness calculations", [
            _line("TRIMP", workout.banister_trimp),
            _line("TRIMP/hour", workout.trimp_per_hour),
            _line("Mechanical work", workout.mechanical_work_kj, " kJ"),
            _line("Aerobic efficiency", workout.aerobic_efficiency),
            _line("Aerobic decoupling", workout.aerobic_decoupling_percent, "%"),
            _line("Session RPE", workout.session_rpe, "/10"),
            _line("Session RPE load", workout.session_rpe_load),
            _line("Fitness aerobic load", workout.fitness_aerobic_load),
            _line("Fitness high-intensity load", workout.fitness_high_intensity_load),
        ]),
        ("Personal baseline", [
            _line("Comparable workouts", workout.comparable_workout_count),
            _line("Efficiency vs baseline", workout.efficiency_vs_baseline_percent, "%"),
            _line("Decoupling vs baseline", workout.decoupling_vs_baseline_percent, "%"),
            _line("Average HR vs baseline", workout.avg_hr_vs_baseline_bpm, " bpm"),
            _line("Average power vs baseline", workout.avg_power_vs_baseline_percent, "%"),
            _line("Average speed vs baseline", workout.avg_speed_vs_baseline_percent, "%"),
            _line("TRIMP vs recent mean", workout.trimp_vs_recent_mean_percent, "%"),
            _line("Load context", workout.load_context),
        ]),
    ]
    for title, values in sections:
        values = [x for x in values if x]
        if values:
            lines.extend(["", title, *values])

    sources = list(dict.fromkeys(workout.sources or ([workout.source] if workout.source else [])))
    if sources:
        lines.extend(["", "Sources", *sources])
    return "\n".join(lines).strip()


class FitnessWorkoutCalendar(CalendarEntity):
    """Canonical merged Fitness workout history."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:calendar-heart"

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
        self._attr_name = f"{profile} Workouts"
        self._attr_unique_id = f"{entry.entry_id}_workouts"
        self._attr_device_info = device_info(entry, "evaluation")

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.add_listener(self._handle_manager_update))

    def _handle_manager_update(self):
        # CalendarEntity.async_write_ha_state() also schedules subscribed
        # calendar/event listeners, so one manager notification updates both
        # the entity state and an already-open Calendar view.
        self.async_write_ha_state()

    def _events(self) -> list[CalendarEvent]:
        events = []
        for workout in self.manager.local_workouts():
            times = _event_times(workout)
            if times is None:
                continue
            start, end = times
            events.append(CalendarEvent(
                start=start, end=end, summary=_summary(workout),
                description=_description(workout),
                uid=f"fitness-{self.entry.entry_id}-{int(start.timestamp())}",
            ))
        return sorted(events, key=lambda event: event.start)

    @property
    def event(self):
        now = dt_util.now()
        for event in self._events():
            if event.end >= now:
                return event
        return None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime):
        return [
            event for event in self._events()
            if event.end > start_date and event.start < end_date
        ]
