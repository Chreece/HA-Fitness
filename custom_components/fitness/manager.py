"""Central Fitness profile/session/workout/evaluation manager."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from statistics import mean
from typing import Callable, Any

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .const import (
    ANTPLUS_DOMAINS,
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_FEEDBACK_AREA_IDS,
    CONF_FEEDBACK_LIGHT_IDS,
    CONF_LANGUAGE,
    CONF_NOTIFY_ENTITY_IDS,
    CONF_TTS_ENTITY_ID,
    CONF_TTS_MEDIA_PLAYER_IDS,
    CONF_DATE_OF_BIRTH,
    CONF_MAX_HR,
    CONF_PERIODIC_LIVE_ANNOUNCEMENTS,
    CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
    CONF_PROFILE_NAME,
    CONF_RESTING_HR,
    CONF_SEX,
    CONF_VO2MAX,
    CONF_WEIGHT,
    DOMAIN,
    MAX_STORED_WORKOUTS,
    METRIC_ALTITUDE,
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
    METHOD_FRIEND_2017,
    METHOD_PERSONAL_HRV_BASELINE,
    METHOD_TANAKA_2001,
    METHOD_UTH_2004,
    MIN_LOCAL_WORKOUT_SAMPLES,
    MIN_LOCAL_WORKOUT_SECONDS,
    STORE_KEY_PREFIX,
    STORE_VERSION,
    SUPPORTED_LANGUAGES,
)
from .engine.fitness import (
    friend_predicted_vo2max,
    hrv_personal_status,
    percent_predicted,
    reference_status,
    threshold_pace_from_speed,
    uth_vo2max,
)
from .engine.heart_rate import predicted_max_hr_tanaka, heart_rate_reserve
from .engine.training import (
    aerobic_efficiency_and_decoupling,
    banister_trimp,
    mechanical_work_kj,
    time_in_hrr_intensity,
)
from .engine.live import (
    acsm_hrr_intensity,
    pace_from_speed_kmh,
    percent_hrr,
    percent_max_hr,
    relative_percent,
    speed_from_pace_min_km,
)
from .feedback import (
    intensity_rgb,
    static_intensity_message,
    static_periodic_live_message,
    static_session_message,
    static_workout_message,
)
from .providers.devices import (
    all_live_candidate_entity_ids,
    discover_sources,
    source_device_ids,
)
from .providers.entities import (
    is_entity_reference,
    numeric_entity_state,
    resolve_number_or_entity,
)
from .providers.evaluation import collect_provider_metrics, workout_device_entity_ids
from .providers.workouts import (
    Workout,
    _dt,
    _sport_key,
    discover_external_workouts,
    newest,
)


class FitnessManager:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.listeners: list[Callable[[], None]] = []
        self.remove_listeners: list[Callable[[], None]] = []
        self.store = Store(
            hass,
            STORE_VERSION,
            f"{STORE_KEY_PREFIX}.{entry.entry_id}",
        )
        self.history: list[dict] = []
        self.session_armed = False
        self.session_active = False
        self.session_started: datetime | None = None
        self.samples: list[dict[str, Any]] = []
        self.capture_control = "idle"

        # Pre-workout states of ANT+ Capture switches. Persisted so a Home
        # Assistant restart cannot make Fitness forget which switches it
        # temporarily enabled for a workout.
        self._capture_switch_snapshot: dict[str, str] = {}
        self._capture_switches_changed_by_fitness: set[str] = set()

        # Recovery begins after Stop Workout. The workout timer is already
        # stopped and Live entities become unavailable, but capture can remain
        # on briefly to measure post-exercise HR recovery.
        self.recovery_active = False
        self._recovery_task: asyncio.Task | None = None
        self._recovery_reference_hr: float | None = None
        self._recovery_workout_start: str | None = None

        # Cached Home Assistant Recorder long-term statistics.
        self.long_term_statistics: dict[str, Any] = {}
        self.long_term_statistics_updated: str | None = None

        # Keys of sensor descriptions that have produced a valid value at least
        # once. These are persisted so created HA entities are never removed
        # merely because a later workout lacks the necessary inputs.
        self.materialized_sensor_keys: set[str] = set()
        self.ai_general: str | None = None
        self.ai_workout: str | None = None
        self.ai_general_verdict: str | None = None
        self.ai_workout_verdict: str | None = None
        self.ai_last_generated: str | None = None
        self._last_external_signature: str | None = None
        self._last_announced_workout_signature: str | None = None
        self._external_workout_baseline_pending = False

        # Provider integrations restore/update workout entities in stages.
        # Startup restoration is baseline-only; later provider changes are
        # debounced before Fitness can evaluate or announce them.
        self._external_workout_announcements_armed = False
        self._external_workout_debounce_task: asyncio.Task | None = None
        self._external_workout_candidate_signature: str | None = None

        self._last_live_intensity: str | None = None
        self._last_live_intensity_accepted_at: datetime | None = None
        self._feedback_generation = 0
        # Original light states for the current feedback pulse cycle.
        # Kept in memory so feedback does not depend on scene.create.
        self._feedback_light_snapshot: dict[str, dict] = {}
        self._feedback_scene_active = False
        self._feedback_lock = asyncio.Lock()
        self._live_feedback_task: asyncio.Task | None = None
        self._periodic_live_announcement_task: asyncio.Task | None = None

        # Live coaching diagnostics, exposed on the Heart rate intensity sensor.
        self.last_feedback_intensity: str | None = None
        self.last_feedback_time: str | None = None
        self.last_feedback_light_result: str | None = None
        self.last_feedback_tts_result: str | None = None
        self.last_feedback_message: str | None = None
        self.last_feedback_bpm: int | None = None
        self.last_feedback_pulse_interval: float | None = None
        self.last_feedback_pulse_count: int | None = None
        self.last_periodic_live_announcement_time: str | None = None
        self.last_periodic_live_message: str | None = None

        # Runtime-selected workout room. Stored by area ID so renaming an area
        # does not break the selection.
        self.selected_feedback_area_id: str | None = None

        self._ai_lock = asyncio.Lock()
        # Serializes start/recovery spoken guidance so asynchronously generated
        # AI messages cannot overtake one another.
        self._session_announcement_lock = asyncio.Lock()

        # Workout lifecycle light cues are serialized separately from the
        # heartbeat/intensity pulses. They reuse the same original-state
        # snapshot only while intensity feedback is suspended.
        self._session_status_light_lock = asyncio.Lock()
        self._session_status_light_active = False
        self._session_status_light_task: asyncio.Task | None = None
        self._session_waiting_red = False

    @property
    def config(self):
        return {**self.entry.data, **self.entry.options}

    async def async_setup(self):
        stored = await self.store.async_load() or {}
        self.history = list(stored.get("history") or [])
        self.ai_general = stored.get("ai_general")
        self.ai_workout = stored.get("ai_workout")
        self.ai_general_verdict = stored.get("ai_general_verdict")
        self.ai_workout_verdict = stored.get("ai_workout_verdict")
        self.ai_last_generated = stored.get("ai_last_generated")
        self.long_term_statistics = dict(
            stored.get("long_term_statistics") or {}
        )
        self.long_term_statistics_updated = stored.get(
            "long_term_statistics_updated"
        )
        self.materialized_sensor_keys = set(
            stored.get("materialized_sensor_keys") or []
        )
        self._capture_switch_snapshot = dict(
            stored.get("capture_switch_snapshot") or {}
        )
        self._capture_switches_changed_by_fitness = set(
            stored.get("capture_switches_changed_by_fitness") or []
        )
        self._last_announced_workout_signature = stored.get(
            "last_announced_workout_signature"
        )
        self.selected_feedback_area_id = stored.get(
            "selected_feedback_area_id"
        )

        valid_area_ids = {
            area_id
            for area_id, _name in self.available_feedback_areas()
        }

        # Persisted runtime room wins, but only if it still exists.
        if (
            self.selected_feedback_area_id
            and self.selected_feedback_area_id not in valid_area_ids
        ):
            self.selected_feedback_area_id = None

        # If no persisted runtime room exists, use the first configured feedback
        # area as the initial Workout room. If setup did not specify an area,
        # deliberately remain unselected. Never guess an arbitrary HA area.
        if not self.selected_feedback_area_id:
            configured_areas = [
                area_id
                for area_id in list(
                    self.config.get(CONF_FEEDBACK_AREA_IDS) or []
                )
                if area_id in valid_area_ids
            ]
            if configured_areas:
                self.selected_feedback_area_id = configured_areas[0]
            else:
                self.selected_feedback_area_id = None

        ids = set(all_live_candidate_entity_ids(self.hass, self.config))
        ids.update(workout_device_entity_ids(self.hass, self.config))

        for key in (
            CONF_WEIGHT,
            CONF_RESTING_HR,
            CONF_MAX_HR,
            CONF_VO2MAX,
        ):
            raw = self.config.get(key)
            if is_entity_reference(raw):
                ids.add(str(raw).strip())

        if ids:
            self.remove_listeners.append(
                async_track_state_change_event(
                    self.hass,
                    sorted(ids),
                    self._async_source_change,
                )
            )

        # Completed-workout providers restore asynchronously after Home
        # Assistant startup. During that restoration window the same workout may
        # temporarily appear with only a subset of its attributes. Never treat
        # startup restoration as a newly completed workout.
        self._external_workout_announcements_armed = False
        self._external_workout_baseline_pending = True
        self._last_external_signature = (
            self._last_announced_workout_signature
            if self._last_announced_workout_signature
            else None
        )
        self.hass.async_create_task(
            self._async_arm_external_workout_announcements()
        )

        # Recover a pre-workout capture snapshot if HA restarted while Fitness
        # had temporarily enabled ANT+ Capture switches.
        if self._capture_switch_snapshot:
            self.hass.async_create_task(
                self._async_restore_stale_capture_snapshot()
            )

        # Refresh HA Recorder long-term statistics after integrations have had
        # a moment to restore their entities. Failure is non-fatal.
        self.hass.async_create_task(
            self._async_delayed_long_term_refresh()
        )

        # Generate an initial general assessment only if AI is configured and
        # there is not already a persisted one.
        if self.config.get(CONF_AI_ENABLED) and not self.ai_general:
            self.hass.async_create_task(
                self.async_generate_ai(general=True, workout=False)
            )

    async def async_shutdown(self):
        for remove in self.remove_listeners:
            remove()
        self.remove_listeners.clear()

        if self._live_feedback_task and not self._live_feedback_task.done():
            self._live_feedback_task.cancel()

        if (
            self._periodic_live_announcement_task
            and not self._periodic_live_announcement_task.done()
        ):
            self._periodic_live_announcement_task.cancel()

        if self._recovery_task and not self._recovery_task.done():
            self._recovery_task.cancel()

        if (
            self._external_workout_debounce_task
            and not self._external_workout_debounce_task.done()
        ):
            self._external_workout_debounce_task.cancel()

        if (
            self._session_status_light_task
            and not self._session_status_light_task.done()
        ):
            self._session_status_light_task.cancel()

        if self._feedback_scene_active:
            await self._async_restore_feedback_lights()

    def add_listener(self, listener):
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)

    def sensor_was_materialized(self, key: str) -> bool:
        """Return whether a sensor entity has ever had a valid value."""
        return key in self.materialized_sensor_keys

    def remember_materialized_sensor(
        self,
        key: str,
        *,
        persist: bool = True,
    ) -> bool:
        """Persist a sensor key after its first valid calculation."""
        if key in self.materialized_sensor_keys:
            return False

        self.materialized_sensor_keys.add(key)

        if persist:
            self.hass.async_create_task(self._save())

        return True

    def remember_materialized_sensors(
        self,
        keys: set[str],
        *,
        persist: bool = True,
    ) -> bool:
        """Restore keys corresponding to entities already in HA's registry."""
        added = set(keys) - self.materialized_sensor_keys
        if not added:
            return False

        self.materialized_sensor_keys.update(added)

        if persist:
            self.hass.async_create_task(self._save())

        return True

    def _notify(self):
        for listener in list(self.listeners):
            listener()

    async def _save(self):
        await self.store.async_save(
            {
                "history": self.history[-MAX_STORED_WORKOUTS:],
                "ai_general": self.ai_general,
                "ai_workout": self.ai_workout,
                "ai_general_verdict": self.ai_general_verdict,
                "ai_workout_verdict": self.ai_workout_verdict,
                "ai_last_generated": self.ai_last_generated,
                "long_term_statistics": self.long_term_statistics,
                "long_term_statistics_updated": self.long_term_statistics_updated,
                "materialized_sensor_keys": sorted(
                    self.materialized_sensor_keys
                ),
                "capture_switch_snapshot": dict(
                    self._capture_switch_snapshot
                ),
                "capture_switches_changed_by_fitness": sorted(
                    self._capture_switches_changed_by_fitness
                ),
                "last_announced_workout_signature": (
                    self._last_announced_workout_signature
                ),
                "selected_feedback_area_id": (
                    self.selected_feedback_area_id
                ),
            }
        )

    @callback
    def _async_source_change(self, event: Event):
        """React to live samples and genuinely new completed workouts."""

        # Start button only arms capture. The workout clock begins on the first
        # subsequent valid live measurement/event.
        if self.session_armed and not self.session_active:
            if self._has_valid_live_workout_data():
                self._begin_session_from_live_data()

        if self.session_active:
            self._capture_sample()
            self._check_live_intensity_feedback()

        if self.session_active and self.config.get(CONF_PERIODIC_LIVE_ANNOUNCEMENTS):
            if (
                self._periodic_live_announcement_task is None
                or self._periodic_live_announcement_task.done()
            ):
                self._periodic_live_announcement_task = (
                    self.hass.async_create_task(
                        self._async_periodic_live_announcements()
                    )
                )

        self._notify()

        # Provider workout entities often change several times while one
        # completed workout is being restored/synchronized. Re-evaluate only
        # after the provider data has settled.
        self._schedule_external_workout_recheck()

    @staticmethod
    def _workout_has_real_information(
        workout: Workout | None,
    ) -> bool:
        """Reject unavailable/placeholder workout representations.

        A provider timestamp plus a name/sport is not enough to trigger AI,
        speech or notifications. Require at least one substantive completed-
        workout measurement.
        """
        if workout is None or not workout.start:
            return False

        fields = (
            "duration_s",
            "moving_time_s",
            "elapsed_time_s",
            "distance_m",
            "avg_hr",
            "max_hr",
            "avg_power",
            "max_power",
            "weighted_power",
            "avg_cadence",
            "max_cadence",
            "calories",
            "training_load",
            "relative_effort",
            "kilojoules",
            "total_reps",
            "exercise_count",
            "volume_kg",
            "sample_count",
            "banister_trimp",
            "mechanical_work_kj",
        )

        for field_name in fields:
            value = getattr(workout, field_name, None)
            try:
                if value is not None and float(value) > 0:
                    return True
            except (TypeError, ValueError):
                continue

        for field_name in ("elevation_gain_m", "elevation_loss_m"):
            value = getattr(workout, field_name, None)
            try:
                if value is not None and abs(float(value)) > 0:
                    return True
            except (TypeError, ValueError):
                continue

        return False

    async def _async_arm_external_workout_announcements(self) -> None:
        """Settle startup provider state and establish a silent baseline."""
        await asyncio.sleep(30)

        latest = self.latest_workout()
        signature = (
            self._workout_signature(latest)
            if self._workout_has_real_information(latest)
            else None
        )

        if signature is not None:
            self._last_external_signature = signature
            self._last_announced_workout_signature = signature
            await self._save()

        self._external_workout_baseline_pending = False
        self._external_workout_announcements_armed = True

    def _schedule_external_workout_recheck(self) -> None:
        """Debounce provider changes before accepting a completed workout."""
        if not self._external_workout_announcements_armed:
            return
        if self.recovery_active:
            return

        latest = self.latest_workout()
        if not self._workout_has_real_information(latest):
            return

        signature = self._workout_signature(latest)
        if signature is None or signature == self._last_external_signature:
            return

        self._external_workout_candidate_signature = signature

        if (
            self._external_workout_debounce_task
            and not self._external_workout_debounce_task.done()
        ):
            self._external_workout_debounce_task.cancel()

        self._external_workout_debounce_task = self.hass.async_create_task(
            self._async_process_external_workout_after_settle(signature)
        )

    async def _async_process_external_workout_after_settle(
        self,
        candidate_signature: str,
    ) -> None:
        """Accept one stable provider workout after its entities settle."""
        try:
            await asyncio.sleep(8)
        except asyncio.CancelledError:
            return

        if not self._external_workout_announcements_armed:
            return

        latest = self.latest_workout()
        if not self._workout_has_real_information(latest):
            return

        signature = self._workout_signature(latest)
        if (
            signature is None
            or signature != candidate_signature
            or signature != self._external_workout_candidate_signature
        ):
            return

        if signature == self._last_external_signature:
            return

        self._last_external_signature = signature

        if signature == self._last_announced_workout_signature:
            return

        self._last_announced_workout_signature = signature
        await self._save()
        await self._async_handle_new_workout(latest)

    def _current_live_intensity(self) -> str | None:
        live = self.live_values()
        evaluation = self.evaluation()
        hrr = percent_hrr(
            live.get(METRIC_HEART_RATE),
            evaluation.get("max_hr"),
            evaluation.get("resting_hr"),
        )
        return acsm_hrr_intensity(hrr)

    def _check_live_intensity_feedback(self):
        """Accept intensity transitions no more often than every five seconds."""
        if self._session_status_light_active:
            return

        intensity = self._current_live_intensity()
        if intensity is None:
            return

        if intensity == self._last_live_intensity:
            return

        now = datetime.now(timezone.utc)

        # The first valid intensity of a workout is accepted immediately.
        # Afterwards the previous accepted intensity must be at least 5 seconds
        # old. A transition ignored here is naturally reconsidered by the next
        # live sensor update, so a persistent new intensity is not lost.
        if self._last_live_intensity_accepted_at is not None:
            age = (
                now - self._last_live_intensity_accepted_at
            ).total_seconds()
            if age < 5.0:
                return

        self._last_live_intensity = intensity
        self._last_live_intensity_accepted_at = now

        if self._live_feedback_task and not self._live_feedback_task.done():
            self._live_feedback_task.cancel()

        self._live_feedback_task = self.hass.async_create_task(
            self._async_live_intensity_feedback(intensity)
        )

    @staticmethod
    def _session_status_intensity(status: str) -> str | None:
        """Map lifecycle status colors onto the existing RGB palette."""
        return {
            "red": "near_maximal",
            "orange": "vigorous",
            "yellow": "moderate",
            "blue": "very_light",
            "green": "light",
        }.get(status)

    async def _async_prepare_session_status_lights(
        self,
        light_ids: list[str],
        *,
        preserve_existing_snapshot: bool = False,
    ) -> bool:
        """Suspend intensity feedback and establish the lifecycle snapshot."""
        # Invalidate/cancel any active intensity cue before lifecycle lights.
        self._feedback_generation += 1
        if self._live_feedback_task and not self._live_feedback_task.done():
            self._live_feedback_task.cancel()

        async with self._feedback_lock:
            if (
                self._feedback_scene_active
                and not preserve_existing_snapshot
            ):
                await self._async_restore_feedback_lights(
                    clear_snapshot=True,
                )

            if not self._feedback_scene_active:
                return await self._async_snapshot_feedback_lights(
                    light_ids
                )

            return bool(self._feedback_light_snapshot)

    async def _async_session_status_waiting_red(self) -> None:
        """Hold workout lights red until the first valid live data arrives."""
        async with self._session_status_light_lock:
            light_ids = self._feedback_light_ids()
            if not light_ids:
                self._session_status_light_active = False
                self._session_waiting_red = False
                return

            snapshot_ok = await self._async_prepare_session_status_lights(
                light_ids,
            )
            if not snapshot_ok:
                self._session_status_light_active = False
                self._session_waiting_red = False
                return

            async with self._feedback_lock:
                await self._async_set_feedback_color(
                    light_ids,
                    self._session_status_intensity("red"),
                )

            # Keep the original snapshot alive. Green-on-live will restore it.
            self._session_waiting_red = True
            self.last_feedback_light_result = "waiting_for_live_data_red"
            self._notify()

    async def _async_session_status_cue(
        self,
        status: str,
        *,
        seconds: float = 3.0,
        finish_waiting: bool = False,
        resume_intensity: bool = False,
    ) -> None:
        """Show one lifecycle color temporarily, then restore original state."""
        async with self._session_status_light_lock:
            light_ids = self._feedback_light_ids()
            if not light_ids:
                self._session_status_light_active = False
                self._session_waiting_red = False
                if resume_intensity and self.session_active:
                    self._check_live_intensity_feedback()
                return

            preserve = bool(
                finish_waiting
                and self._session_waiting_red
                and self._feedback_scene_active
            )
            snapshot_ok = await self._async_prepare_session_status_lights(
                light_ids,
                preserve_existing_snapshot=preserve,
            )
            if not snapshot_ok:
                self._session_status_light_active = False
                self._session_waiting_red = False
                if resume_intensity and self.session_active:
                    self._check_live_intensity_feedback()
                return

            mapped = self._session_status_intensity(status)
            if mapped is None:
                self._session_status_light_active = False
                return

            try:
                async with self._feedback_lock:
                    await self._async_set_feedback_color(
                        light_ids,
                        mapped,
                    )

                self.last_feedback_light_result = (
                    f"session_status_{status}"
                )
                self._notify()
                await asyncio.sleep(max(0.0, float(seconds)))

            except asyncio.CancelledError:
                # Restore below before exiting.
                pass

            finally:
                async with self._feedback_lock:
                    await self._async_restore_feedback_lights(
                        clear_snapshot=True,
                    )

                self._session_waiting_red = False
                self._session_status_light_active = False
                self._notify()

                if resume_intensity and self.session_active:
                    # Re-evaluate the current zone after lifecycle feedback
                    # releases control of the lights.
                    self._last_live_intensity = None
                    self._last_live_intensity_accepted_at = None
                    self._check_live_intensity_feedback()

    def _queue_session_status_waiting_red(self) -> None:
        """Immediately reserve lifecycle lights, then hold red asynchronously."""
        self._session_status_light_active = True
        self._session_status_light_task = self.hass.async_create_task(
            self._async_session_status_waiting_red()
        )

    def _queue_session_status_cue(
        self,
        status: str,
        *,
        finish_waiting: bool = False,
        resume_intensity: bool = False,
    ) -> None:
        """Queue a three-second lifecycle color cue."""
        self._session_status_light_active = True
        self._session_status_light_task = self.hass.async_create_task(
            self._async_session_status_cue(
                status,
                seconds=3.0,
                finish_waiting=finish_waiting,
                resume_intensity=resume_intensity,
            )
        )

    def available_feedback_areas(self) -> list[tuple[str, str]]:
        """Return current Home Assistant areas as (area_id, name)."""
        registry = ar.async_get(self.hass)
        items = [
            (area.id, area.name)
            for area in registry.async_list_areas()
        ]
        return sorted(
            items,
            key=lambda item: item[1].casefold(),
        )

    def selected_feedback_area_name(self) -> str | None:
        """Return the display name of the currently selected workout room."""
        selected = self.selected_feedback_area_id
        if not selected:
            return None

        registry = ar.async_get(self.hass)
        area = registry.async_get_area(selected)
        return area.name if area is not None else None

    async def async_select_feedback_area(
        self,
        area_id: str | None,
    ):
        """Change or clear Workout room and persist the selection."""
        if area_id is None:
            self.selected_feedback_area_id = None
            await self._save()
            self._notify()
            return

        valid_ids = {
            item[0]
            for item in self.available_feedback_areas()
        }
        if area_id not in valid_ids:
            return

        self.selected_feedback_area_id = area_id
        await self._save()
        self._notify()

    def _entity_area_id(
        self,
        entity_id: str,
    ) -> str | None:
        """Resolve an entity's effective HA area.

        Entity-level area assignment takes precedence over the owning device's
        area assignment.
        """
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        entry = entity_registry.async_get(entity_id)
        if entry is None:
            return None

        entity_area = getattr(entry, "area_id", None)
        if entity_area:
            return entity_area

        if entry.device_id:
            device = device_registry.async_get(entry.device_id)
            if device is not None:
                return getattr(device, "area_id", None)

        return None

    def _entities_in_selected_area(
        self,
        domain: str,
    ) -> list[str]:
        """Return registered entities of a domain in the selected workout room."""
        selected = self.selected_feedback_area_id
        if not selected:
            return []

        entity_registry = er.async_get(self.hass)
        result = []

        for entry in entity_registry.entities.values():
            if not entry.entity_id.startswith(f"{domain}."):
                continue
            if self._entity_area_id(entry.entity_id) == selected:
                result.append(entry.entity_id)

        return sorted(set(result))

    @staticmethod
    def _normalized_color_modes(state) -> set[str]:
        """Normalize Home Assistant ColorMode enums and strings."""
        raw_modes = (
            state.attributes.get("supported_color_modes") or []
            if state is not None
            else []
        )

        result: set[str] = set()

        for mode in raw_modes:
            value = getattr(mode, "value", mode)
            if value is None:
                continue
            result.add(str(value).lower())

        return result

    def workout_adapter_diagnostics(self) -> dict:
        """Return latest completed-workout adapter/fallback diagnostics."""
        try:
            from .providers.workout_adapters.registry import (
                last_adapter_diagnostics,
            )
            return last_adapter_diagnostics()
        except Exception:
            return {}

    def live_feedback_diagnostics(self) -> dict:
        """Return current live coaching diagnostics for UI/entity attributes."""
        configured_lights = list(
            self.config.get(CONF_FEEDBACK_LIGHT_IDS) or []
        )
        selected_areas = list(
            self.config.get(CONF_FEEDBACK_AREA_IDS) or []
        )
        tts_entity = str(
            self.config.get(CONF_TTS_ENTITY_ID) or ""
        ).strip()
        media_players = list(
            self.config.get(CONF_TTS_MEDIA_PLAYER_IDS) or []
        )

        usable_media_players = self._feedback_media_player_ids()

        tts_state = self.hass.states.get(tts_entity) if tts_entity else None
        tts_available = bool(
            tts_entity
            and tts_entity.startswith("tts.")
            and tts_state is not None
            and tts_state.state != "unavailable"
        )

        resolved_lights = self._feedback_light_ids()

        return {
            "workout_adapters": self.workout_adapter_diagnostics(),
            "feedback_enabled": bool(
                resolved_lights
                or (tts_available and usable_media_players)
            ),
            "session_active": self.session_active,
            "configured_feedback_areas": selected_areas,
            "selected_feedback_area_id": self.selected_feedback_area_id,
            "selected_feedback_area_name": self.selected_feedback_area_name(),
            "configured_feedback_lights": configured_lights,
            "resolved_feedback_lights": resolved_lights,
            "tts_entity": tts_entity or None,
            "tts_available": tts_available,
            "tts_media_players": media_players,
            "usable_tts_media_players": usable_media_players,
            "media_players_require_media_play": True,
            "last_feedback_intensity": self.last_feedback_intensity,
            "last_feedback_time": self.last_feedback_time,
            "light_snapshot_active": self._feedback_scene_active,
            "snapshotted_feedback_lights": sorted(
                self._feedback_light_snapshot
            ),
            "last_light_feedback": self.last_feedback_light_result,
            "last_tts_feedback": self.last_feedback_tts_result,
            "last_feedback_message": self.last_feedback_message,
            "intensity_transition_min_age_seconds": 5,
            "last_feedback_bpm": self.last_feedback_bpm,
            "last_feedback_pulse_interval_seconds": (
                self.last_feedback_pulse_interval
            ),
            "last_feedback_pulse_count": self.last_feedback_pulse_count,
            "antplus_capture_switches": self._antplus_capture_switches(),
            "antplus_capture_snapshot": dict(
                self._capture_switch_snapshot
            ),
            "antplus_capture_changed_by_fitness": sorted(
                self._capture_switches_changed_by_fitness
            ),
            "periodic_live_announcements": bool(
                self.config.get(CONF_PERIODIC_LIVE_ANNOUNCEMENTS)
            ),
            "periodic_live_interval_minutes": self.config.get(
                CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
                5,
            ),
            "last_periodic_live_announcement_time": (
                self.last_periodic_live_announcement_time
            ),
            "last_periodic_live_message": self.last_periodic_live_message,
            "live_coaching_context": (
                self.live_coaching_context()
                if self.session_active
                else None
            ),
        }

    def _feedback_light_ids(self) -> list[str]:
        """Resolve intensity lights from the selected Workout room.

        Runtime room semantics:
        - every color-capable light in the selected Workout room is used
        - configured lights with NO area remain global and are also used
        - configured lights assigned to another area are replaced by the
          selected room's lights
        """
        configured_explicit = set(
            self.config.get(CONF_FEEDBACK_LIGHT_IDS) or []
        )
        candidates: set[str] = set()

        selected = self.selected_feedback_area_id

        if selected:
            # Current room determines all room-bound light targets.
            candidates.update(
                self._entities_in_selected_area("light")
            )

            # Explicit area-less lights are global and survive room changes.
            for entity_id in configured_explicit:
                if self._entity_area_id(entity_id) is None:
                    candidates.add(entity_id)
        else:
            # No runtime room selected: fall back to configured targets.
            candidates.update(configured_explicit)

            configured_areas = set(
                self.config.get(CONF_FEEDBACK_AREA_IDS) or []
            )
            if configured_areas:
                entity_registry = er.async_get(self.hass)
                for entry in entity_registry.entities.values():
                    if not entry.entity_id.startswith("light."):
                        continue
                    if self._entity_area_id(entry.entity_id) in configured_areas:
                        candidates.add(entry.entity_id)

        usable: list[str] = []

        for entity_id in candidates:
            if (
                not isinstance(entity_id, str)
                or not entity_id.startswith("light.")
            ):
                continue

            state = self.hass.states.get(entity_id)
            if (
                state is None
                or state.state in ("unavailable", "unknown")
            ):
                continue

            supported = self._normalized_color_modes(state)
            if not supported.intersection(
                {"hs", "xy", "rgb", "rgbw", "rgbww"}
            ):
                continue

            usable.append(entity_id)

        return sorted(set(usable))

    async def _async_snapshot_feedback_lights(
        self,
        light_ids: list[str],
    ) -> bool:
        """Capture original light states in memory before feedback.

        Only entities already validated as existing, available and color-capable
        are included. No Home Assistant scene service is required.
        """
        if not light_ids:
            self.last_feedback_light_result = "no_usable_lights"
            return False

        snapshot: dict[str, dict] = {}

        for entity_id in light_ids:
            state = self.hass.states.get(entity_id)
            if state is None or state.state == "unavailable":
                continue

            attrs = state.attributes

            saved = {
                "state": state.state,
                "brightness": attrs.get("brightness"),
                "color_mode": getattr(
                    attrs.get("color_mode"),
                    "value",
                    attrs.get("color_mode"),
                ),
                "rgb_color": attrs.get("rgb_color"),
                "hs_color": attrs.get("hs_color"),
                "xy_color": attrs.get("xy_color"),
                "color_temp_kelvin": attrs.get("color_temp_kelvin"),
                "effect": attrs.get("effect"),
            }

            snapshot[entity_id] = saved

        if not snapshot:
            self._feedback_light_snapshot = {}
            self._feedback_scene_active = False
            self.last_feedback_light_result = "snapshot_failed"
            return False

        self._feedback_light_snapshot = snapshot
        self._feedback_scene_active = True
        self.last_feedback_light_result = "snapshot_created"
        return True

    async def _async_restore_feedback_lights(
        self,
        *,
        clear_snapshot: bool = True,
    ):
        """Restore every snapshotted light to its pre-feedback state.

        During heartbeat-style pulses the snapshot is retained between pulses.
        The final restore clears it.
        """
        if not self._feedback_scene_active:
            return

        snapshot = dict(self._feedback_light_snapshot)
        success = 0
        failed = 0

        for entity_id, saved in snapshot.items():
            state = self.hass.states.get(entity_id)
            if state is None or state.state == "unavailable":
                failed += 1
                continue

            try:
                if saved.get("state") == "off":
                    await self.hass.services.async_call(
                        "light",
                        "turn_off",
                        {},
                        target={"entity_id": entity_id},
                        blocking=True,
                    )
                    success += 1
                    continue

                service_data = {}

                brightness = saved.get("brightness")
                if brightness is not None:
                    service_data["brightness"] = brightness

                color_mode = str(
                    saved.get("color_mode") or ""
                ).lower()

                # Restore the light using the color representation that was
                # active before feedback.
                if color_mode in ("rgb", "rgbw", "rgbww"):
                    rgb = saved.get("rgb_color")
                    if rgb is not None:
                        service_data["rgb_color"] = list(rgb)

                elif color_mode == "hs":
                    hs = saved.get("hs_color")
                    if hs is not None:
                        service_data["hs_color"] = list(hs)

                elif color_mode == "xy":
                    xy = saved.get("xy_color")
                    if xy is not None:
                        service_data["xy_color"] = list(xy)

                elif color_mode in (
                    "color_temp",
                    "color_temperature",
                ):
                    kelvin = saved.get("color_temp_kelvin")
                    if kelvin is not None:
                        service_data["color_temp_kelvin"] = kelvin

                effect = saved.get("effect")
                if effect not in (None, "none", "None"):
                    service_data["effect"] = effect

                await self.hass.services.async_call(
                    "light",
                    "turn_on",
                    service_data,
                    target={"entity_id": entity_id},
                    blocking=True,
                )
                success += 1

            except Exception:
                failed += 1
                continue

        if clear_snapshot:
            self._feedback_light_snapshot = {}
            self._feedback_scene_active = False

        if success and not failed:
            self.last_feedback_light_result = "success_restored"
        elif success and failed:
            self.last_feedback_light_result = "partial_restore"
        elif failed:
            self.last_feedback_light_result = "restore_failed"
        else:
            self.last_feedback_light_result = "no_usable_lights"

    async def _async_set_feedback_color(
        self,
        light_ids: list[str],
        intensity: str,
    ):
        """Set intensity color independently on every usable light."""
        rgb = intensity_rgb(intensity)

        if not rgb or not light_ids:
            self.last_feedback_light_result = "no_usable_lights"
            return

        success = 0
        failed = 0

        for entity_id in light_ids:
            state = self.hass.states.get(entity_id)
            if state is None or state.state == "unavailable":
                failed += 1
                continue

            supported = self._normalized_color_modes(state)
            if not supported.intersection(
                {"hs", "xy", "rgb", "rgbw", "rgbww"}
            ):
                failed += 1
                continue

            try:
                await self.hass.services.async_call(
                    "light",
                    "turn_on",
                    {
                        "rgb_color": list(rgb),
                        "brightness_pct": 100,
                    },
                    target={"entity_id": entity_id},
                    blocking=True,
                )
                success += 1
            except Exception:
                failed += 1
                continue

        if success and not failed:
            self.last_feedback_light_result = "success"
        elif success and failed:
            self.last_feedback_light_result = "partial_success"
        elif failed:
            self.last_feedback_light_result = "failed"
        else:
            self.last_feedback_light_result = "no_usable_lights"

    async def _async_live_intensity_feedback(self, intensity: str):
        """Show intensity colour for three seconds, then restore the lights."""
        self._feedback_generation += 1
        generation = self._feedback_generation
        light_ids = self._feedback_light_ids()

        current_hr = self.live_values().get(METRIC_HEART_RATE)
        try:
            bpm = (
                int(round(float(current_hr)))
                if current_hr is not None
                else None
            )
        except (TypeError, ValueError):
            bpm = None

        self.last_feedback_intensity = intensity
        self.last_feedback_time = datetime.now(timezone.utc).isoformat()
        self.last_feedback_bpm = bpm

        # Retain the old diagnostic attributes for entity compatibility, but
        # blinking no longer exists.
        self.last_feedback_pulse_interval = 3.0
        self.last_feedback_pulse_count = 1

        snapshot_ok = False
        if not light_ids:
            self.last_feedback_light_result = "no_usable_lights"

        async with self._feedback_lock:
            if light_ids and not self._feedback_scene_active:
                snapshot_ok = await self._async_snapshot_feedback_lights(
                    light_ids
                )
            else:
                snapshot_ok = bool(self._feedback_scene_active)

        # Spoken intensity coaching remains independent from the visual cue.
        message = await self._async_intensity_message(intensity)
        self.last_feedback_message = message

        if message:
            await self._async_speak(message)
        else:
            self.last_feedback_tts_result = "no_message"

        self._notify()

        try:
            if light_ids and snapshot_ok:
                async with self._feedback_lock:
                    await self._async_set_feedback_color(
                        light_ids,
                        intensity,
                    )

                await asyncio.sleep(3.0)

        except asyncio.CancelledError:
            return

        if generation != self._feedback_generation:
            return

        async with self._feedback_lock:
            await self._async_restore_feedback_lights(
                clear_snapshot=True,
            )

        self._notify()

    async def _async_intensity_message(self, intensity: str) -> str:
        """Use AI when enabled; localized static coaching is always a fallback."""
        language = self._ai_language()
        current_hr = self.live_values().get(METRIC_HEART_RATE)
        bpm = (
            int(round(current_hr))
            if current_hr is not None
            else None
        )

        if self.config.get(CONF_AI_ENABLED):
            strings = self._prompt_strings()
            prompt = (
                "Write ONE short motivational coaching sentence for a person "
                f"whose current aerobic exercise intensity is `{intensity}`. "
                f"The current heart rate is {bpm if bpm is not None else 'unknown'} "
                "beats per minute. Include the current BPM naturally in the sentence "
                "when it is available. Do not list other sensor values. Keep it "
                "supportive but not exaggerated, about 12-25 words. Do not give "
                "medical advice. Output only the sentence. "
                f"Write it in {strings['language']}."
            )
            result = await self._call_ai(
                prompt,
                f"Fitness live intensity {self.config.get(CONF_PROFILE_NAME)}",
            )
            if result:
                compact = " ".join(str(result).split()).strip()
                if compact:
                    return compact[:350]

        return static_intensity_message(
            language,
            intensity,
            bpm=bpm,
        )

    def _available_live_source_names(self) -> list[str]:
        """Return friendly names of live sources currently producing data."""
        values = self.live_values(raw=True)
        sources = self.live_sources()
        result: list[str] = []

        for metric, source in sources.items():
            if values.get(metric) is None:
                continue

            state = self.hass.states.get(source.entity_id)
            friendly = (
                state.attributes.get("friendly_name")
                if state is not None
                else None
            )
            name = str(friendly or source.entity_id)
            if name not in result:
                result.append(name)

        return result

    async def _async_session_guidance_message(
        self,
        event: str,
        *,
        sensors: list[str] | None = None,
        seconds: int | None = None,
        remaining: int | None = None,
        collected: bool | None = None,
    ) -> str | None:
        """Generate localized AI/static live-session guidance."""
        language = self._ai_language()

        static_event = event
        if event == "recovery_checkpoint" and collected is False:
            static_event = "recovery_checkpoint_missing"

        fallback = static_session_message(
            language,
            static_event,
            sensors=sensors,
            seconds=seconds,
            remaining=remaining,
        )

        if not self.config.get(CONF_AI_ENABLED):
            return fallback

        context = {
            "event": event,
            "live_sensor_names": sensors or [],
            "checkpoint_seconds": seconds,
            "remaining_seconds": remaining,
            "heart_rate_collected": collected,
        }

        instructions = {
            "waiting_live": (
                "Say that the workout has been started/armed, but the timer has "
                "not started yet because Fitness is waiting for live sensor data."
            ),
            "started_with_live": (
                "Say that the workout has started, name the supplied live sensors "
                "naturally, and say the workout timer has started."
            ),
            "live_available": (
                "Say that live data is now available, name the supplied sensors, "
                "say the workout timer has started, and tell the user they can "
                "begin the workout."
            ),
            "stopped_without_live": (
                "Say the workout was stopped before live sensor data arrived and "
                "therefore no live workout was recorded."
            ),
            "recovery_wait": (
                "Say the workout timer has stopped and ask the user to wait while "
                "post-exercise heart-rate recovery is collected for 120 seconds."
            ),
            "recovery_checkpoint": (
                "Report the supplied post-exercise heart-rate recovery checkpoint. "
                "If heart_rate_collected is true, clearly say that checkpoint was "
                "collected. If false, clearly say no HR value was available there. "
                "State the supplied remaining seconds."
            ),
            "recovery_complete": (
                "Say post-exercise heart-rate recovery collection is complete, all "
                "available recovery data has been saved, and everything is ready."
            ),
            "no_recovery": (
                "Say the workout ended but post-exercise heart-rate recovery could "
                "not be collected because usable heart-rate data was unavailable."
            ),
        }.get(event)

        if not instructions:
            return fallback

        prompt = (
            "Create ONE short spoken Home Assistant fitness status message. "
            f"{instructions} "
            "Do not add medical advice, do not invent sensor names or values, "
            "and do not add information absent from the context. "
            "Use natural conversational language, no markdown, about 10-30 words. "
            f"Output only the spoken sentence in {self._prompt_strings()['language']}.\n\n"
            f"Context: {json.dumps(context, ensure_ascii=False)}"
        )

        # Session-state guidance must be timely. Give AI a short chance to
        # personalize the wording, then use the localized deterministic fallback
        # rather than leaving Start/Stop/Recovery feedback waiting on an LLM.
        try:
            result = await asyncio.wait_for(
                self._call_ai(
                    prompt,
                    (
                        "Fitness session guidance "
                        f"{self.config.get(CONF_PROFILE_NAME)}"
                    ),
                ),
                timeout=2.5,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            result = None

        if result:
            compact = " ".join(str(result).split()).strip()
            if compact:
                return compact[:450]

        return fallback

    async def _async_announce_session_guidance(
        self,
        event: str,
        **context,
    ) -> None:
        """Speak session guidance in order without affecting measurement timing."""
        async with self._session_announcement_lock:
            message = await self._async_session_guidance_message(
                event,
                **context,
            )
            if not message:
                return
            self.last_feedback_message = message
            await self._async_speak(message)
            self._notify()

    def _queue_session_guidance(
        self,
        event: str,
        **context,
    ) -> None:
        """Queue guidance without blocking capture/recovery timers."""
        self.hass.async_create_task(
            self._async_announce_session_guidance(
                event,
                **context,
            )
        )

    def _recent_live_trend(
        self,
        metric: str,
        *,
        window_seconds: int = 90,
    ) -> dict | None:
        """Describe the recent direction of a live metric.

        This is a simple descriptive comparison of the first and second halves
        of recent captured samples. It is not a physiological model.
        """
        if not self.samples:
            return None

        now = datetime.now(timezone.utc)
        recent = []

        for sample in reversed(self.samples):
            timestamp = sample.get("timestamp")
            try:
                dt = datetime.fromisoformat(str(timestamp))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue

            if (now - dt).total_seconds() > window_seconds:
                break

            value = sample.get(metric)
            if value is not None:
                try:
                    recent.append((dt, float(value)))
                except (TypeError, ValueError):
                    continue

        if len(recent) < 4:
            return None

        recent.sort(key=lambda item: item[0])
        midpoint = len(recent) // 2
        first = [value for _, value in recent[:midpoint]]
        second = [value for _, value in recent[midpoint:]]

        if not first or not second:
            return None

        first_avg = mean(first)
        second_avg = mean(second)
        delta = second_avg - first_avg

        scale = max(abs(first_avg), 1.0)
        relative_change = delta / scale * 100.0

        if relative_change >= 3.0:
            direction = "rising"
        elif relative_change <= -3.0:
            direction = "falling"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "delta": round(delta, 2),
            "relative_change_percent": round(relative_change, 1),
            "window_seconds": window_seconds,
            "sample_count": len(recent),
        }

    def live_coaching_context(self) -> dict:
        """Return normalized live data plus individualized relative context."""
        live = self.live_values()
        evaluation = self.evaluation()

        heart_rate = live.get(METRIC_HEART_RATE)
        power = live.get(METRIC_POWER)
        cadence = live.get(METRIC_CADENCE)
        speed_kmh = live.get(METRIC_SPEED)
        pace = pace_from_speed_kmh(speed_kmh)

        max_hr = evaluation.get("max_hr")
        resting_hr = evaluation.get("resting_hr")
        threshold_hr = evaluation.get("threshold_hr")
        threshold_power = evaluation.get("threshold_power")
        threshold_pace = evaluation.get("threshold_pace")
        weight = evaluation.get("weight")

        hrr_pct = percent_hrr(
            heart_rate,
            max_hr,
            resting_hr,
        )
        hrmax_pct = percent_max_hr(
            heart_rate,
            max_hr,
        )
        intensity = acsm_hrr_intensity(hrr_pct)

        threshold_hr_pct = relative_percent(
            heart_rate,
            threshold_hr,
        )
        threshold_power_pct = relative_percent(
            power,
            threshold_power,
        )

        threshold_speed_kmh = speed_from_pace_min_km(
            threshold_pace
        )
        threshold_speed_pct = relative_percent(
            speed_kmh,
            threshold_speed_kmh,
        )

        power_to_weight = (
            power / weight
            if power is not None and weight
            else None
        )

        return {
            "session_duration_minutes": round(
                self.session_duration() / 60.0,
                1,
            ),
            "heart_rate_bpm": (
                round(heart_rate)
                if heart_rate is not None else None
            ),
            "heart_rate_percent_max": (
                round(hrmax_pct, 1)
                if hrmax_pct is not None else None
            ),
            "heart_rate_reserve_percent": (
                round(hrr_pct, 1)
                if hrr_pct is not None else None
            ),
            "heart_rate_intensity": intensity,
            "heart_rate_relative_threshold_percent": (
                round(threshold_hr_pct, 1)
                if threshold_hr_pct is not None else None
            ),
            "power_w": (
                round(power)
                if power is not None else None
            ),
            "power_to_weight_w_kg": (
                round(power_to_weight, 2)
                if power_to_weight is not None else None
            ),
            "power_relative_threshold_percent": (
                round(threshold_power_pct, 1)
                if threshold_power_pct is not None else None
            ),
            "cadence_per_min": (
                round(cadence)
                if cadence is not None else None
            ),
            "speed_kmh": (
                round(speed_kmh, 2)
                if speed_kmh is not None else None
            ),
            "pace_min_km": (
                round(pace, 2)
                if pace is not None else None
            ),
            "speed_relative_threshold_percent": (
                round(threshold_speed_pct, 1)
                if threshold_speed_pct is not None else None
            ),
            "heart_rate_trend": self._recent_live_trend(
                METRIC_HEART_RATE
            ),
            "power_trend": self._recent_live_trend(
                METRIC_POWER
            ),
            "cadence_trend": self._recent_live_trend(
                METRIC_CADENCE
            ),
            "speed_trend": self._recent_live_trend(
                METRIC_SPEED
            ),
        }

    def _periodic_live_interval_seconds(self) -> float:
        """Return configured periodic announcement cadence in seconds."""
        raw = self.config.get(
            CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
            5,
        )
        try:
            minutes = float(raw)
        except (TypeError, ValueError):
            minutes = 5.0

        # Avoid accidental rapid-fire TTS while still allowing practical tests.
        minutes = max(1.0, min(minutes, 120.0))
        return minutes * 60.0

    async def _async_periodic_live_message(self) -> str | None:
        """Generate an interpreted live workout status summary."""
        context = self.live_coaching_context()

        if not any(
            context.get(key) is not None
            for key in (
                "heart_rate_bpm",
                "heart_rate_intensity",
                "power_w",
                "cadence_per_min",
                "pace_min_km",
            )
        ):
            return None

        if self.config.get(CONF_AI_ENABLED):
            strings = self._prompt_strings()

            prompt = (
                "Give ONE concise spoken coaching update for an ongoing workout. "
                "Interpret the structured data instead of reading fields aloud. "
                "Prioritize individualized relative intensity: %HRR, heart rate "
                "versus threshold, power versus threshold, current power-to-weight, "
                "and pace/speed versus threshold when available. Use recent trends "
                "to notice useful patterns such as heart rate rising while power is "
                "stable, or power increasing while heart rate remains stable. "
                "Do not claim cardiac drift from a short trend alone. Mention current "
                "BPM naturally. Mention no more than three numerical values total. "
                "Use simple athlete-friendly language to say whether the effort looks "
                "easy, steady, near threshold, above threshold, or changing only when "
                "the supplied relative data supports that interpretation. End with "
                "one short actionable coaching cue. Do not diagnose disease, do not "
                "invent zones, and do not treat FTP, critical power and lactate-"
                "threshold power as interchangeable. Keep it about 25-45 spoken words, "
                "no bullet points, and output only the sentence in "
                f"{strings['language']}.\n\n"
                f"Live coaching context: "
                f"{json.dumps(context, ensure_ascii=False)}"
            )

            result = await self._call_ai(
                prompt,
                f"Fitness smart live update {self.config.get(CONF_PROFILE_NAME)}",
            )

            if result:
                compact = " ".join(str(result).split()).strip()
                if compact:
                    return compact[:600]

        return self._static_smart_live_message(context)

    def _static_smart_live_message(
        self,
        context: dict,
    ) -> str | None:
        """Deterministic fallback that prioritizes relative workout context."""
        language = self._ai_language()

        base = static_periodic_live_message(
            language,
            heart_rate=context.get("heart_rate_bpm"),
            intensity=context.get("heart_rate_intensity"),
            power=context.get("power_w"),
            cadence=context.get("cadence_per_min"),
            pace=context.get("pace_min_km"),
        )

        if not base:
            return None

        extra = None
        power_pct = context.get("power_relative_threshold_percent")
        hr_pct = context.get("heart_rate_relative_threshold_percent")
        speed_pct = context.get("speed_relative_threshold_percent")

        if power_pct is not None:
            if power_pct < 85:
                extra = "Power is clearly below your configured threshold."
            elif power_pct <= 100:
                extra = "Power is close to your configured threshold."
            else:
                extra = "Power is above your configured threshold."
        elif speed_pct is not None:
            if speed_pct < 90:
                extra = "Your speed is comfortably below threshold pace."
            elif speed_pct <= 102:
                extra = "Your speed is close to threshold pace."
            else:
                extra = "Your speed is above threshold pace."
        elif hr_pct is not None:
            if hr_pct < 90:
                extra = "Heart rate is below your configured threshold."
            elif hr_pct <= 100:
                extra = "Heart rate is close to your configured threshold."
            else:
                extra = "Heart rate is above your configured threshold."

        if language == "en" and extra:
            return f"{base} {extra}"

        return base

    async def _async_periodic_live_announcements(self):
        """Speak live workout data at the configured cadence while active."""
        try:
            while self.session_active:
                await asyncio.sleep(
                    self._periodic_live_interval_seconds()
                )

                if not self.session_active:
                    break

                message = await self._async_periodic_live_message()
                if not message:
                    continue

                self.last_periodic_live_announcement_time = (
                    datetime.now(timezone.utc).isoformat()
                )
                self.last_periodic_live_message = message

                await self._async_speak(message)
                self._notify()

        except asyncio.CancelledError:
            return

    def _tts_language_for_entity(
        self,
        tts_entity: str,
    ) -> str | None:
        """Use the HA language only when the selected TTS provider advertises it."""
        state = self.hass.states.get(tts_entity)
        if state is None:
            return None

        supported = state.attributes.get("supported_languages")
        if not isinstance(supported, (list, tuple)):
            return None

        desired = self._ai_language().lower()

        for item in supported:
            candidate = str(item)
            low = candidate.lower()
            if low == desired or low.startswith(desired + "-") or low.startswith(desired + "_"):
                return candidate

        return None

    @staticmethod
    def _media_player_supports_media_play(state) -> bool:
        """Return whether a media player supports media_player.media_play.

        Home Assistant represents this with MediaPlayerEntityFeature.PLAY in
        the entity's supported_features bitmask.
        """
        if state is None:
            return False

        raw = state.attributes.get("supported_features", 0)
        try:
            supported = int(raw or 0)
        except (TypeError, ValueError):
            return False

        return bool(
            supported
            & int(MediaPlayerEntityFeature.PLAY)
        )

    def _feedback_media_player_ids(self) -> list[str]:
        """Resolve announcement players while respecting explicit setup targets.

        Rules:
        - Explicitly configured players are authoritative.
        - A configured player with no HA area is global and always remains.
        - A configured player in the currently selected Workout room remains.
        - Only a configured player assigned to a DIFFERENT area is replaced by
          usable media players in the selected Workout room.
        - Merely selecting a room never adds extra room players when all
          configured targets are already valid for that room.
        - Every returned player must be available and support media_play.
        """
        configured = {
            entity_id
            for entity_id in (
                self.config.get(CONF_TTS_MEDIA_PLAYER_IDS) or []
            )
            if isinstance(entity_id, str)
            and entity_id.startswith("media_player.")
        }

        candidates: set[str] = set()
        selected = self.selected_feedback_area_id
        needs_room_replacement = False

        for entity_id in configured:
            area_id = self._entity_area_id(entity_id)

            if not selected:
                candidates.add(entity_id)
                continue

            if area_id is None or area_id == selected:
                candidates.add(entity_id)
                continue

            # The configured player is bound to another room. Do not follow it
            # across rooms; replace that room-bound target using the selected
            # Workout room instead.
            needs_room_replacement = True

        if selected and needs_room_replacement:
            candidates.update(
                self._entities_in_selected_area("media_player")
            )

        usable = []

        for entity_id in candidates:
            state = self.hass.states.get(entity_id)
            if (
                state is None
                or state.state in ("unavailable", "unknown")
            ):
                continue

            if not self._media_player_supports_media_play(state):
                continue

            usable.append(entity_id)

        return sorted(set(usable))

    async def _async_speak(self, message: str):
        """Speak only through existing/available configured entities."""
        tts_entity = str(
            self.config.get(CONF_TTS_ENTITY_ID) or ""
        ).strip()

        if not message:
            self.last_feedback_tts_result = "no_message"
            return

        if not tts_entity or not tts_entity.startswith("tts."):
            self.last_feedback_tts_result = "no_tts_entity"
            return

        tts_state = self.hass.states.get(tts_entity)
        if tts_state is None:
            self.last_feedback_tts_result = "tts_entity_missing"
            return
        if tts_state.state == "unavailable":
            self.last_feedback_tts_result = "tts_entity_unavailable"
            return

        media_players = self._feedback_media_player_ids()

        if not media_players:
            self.last_feedback_tts_result = "no_usable_media_players"
            return

        if not self.hass.services.has_service("tts", "speak"):
            self.last_feedback_tts_result = "tts_service_missing"
            return

        language = self._tts_language_for_entity(tts_entity)
        success = 0
        failed = 0

        # Call one media player at a time so a failing speaker cannot suppress
        # announcements on the others.
        for media_player in media_players:
            data = {
                "media_player_entity_id": media_player,
                "message": message,
                "cache": False,
            }

            if language:
                data["language"] = language

            try:
                await self.hass.services.async_call(
                    "tts",
                    "speak",
                    data,
                    target={"entity_id": tts_entity},
                    blocking=True,
                )
                success += 1
            except Exception:
                failed += 1
                continue

        if success and not failed:
            self.last_feedback_tts_result = "success"
        elif success and failed:
            self.last_feedback_tts_result = "partial_success"
        else:
            self.last_feedback_tts_result = "failed"

    async def _async_notify(
        self,
        *,
        title: str,
        message: str,
    ):
        """Notify every usable target independently."""
        if not message:
            return

        if not self.hass.services.has_service(
            "notify",
            "send_message",
        ):
            return

        for entity_id in list(
            self.config.get(CONF_NOTIFY_ENTITY_IDS) or []
        ):
            if not isinstance(entity_id, str) or not entity_id.startswith("notify."):
                continue

            state = self.hass.states.get(entity_id)
            if state is None or state.state == "unavailable":
                continue

            try:
                await self.hass.services.async_call(
                    "notify",
                    "send_message",
                    {
                        "title": title,
                        "message": message,
                    },
                    target={"entity_id": entity_id},
                    blocking=False,
                )
            except Exception:
                continue

    def _static_workout_announcement(
        self,
        workout: Workout,
    ) -> tuple[str, str]:
        duration = int(
            round((workout.duration_s or 0) / 60)
        )
        distance_km = (
            workout.distance_m / 1000.0
            if workout.distance_m is not None
            else None
        )
        return static_workout_message(
            self._ai_language(),
            name=workout.name or workout.sport or "Workout",
            duration_minutes=duration,
            distance_km=distance_km,
        )

    async def _async_handle_new_workout(
        self,
        workout: Workout,
    ):
        """Evaluate/announce only a genuinely populated new workout."""
        if not self._workout_has_real_information(workout):
            return

        if self.config.get(CONF_AI_ENABLED):
            await self.async_generate_ai(
                general=True,
                workout=True,
            )

        static_title, static_message = self._static_workout_announcement(
            workout
        )

        # AI gives the richer interpretation; static localized text guarantees
        # useful feedback if the AI provider is unavailable.
        message = (
            self.ai_workout
            if self.config.get(CONF_AI_ENABLED) and self.ai_workout
            else static_message
        )

        # Keep spoken feedback concise even when the AI workout paragraph is long.
        spoken = message
        if self.config.get(CONF_AI_ENABLED) and self.ai_workout:
            sentences = re.split(r"(?<=[.!?])\s+", self.ai_workout)
            spoken = " ".join(sentences[:2]).strip() or self.ai_workout

        await self._async_speak(spoken)
        await self._async_notify(
            title=static_title,
            message=message,
        )

    def age(self) -> int:
        dob = datetime.fromisoformat(self.config[CONF_DATE_OF_BIRTH]).date()
        today = datetime.now().date()
        return today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )

    def input_value(self, key):
        """Resolve configured values using the field's canonical quantity/unit."""
        quantity_map = {
            CONF_WEIGHT: "weight",
            CONF_RESTING_HR: "heart_rate",
            CONF_MAX_HR: "heart_rate",
            CONF_VO2MAX: "vo2max",
            "height": "height",
            "threshold_hr": "heart_rate",
            "threshold_pace": "pace",
            "threshold_power": "power",
        }
        return resolve_number_or_entity(
            self.hass,
            self.config.get(key),
            quantity=quantity_map.get(key),
        ).value

    def live_values(self, raw: bool = False) -> dict[str, float | None]:
        """Return live measurements in canonical Fitness units.

        By design all Live sensor values become unavailable outside an active
        Fitness workout. Internal capture/recovery code can request raw=True.
        """
        if not raw and not self.session_active:
            return {
                METRIC_HEART_RATE: None,
                METRIC_POWER: None,
                METRIC_CADENCE: None,
                METRIC_SPEED: None,
                METRIC_DISTANCE: None,
                METRIC_ALTITUDE: None,
            }

        sources = discover_sources(self.hass, self.config)
        quantity_map = {
            METRIC_HEART_RATE: "heart_rate",
            METRIC_POWER: "power",
            METRIC_CADENCE: "cadence",
            METRIC_SPEED: "speed",
            METRIC_DISTANCE: "distance",
            METRIC_ALTITUDE: "altitude",
        }
        result = {}
        for metric, source in sources.items():
            result[metric] = numeric_entity_state(
                self.hass,
                source.entity_id,
                quantity=quantity_map.get(metric),
            )
        return result

    def live_sources(self):
        return discover_sources(self.hass, self.config)

    def _has_valid_live_workout_data(self) -> bool:
        values = self.live_values(raw=True)
        return any(
            values.get(metric) is not None
            for metric in (
                METRIC_HEART_RATE,
                METRIC_POWER,
                METRIC_CADENCE,
                METRIC_SPEED,
                METRIC_DISTANCE,
            )
        )

    def _begin_session_from_live_data(
        self,
        *,
        announcement_event: str = "live_available",
    ) -> None:
        """Convert armed capture into active timing on first valid live data."""
        if not self.session_armed or self.session_active:
            return

        self.session_armed = False
        self.session_active = True
        self.recovery_active = False
        self.session_started = datetime.now(timezone.utc)
        self.samples = []

        self._last_live_intensity = None
        self._last_live_intensity_accepted_at = None
        self.last_feedback_intensity = None
        self.last_feedback_time = None
        self.last_feedback_light_result = None
        self.last_feedback_tts_result = None
        self.last_feedback_message = None

        self._capture_sample()

        if self.config.get(CONF_PERIODIC_LIVE_ANNOUNCEMENTS):
            if (
                self._periodic_live_announcement_task is None
                or self._periodic_live_announcement_task.done()
            ):
                self._periodic_live_announcement_task = (
                    self.hass.async_create_task(
                        self._async_periodic_live_announcements()
                    )
                )

        self._queue_session_status_cue(
            "green",
            finish_waiting=(announcement_event == "live_available"),
            resume_intensity=True,
        )

        self._queue_session_guidance(
            announcement_event,
            sensors=self._available_live_source_names(),
        )
        self._notify()

    def _capture_sample(self):
        values = self.live_values(raw=True)
        if not any(v is not None for v in values.values()):
            return

        now = datetime.now(timezone.utc)
        self.samples.append(
            {
                "timestamp": now.isoformat(),
                "_timestamp_epoch": now.timestamp(),
                **values,
            }
        )

    def _antplus_capture_switches(self) -> list[str]:
        """Find every Capture-like switch belonging to ANT+ integrations."""
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        candidates: list[tuple[int, str]] = []

        def config_entry_domain(config_entry_id: str | None) -> str | None:
            if not config_entry_id:
                return None
            config_entry = self.hass.config_entries.async_get_entry(
                config_entry_id
            )
            return (
                config_entry.domain
                if config_entry is not None
                else None
            )

        for entry in entity_registry.entities.values():
            if not entry.entity_id.startswith("switch."):
                continue

            belongs_to_antplus = (
                config_entry_domain(entry.config_entry_id)
                in ANTPLUS_DOMAINS
            )

            if not belongs_to_antplus and entry.device_id:
                device = device_registry.async_get(entry.device_id)
                if device is not None:
                    belongs_to_antplus = any(
                        config_entry_domain(config_entry_id)
                        in ANTPLUS_DOMAINS
                        for config_entry_id in (
                            getattr(device, "config_entries", None)
                            or []
                        )
                    )

            if not belongs_to_antplus:
                continue

            state = self.hass.states.get(entry.entity_id)
            label = " ".join(
                (
                    entry.entity_id,
                    entry.name or "",
                    entry.original_name or "",
                    str(
                        state.attributes.get("friendly_name") or ""
                    ) if state else "",
                )
            ).lower()

            score = 0
            if "capture" in label:
                score += 100
            if "scan" in label:
                score += 50
            if "record" in label:
                score += 40

            if score:
                candidates.append((score, entry.entity_id))

        candidates.sort(
            key=lambda item: (-item[0], item[1])
        )
        return [
            entity_id
            for _score, entity_id in candidates
        ]

    async def _async_restore_stale_capture_snapshot(self) -> None:
        """Restore a persisted capture snapshot after a HA restart."""
        await asyncio.sleep(5)

        if (
            self.session_active
            or self.session_armed
            or self.recovery_active
            or not self._capture_switch_snapshot
        ):
            return

        self.capture_control = await self._async_antplus_control(False)
        self._notify()

    async def _async_antplus_control(self, start: bool) -> str:
        """Temporarily enable all ANT+ Capture switches and restore them later."""
        switch_ids = self._antplus_capture_switches()

        if switch_ids:
            if start:
                # Snapshot current states only once per workout ownership cycle.
                if not self._capture_switch_snapshot:
                    for entity_id in switch_ids:
                        state = self.hass.states.get(entity_id)
                        if (
                            state is not None
                            and state.state in ("on", "off")
                        ):
                            self._capture_switch_snapshot[
                                entity_id
                            ] = state.state

                    self._capture_switches_changed_by_fitness = set()
                    await self._save()

                turned_on: list[str] = []
                already_on: list[str] = []
                unavailable: list[str] = []
                failed: list[str] = []

                for entity_id in switch_ids:
                    state = self.hass.states.get(entity_id)

                    if (
                        state is None
                        or state.state in ("unknown", "unavailable")
                    ):
                        unavailable.append(entity_id)
                        continue

                    # If a switch appeared after the initial snapshot, snapshot
                    # it before Fitness modifies it.
                    if (
                        entity_id not in self._capture_switch_snapshot
                        and state.state in ("on", "off")
                    ):
                        self._capture_switch_snapshot[
                            entity_id
                        ] = state.state

                    if state.state == "on":
                        already_on.append(entity_id)
                        continue

                    if state.state != "off":
                        unavailable.append(entity_id)
                        continue

                    try:
                        await self.hass.services.async_call(
                            "switch",
                            "turn_on",
                            {},
                            target={"entity_id": entity_id},
                            blocking=True,
                        )
                        turned_on.append(entity_id)
                        self._capture_switches_changed_by_fitness.add(
                            entity_id
                        )
                    except Exception:
                        failed.append(entity_id)

                await self._save()

                return (
                    "capture_snapshot:"
                    f"turned_on={len(turned_on)},"
                    f"already_on={len(already_on)},"
                    f"unavailable={len(unavailable)},"
                    f"failed={len(failed)}"
                )

            # Stop/recovery completion: restore exact original states.
            if self._capture_switch_snapshot:
                snapshot = dict(self._capture_switch_snapshot)
                restored_on: list[str] = []
                restored_off: list[str] = []
                unavailable: list[str] = []
                failed: list[str] = []

                for entity_id, original_state in snapshot.items():
                    state = self.hass.states.get(entity_id)

                    if (
                        state is None
                        or state.state in ("unknown", "unavailable")
                    ):
                        unavailable.append(entity_id)
                        continue

                    if state.state == original_state:
                        if original_state == "on":
                            restored_on.append(entity_id)
                        else:
                            restored_off.append(entity_id)
                        continue

                    service = (
                        "turn_on"
                        if original_state == "on"
                        else "turn_off"
                    )

                    try:
                        await self.hass.services.async_call(
                            "switch",
                            service,
                            {},
                            target={"entity_id": entity_id},
                            blocking=True,
                        )
                        if original_state == "on":
                            restored_on.append(entity_id)
                        else:
                            restored_off.append(entity_id)
                    except Exception:
                        failed.append(entity_id)

                unresolved = set(unavailable) | set(failed)

                # Never forget a switch that could not yet be restored.
                if unresolved:
                    self._capture_switch_snapshot = {
                        entity_id: original_state
                        for entity_id, original_state
                        in snapshot.items()
                        if entity_id in unresolved
                    }
                    self._capture_switches_changed_by_fitness.intersection_update(
                        unresolved
                    )
                else:
                    self._capture_switch_snapshot = {}
                    self._capture_switches_changed_by_fitness = set()

                await self._save()

                return (
                    "capture_restore:"
                    f"on={len(restored_on)},"
                    f"off={len(restored_off)},"
                    f"unresolved={len(unresolved)}"
                )

            return "capture_restore:no_snapshot"

        # Compatibility fallback for ANT+ integrations without stateful
        # capture switches.
        device_ids = set(
            source_device_ids(self.hass, self.config)
        )
        registry = er.async_get(self.hass)

        service_names = (
            ("start_capture", "start_scan", "start")
            if start
            else ("stop_capture", "stop_scan", "stop")
        )

        for domain in ANTPLUS_DOMAINS:
            for service in service_names:
                if self.hass.services.has_service(domain, service):
                    await self.hass.services.async_call(
                        domain,
                        service,
                        {},
                        blocking=True,
                    )
                    return f"service:{domain}.{service}"

        wanted = (
            ("start", "capture")
            if start
            else ("stop", "capture")
        )
        pressed: list[str] = []

        for entry in registry.entities.values():
            if entry.device_id not in device_ids:
                continue
            if not entry.entity_id.startswith("button."):
                continue

            label = " ".join(
                (
                    entry.entity_id,
                    entry.name or "",
                    entry.original_name or "",
                )
            ).lower()

            if not all(token in label for token in wanted):
                continue

            try:
                await self.hass.services.async_call(
                    "button",
                    "press",
                    {},
                    target={"entity_id": entry.entity_id},
                    blocking=True,
                )
                pressed.append(entry.entity_id)
            except Exception:
                continue

        if pressed:
            return "buttons:" + ",".join(sorted(pressed))

        return "no_antplus_capture_control_found"

    async def async_start_session(self):
        """Arm workout capture; the timer starts only on first valid live data."""
        if self.session_active or self.session_armed:
            return

        if self._recovery_task and not self._recovery_task.done():
            self._recovery_task.cancel()
            self._recovery_task = None

        self.recovery_active = False
        self.session_armed = True
        self.session_started = None
        self.samples = []

        self._last_live_intensity = None
        self._last_live_intensity_accepted_at = None
        self.last_feedback_intensity = None
        self.last_feedback_time = None
        self.last_feedback_light_result = None
        self.last_feedback_tts_result = None
        self.last_feedback_message = None

        self.capture_control = await self._async_antplus_control(True)

        # If usable data already exists after capture is enabled, timing can
        # begin immediately. Otherwise remain armed until a later source event.
        if self._has_valid_live_workout_data():
            self._begin_session_from_live_data(
                announcement_event="started_with_live",
            )
        else:
            self._queue_session_status_waiting_red()
            self._queue_session_guidance("waiting_live")
            self._notify()

    async def async_stop_session(self):
        """Stop workout timing; optionally keep capture for 120 s HR recovery."""
        if self.session_armed and not self.session_active:
            self.session_armed = False
            self.capture_control = await self._async_antplus_control(False)

            if self._session_waiting_red or self._feedback_scene_active:
                self._queue_session_status_cue(
                    "red",
                    finish_waiting=True,
                )

            self._queue_session_guidance("stopped_without_live")
            self._notify()
            return

        if not self.session_active:
            return

        self._capture_sample()
        stop_time = datetime.now(timezone.utc)

        previous_signature = self._workout_signature(
            self.latest_workout()
        )

        workout = self._finalize_local_workout(stop_time)

        # The workout itself is over now. Live entities immediately become
        # unavailable even if ANT capture remains on for recovery.
        self.session_active = False
        self.session_armed = False

        # Visual indication that workout timing is over and post-exercise
        # handling has begun. It restores the exact pre-cue light state.
        self._queue_session_status_cue("red")

        if (
            self._periodic_live_announcement_task
            and not self._periodic_live_announcement_task.done()
        ):
            self._periodic_live_announcement_task.cancel()
        self._periodic_live_announcement_task = None

        if workout is not None:
            self.history.append(workout.as_dict())
            self.history = self.history[-MAX_STORED_WORKOUTS:]

        await self._save()
        self._notify()

        # HR recovery requires post-exercise HR samples. Keep ANT capture alive
        # for up to two minutes when HR was present at workout end.
        last_hr = None
        for sample in reversed(self.samples):
            if sample.get(METRIC_HEART_RATE) is not None:
                last_hr = float(sample[METRIC_HEART_RATE])
                break

        if workout is not None and last_hr is not None:
            self.recovery_active = True
            self._recovery_reference_hr = last_hr
            self._recovery_workout_start = workout.start
            self._queue_session_guidance("recovery_wait")
            self._recovery_task = self.hass.async_create_task(
                self._async_collect_heart_rate_recovery()
            )
        else:
            self.capture_control = await self._async_antplus_control(False)
            if workout is not None:
                self._queue_session_guidance("no_recovery")

        latest = self.latest_workout()
        latest_signature = self._workout_signature(latest)

        if (
            latest is not None
            and latest_signature is not None
            and latest_signature != previous_signature
        ):
            self._last_external_signature = latest_signature

            # If HR recovery is running, defer the final workout AI/summary
            # until the recovery checkpoints have been written to history.
            if not self.recovery_active and (
                latest_signature
                != self._last_announced_workout_signature
            ):
                self._last_announced_workout_signature = (
                    latest_signature
                )
                await self._save()
                await self._async_handle_new_workout(latest)

        if not self.recovery_active:
            self.hass.async_create_task(
                self._async_refresh_long_term_statistics()
            )

    async def _async_collect_heart_rate_recovery(self) -> None:
        """Measure HR fall at 10/30/60/120 s after the workout timer stops."""
        reference = self._recovery_reference_hr
        workout_start = self._recovery_workout_start
        if reference is None or workout_start is None:
            self.recovery_active = False
            self.capture_control = await self._async_antplus_control(False)
            return

        checkpoints = (
            (10, "hrr_10s"),
            (30, "hrr_30s"),
            (60, "hrr_60s"),
            (120, "hrr_120s"),
        )
        elapsed = 0

        try:
            for seconds, field_name in checkpoints:
                await asyncio.sleep(seconds - elapsed)
                elapsed = seconds

                hr = self.live_values(raw=True).get(
                    METRIC_HEART_RATE
                )
                remaining = max(0, 120 - seconds)

                checkpoint_color = {
                    10: "orange",
                    30: "yellow",
                    60: "blue",
                    120: "green",
                }.get(seconds)
                if checkpoint_color is not None:
                    self._queue_session_status_cue(
                        checkpoint_color,
                    )

                if hr is None:
                    self._queue_session_guidance(
                        "recovery_checkpoint",
                        seconds=seconds,
                        remaining=remaining,
                        collected=False,
                    )
                    continue

                recovery = max(0.0, reference - float(hr))

                for item in reversed(self.history):
                    if item.get("start") == workout_start:
                        item[field_name] = round(recovery, 1)
                        break

                await self._save()
                self._queue_session_guidance(
                    "recovery_checkpoint",
                    seconds=seconds,
                    remaining=remaining,
                    collected=True,
                )
                self._notify()

        except asyncio.CancelledError:
            return
        finally:
            self.recovery_active = False
            self._recovery_reference_hr = None
            self._recovery_workout_start = None
            self.capture_control = await self._async_antplus_control(False)
            await self._save()
            self._notify()

            # Final readiness cue is queued after the 120 s checkpoint cue.
            self._queue_session_guidance("recovery_complete")

            # The completed workout evaluation/summary now sees all available
            # HR-recovery checkpoints rather than the pre-recovery workout.
            latest = self.latest_workout()
            latest_signature = self._workout_signature(latest)
            if (
                latest is not None
                and latest_signature is not None
                and latest_signature
                != self._last_announced_workout_signature
            ):
                self._last_external_signature = latest_signature
                self._last_announced_workout_signature = latest_signature
                await self._save()
                await self._async_handle_new_workout(latest)

            self.hass.async_create_task(
                self._async_refresh_long_term_statistics()
            )

    def session_duration(self) -> float:
        if not self.session_active or not self.session_started:
            return 0.0
        return max(
            0.0,
            (
                datetime.now(timezone.utc)
                - self.session_started
            ).total_seconds(),
        )

    def session_status(self) -> str:
        if self.session_active:
            return "active"
        if self.session_armed:
            return "waiting_for_live_data"
        if self.recovery_active:
            return "recovery"
        return "idle"

    def _infer_sport(self) -> str:
        # Device/entity naming is only used to name the workout, never for
        # physiological calculations.
        text = " ".join(
            source.entity_id for source in self.live_sources().values()
        ).lower()
        if any(x in text for x in ("stryd", "run", "footpod", "foot_pod")):
            return "Run"
        if any(x in text for x in ("bike", "cycling", "bicycle", "cadence")) and "stryd" not in text:
            return "Ride"
        return "Workout"

    def _workout_name(self, start: datetime, sport: str) -> str:
        hour = start.astimezone().hour
        if 5 <= hour < 12:
            part = "Morning"
        elif 12 <= hour < 17:
            part = "Afternoon"
        elif 17 <= hour < 22:
            part = "Evening"
        else:
            part = "Night"
        return f"{part} {sport} – {start.astimezone():%Y-%m-%d %H:%M}"

    @staticmethod
    def _percent_difference_from_baseline(
        current: float | None,
        baseline: float | None,
    ) -> float | None:
        if current is None or baseline is None:
            return None
        try:
            current = float(current)
            baseline = float(baseline)
        except (TypeError, ValueError):
            return None
        if baseline == 0:
            return None
        return ((current - baseline) / abs(baseline)) * 100.0

    @staticmethod
    def _safe_mean(values: list[float]) -> float | None:
        clean = []
        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                clean.append(number)
        return mean(clean) if clean else None

    def _comparable_local_workouts(
        self,
        workout: Workout,
        *,
        lookback_days: int = 90,
    ) -> list[Workout]:
        """Return similar prior Fitness workouts for personal comparison.

        Similarity is deliberately conservative:
        - same normalized sport when known
        - previous workouts only
        - within 90 days
        - duration within ±35% when both durations exist
        - distance within ±35% when both distances exist

        This is not a scientific population classifier; it is a personal
        within-subject comparison filter.
        """
        now_start = _dt(workout.start)
        if now_start is None:
            return []

        result: list[Workout] = []
        current_sport = _sport_key(workout.sport)

        for previous in self.local_workouts():
            prev_start = _dt(previous.start)
            if prev_start is None or prev_start >= now_start:
                continue

            age_days = (now_start - prev_start).total_seconds() / 86400.0
            if age_days < 0 or age_days > lookback_days:
                continue

            prev_sport = _sport_key(previous.sport)
            generic = {"", "workout", "activity", "exercise", "session"}

            if (
                current_sport not in generic
                and prev_sport not in generic
                and current_sport != prev_sport
            ):
                continue

            if (
                workout.duration_s is not None
                and previous.duration_s is not None
            ):
                reference = max(
                    abs(float(workout.duration_s)),
                    abs(float(previous.duration_s)),
                    1.0,
                )
                if (
                    abs(
                        float(workout.duration_s)
                        - float(previous.duration_s)
                    )
                    / reference
                    > 0.35
                ):
                    continue

            if (
                workout.distance_m is not None
                and previous.distance_m is not None
                and max(
                    abs(float(workout.distance_m)),
                    abs(float(previous.distance_m)),
                ) > 500
            ):
                reference = max(
                    abs(float(workout.distance_m)),
                    abs(float(previous.distance_m)),
                    1.0,
                )
                if (
                    abs(
                        float(workout.distance_m)
                        - float(previous.distance_m)
                    )
                    / reference
                    > 0.35
                ):
                    continue

            result.append(previous)

        return result[-20:]

    def _apply_personal_workout_context(
        self,
        workout: Workout,
    ) -> Workout:
        """Compare a completed workout against the user's own history.

        Raw metrics are never overwritten.
        """
        comparable = self._comparable_local_workouts(workout)
        workout.comparable_workout_count = len(comparable)

        if not comparable:
            workout.personal_context_summary = (
                "No sufficiently comparable prior Fitness workouts are "
                "available yet."
            )
            return workout

        def baseline(field_name: str) -> float | None:
            return self._safe_mean(
                [
                    getattr(item, field_name)
                    for item in comparable
                    if getattr(item, field_name) is not None
                ]
            )

        efficiency_baseline = baseline("aerobic_efficiency")
        decoupling_baseline = baseline("aerobic_decoupling_percent")
        hr_baseline = baseline("avg_hr")
        power_baseline = baseline("avg_power")
        speed_baseline = baseline("average_speed_m_s")
        trimp_baseline = baseline("banister_trimp")

        workout.efficiency_vs_baseline_percent = (
            self._percent_difference_from_baseline(
                workout.aerobic_efficiency,
                efficiency_baseline,
            )
        )

        # Lower decoupling is generally preferable for the same type of steady
        # aerobic session, so report current minus personal baseline directly.
        if (
            workout.aerobic_decoupling_percent is not None
            and decoupling_baseline is not None
        ):
            workout.decoupling_vs_baseline_percent = (
                float(workout.aerobic_decoupling_percent)
                - float(decoupling_baseline)
            )

        if workout.avg_hr is not None and hr_baseline is not None:
            workout.avg_hr_vs_baseline_bpm = (
                float(workout.avg_hr) - float(hr_baseline)
            )

        workout.avg_power_vs_baseline_percent = (
            self._percent_difference_from_baseline(
                workout.avg_power,
                power_baseline,
            )
        )

        workout.avg_speed_vs_baseline_percent = (
            self._percent_difference_from_baseline(
                workout.average_speed_m_s,
                speed_baseline,
            )
        )

        workout.trimp_vs_recent_mean_percent = (
            self._percent_difference_from_baseline(
                workout.banister_trimp,
                trimp_baseline,
            )
        )

        # Deterministic descriptive load context, not a medical/safety score.
        if workout.trimp_vs_recent_mean_percent is not None:
            delta = workout.trimp_vs_recent_mean_percent
            if delta >= 35:
                workout.load_context = "much_higher_than_personal_norm"
            elif delta >= 15:
                workout.load_context = "higher_than_personal_norm"
            elif delta <= -35:
                workout.load_context = "much_lower_than_personal_norm"
            elif delta <= -15:
                workout.load_context = "lower_than_personal_norm"
            else:
                workout.load_context = "similar_to_personal_norm"

        parts: list[str] = []

        if workout.efficiency_vs_baseline_percent is not None:
            parts.append(
                "aerobic efficiency "
                f"{workout.efficiency_vs_baseline_percent:+.1f}% "
                "vs comparable-workout baseline"
            )

        if workout.decoupling_vs_baseline_percent is not None:
            parts.append(
                "aerobic decoupling "
                f"{workout.decoupling_vs_baseline_percent:+.1f} percentage "
                "points vs baseline"
            )

        if workout.avg_hr_vs_baseline_bpm is not None:
            parts.append(
                "average HR "
                f"{workout.avg_hr_vs_baseline_bpm:+.1f} bpm vs baseline"
            )

        if workout.avg_power_vs_baseline_percent is not None:
            parts.append(
                "average power "
                f"{workout.avg_power_vs_baseline_percent:+.1f}% vs baseline"
            )
        elif workout.avg_speed_vs_baseline_percent is not None:
            parts.append(
                "average speed "
                f"{workout.avg_speed_vs_baseline_percent:+.1f}% vs baseline"
            )

        if workout.trimp_vs_recent_mean_percent is not None:
            parts.append(
                "TRIMP "
                f"{workout.trimp_vs_recent_mean_percent:+.1f}% vs comparable "
                "recent-workout mean"
            )

        if parts:
            workout.personal_context_summary = (
                f"Compared with {len(comparable)} similar prior workout"
                f"{'s' if len(comparable) != 1 else ''}: "
                + "; ".join(parts)
                + "."
            )
        else:
            workout.personal_context_summary = (
                f"{len(comparable)} comparable prior workouts were found, "
                "but no directly comparable derived metrics were available."
            )

        return workout

    def _finalize_local_workout(self, stop_time: datetime) -> Workout | None:
        if self.session_started is None:
            return None

        duration = (stop_time - self.session_started).total_seconds()
        if duration < MIN_LOCAL_WORKOUT_SECONDS or len(self.samples) < MIN_LOCAL_WORKOUT_SAMPLES:
            return None

        def values(metric):
            return [
                float(sample[metric])
                for sample in self.samples
                if sample.get(metric) is not None
            ]

        hr = values(METRIC_HEART_RATE)
        power = values(METRIC_POWER)
        cadence = values(METRIC_CADENCE)
        distance = values(METRIC_DISTANCE)
        altitude = values(METRIC_ALTITUDE)
        speed = values(METRIC_SPEED)

        # Require actual exercise evidence, not merely an idle connected sensor.
        movement = (
            (speed and max(speed) > 0.5)
            or (power and max(power) > 20)
            or (distance and max(distance) > min(distance))
            or (cadence and max(cadence) > 20)
        )
        if not movement and not hr:
            return None

        elevation_gain = None
        if len(altitude) >= 2:
            elevation_gain = sum(
                max(0.0, b - a) for a, b in zip(altitude, altitude[1:])
            )

        distance_m = None
        if distance:
            # Unit normalization remains conservative. ANT+ integrations often
            # expose meters; if the total is implausibly small while speed shows
            # activity, retain it as provider/raw distance rather than invent.
            distance_m = max(distance) - min(distance)
            if distance_m <= 0:
                distance_m = max(distance)

        evaluation = self.evaluation()
        resting_hr = evaluation.get("resting_hr")
        max_hr = evaluation.get("max_hr")

        trimp = banister_trimp(
            duration / 60.0,
            mean(hr) if hr else None,
            resting_hr,
            max_hr,
            self.config.get(CONF_SEX),
        )
        trimp_per_hour = (
            trimp / (duration / 3600.0)
            if trimp is not None and duration > 0
            else None
        )

        work_kj = mechanical_work_kj(self.samples)
        coupling = aerobic_efficiency_and_decoupling(
            self.samples,
            duration,
        )
        has_hr_intensity_basis = (
            bool(hr)
            and resting_hr is not None
            and max_hr is not None
        )
        intensity_time = (
            time_in_hrr_intensity(
                self.samples,
                resting_hr,
                max_hr,
            )
            if has_hr_intensity_basis
            else {}
        )

        sport = self._infer_sport()
        workout = Workout(
            source="fitness_live_capture",
            name=self._workout_name(self.session_started, sport),
            sport=sport.lower(),
            start=self.session_started.isoformat(),
            end=stop_time.isoformat(),
            duration_s=duration,
            distance_m=distance_m,
            avg_hr=mean(hr) if hr else None,
            max_hr=max(hr) if hr else None,
            avg_power=mean(power) if power else None,
            max_power=max(power) if power else None,
            avg_cadence=mean(cadence) if cadence else None,
            elevation_gain_m=elevation_gain,
            sample_count=len(self.samples),
            banister_trimp=trimp,
            trimp_per_hour=trimp_per_hour,
            mechanical_work_kj=work_kj,
            aerobic_efficiency=coupling.get("efficiency"),
            aerobic_efficiency_kind=coupling.get("efficiency_kind"),
            aerobic_decoupling_percent=coupling.get("decoupling_percent"),
            time_very_light_s=(
                intensity_time.get("very_light")
                if has_hr_intensity_basis else None
            ),
            time_light_s=(
                intensity_time.get("light")
                if has_hr_intensity_basis else None
            ),
            time_moderate_s=(
                intensity_time.get("moderate")
                if has_hr_intensity_basis else None
            ),
            time_vigorous_s=(
                intensity_time.get("vigorous")
                if has_hr_intensity_basis else None
            ),
            time_near_maximal_s=(
                intensity_time.get("near_maximal")
                if has_hr_intensity_basis else None
            ),
        )

        return self._apply_personal_workout_context(workout)

    def local_workouts(self) -> list[Workout]:
        result = []
        for item in self.history:
            try:
                result.append(Workout(**item))
            except TypeError:
                continue
        return result

    def latest_workout(self) -> Workout | None:
        candidates = self.local_workouts() + discover_external_workouts(
            self.hass, self.config
        )
        return newest(candidates)

    @staticmethod
    def _workout_signature(
        workout: Workout | None,
    ):
        """Return a source-independent fingerprint for one real workout.

        Garmin/Strava/local capture may represent the same session using
        different entity IDs and names. A five-minute start-time bucket plus
        normalized sport avoids announcing the same workout again when the
        provider representation changes after a restart/sync.
        """
        if workout is None:
            return None

        sport = (
            str(workout.sport or "workout")
            .strip()
            .lower()
            .replace(" ", "_")
        )

        start = None
        if workout.start:
            try:
                start = datetime.fromisoformat(
                    str(workout.start).replace("Z", "+00:00")
                )
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                start = None

        if start is not None:
            timestamp = int(start.timestamp())
            five_minute_bucket = timestamp // 300
            return f"{sport}|t5:{five_minute_bucket}"

        # Rare fallback for providers with no usable start timestamp.
        duration_bucket = (
            int((workout.duration_s or 0) // 120)
            if workout.duration_s is not None
            else 0
        )
        distance_bucket = (
            int((workout.distance_m or 0) // 500)
            if workout.distance_m is not None
            else 0
        )
        name = (
            str(workout.name or "workout")
            .strip()
            .lower()
            .replace(" ", "_")
        )
        return (
            f"{sport}|name:{name}|"
            f"d2:{duration_bucket}|dist500:{distance_bucket}"
        )

    def live_session_statistics(self) -> dict[str, Any]:
        """Within-session summaries; unavailable outside an active workout."""
        if not self.session_active:
            return {}

        def vals(metric):
            result = []
            for sample in self.samples:
                value = sample.get(metric)
                if value is not None:
                    try:
                        result.append(float(value))
                    except (TypeError, ValueError):
                        pass
            return result

        hr = vals(METRIC_HEART_RATE)
        power = vals(METRIC_POWER)
        cadence = vals(METRIC_CADENCE)
        speed = vals(METRIC_SPEED)
        duration = self.session_duration()
        evaluation = self.evaluation()

        trimp = banister_trimp(
            duration / 60.0,
            mean(hr) if hr else None,
            evaluation.get("resting_hr"),
            evaluation.get("max_hr"),
            self.config.get(CONF_SEX),
        )
        coupling = aerobic_efficiency_and_decoupling(
            self.samples,
            duration,
        )
        resting_hr = evaluation.get("resting_hr")
        max_hr = evaluation.get("max_hr")
        has_hr_intensity_basis = (
            bool(hr)
            and resting_hr is not None
            and max_hr is not None
        )
        intensity_time = (
            time_in_hrr_intensity(
                self.samples,
                resting_hr,
                max_hr,
            )
            if has_hr_intensity_basis
            else {}
        )

        return {
            "average_hr": mean(hr) if hr else None,
            "maximum_hr": max(hr) if hr else None,
            "average_power": mean(power) if power else None,
            "maximum_power": max(power) if power else None,
            "average_cadence": mean(cadence) if cadence else None,
            "average_speed": mean(speed) if speed else None,
            "banister_trimp": trimp,
            "mechanical_work_kj": mechanical_work_kj(self.samples),
            "aerobic_efficiency": coupling.get("efficiency"),
            "aerobic_efficiency_kind": coupling.get("efficiency_kind"),
            "aerobic_decoupling_percent": coupling.get("decoupling_percent"),
            "time_very_light_s": (
                intensity_time.get("very_light")
                if has_hr_intensity_basis else None
            ),
            "time_light_s": (
                intensity_time.get("light")
                if has_hr_intensity_basis else None
            ),
            "time_moderate_s": (
                intensity_time.get("moderate")
                if has_hr_intensity_basis else None
            ),
            "time_vigorous_s": (
                intensity_time.get("vigorous")
                if has_hr_intensity_basis else None
            ),
            "time_near_maximal_s": (
                intensity_time.get("near_maximal")
                if has_hr_intensity_basis else None
            ),
        }

    async def _async_delayed_long_term_refresh(self) -> None:
        await asyncio.sleep(8)
        await self._async_refresh_long_term_statistics()

    @staticmethod
    def _summarize_stat_periods(periods: list[dict[str, Any]]) -> dict[str, Any]:
        values = []
        dated = []
        for row in periods or []:
            value = row.get("mean")
            if value is None:
                value = row.get("state")
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            values.append(number)
            dated.append((row.get("start"), number))

        if not values:
            return {}

        def tail_mean(n: int):
            vals = values[-n:]
            return mean(vals) if vals else None

        recent14 = values[-14:]
        previous14 = values[-28:-14]
        trend_pct = None
        if recent14 and previous14:
            prior = mean(previous14)
            if prior != 0:
                trend_pct = (mean(recent14) - prior) / abs(prior) * 100

        return {
            "days_available": len(values),
            "mean_7d": round(tail_mean(7), 3) if tail_mean(7) is not None else None,
            "mean_28d": round(tail_mean(28), 3) if tail_mean(28) is not None else None,
            "mean_90d": round(tail_mean(90), 3) if tail_mean(90) is not None else None,
            "trend_14_vs_previous_14_percent": (
                round(trend_pct, 2)
                if trend_pct is not None
                else None
            ),
            "latest_daily_mean": round(values[-1], 3),
        }

    async def _async_refresh_long_term_statistics(self) -> None:
        """Cache Recorder long-term statistics for relevant profile sources."""
        if not self.hass.services.has_service(
            "recorder",
            "get_statistics",
        ):
            return

        provider = collect_provider_metrics(
            self.hass,
            self.config,
        )

        entity_to_metric: dict[str, str] = {}

        for key in (
            "vo2max",
            "resting_hr",
            "weight_kg",
            "hrv_weekly",
            "hrv_last_night",
            "fitness_age",
            "threshold_hr",
            "threshold_speed",
            "ftp_running",
            "power_to_weight_running",
            "training_readiness",
            "sleep_score",
        ):
            entity_id = provider.get(f"{key}_entity")
            if isinstance(entity_id, str):
                entity_to_metric[entity_id] = key

        for key in (
            CONF_WEIGHT,
            CONF_RESTING_HR,
            CONF_MAX_HR,
            CONF_VO2MAX,
            "threshold_hr",
            "threshold_pace",
            "threshold_power",
        ):
            raw = self.config.get(key)
            if is_entity_reference(raw):
                entity_to_metric[str(raw).strip()] = key

        if not entity_to_metric:
            return

        start = datetime.now(timezone.utc) - timedelta(days=90)

        try:
            response = await self.hass.services.async_call(
                "recorder",
                "get_statistics",
                {
                    "statistic_ids": sorted(entity_to_metric),
                    "start_time": start.isoformat(),
                    "period": "day",
                    "types": ["mean", "min", "max", "state"],
                },
                blocking=True,
                return_response=True,
            )
        except Exception:
            return

        if not isinstance(response, dict):
            return

        raw_statistics = response.get("statistics")
        if not isinstance(raw_statistics, dict):
            # Some HA service response handlers may directly return the map.
            raw_statistics = response

        result: dict[str, Any] = {}
        for entity_id, metric_key in entity_to_metric.items():
            periods = raw_statistics.get(entity_id)
            if not isinstance(periods, list):
                continue
            summary = self._summarize_stat_periods(periods)
            if summary:
                summary["entity_id"] = entity_id
                result[metric_key] = summary

        if result:
            self.long_term_statistics = result
            self.long_term_statistics_updated = (
                datetime.now(timezone.utc).isoformat()
            )
            await self._save()
            self._notify()

    def workout_long_term_summary(self) -> dict[str, Any]:
        """Event-based trends from actual stored Fitness live workouts."""
        workouts = self.local_workouts()
        now = datetime.now(timezone.utc)

        def parse_start(workout):
            try:
                dt = datetime.fromisoformat(
                    str(workout.start).replace("Z", "+00:00")
                )
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                return None

        recent = []
        for workout in workouts:
            dt = parse_start(workout)
            if dt is None:
                continue
            age_days = (now - dt).total_seconds() / 86400
            if age_days <= 90:
                recent.append((dt, workout))

        recent.sort(key=lambda item: item[0])

        def load(days):
            return sum(
                workout.banister_trimp or 0.0
                for dt, workout in recent
                if (now - dt).total_seconds() <= days * 86400
            )

        def avg_field(field_name, days=90):
            vals = [
                float(getattr(workout, field_name))
                for dt, workout in recent
                if (
                    (now - dt).total_seconds() <= days * 86400
                    and getattr(workout, field_name) is not None
                )
            ]
            return mean(vals) if vals else None

        active_days_28 = len({
            dt.date()
            for dt, _ in recent
            if (now - dt).total_seconds() <= 28 * 86400
        })

        if not recent:
            return {
                "workouts_28d": None,
                "active_training_days_28d": None,
                "banister_trimp_7d": None,
                "banister_trimp_28d": None,
                "banister_trimp_42d": None,
                "hrr_60s_mean_90d": None,
                "aerobic_decoupling_mean_90d": None,
                "aerobic_efficiency_mean_90d": None,
            }

        return {
            "workouts_28d": sum(
                1 for dt, _ in recent
                if (now - dt).total_seconds() <= 28 * 86400
            ),
            "active_training_days_28d": active_days_28,
            "banister_trimp_7d": round(load(7), 1),
            "banister_trimp_28d": round(load(28), 1),
            "banister_trimp_42d": round(load(42), 1),
            "hrr_60s_mean_90d": (
                round(avg_field("hrr_60s"), 1)
                if avg_field("hrr_60s") is not None
                else None
            ),
            "aerobic_decoupling_mean_90d": (
                round(avg_field("aerobic_decoupling_percent"), 2)
                if avg_field("aerobic_decoupling_percent") is not None
                else None
            ),
            "aerobic_efficiency_mean_90d": (
                round(avg_field("aerobic_efficiency"), 5)
                if avg_field("aerobic_efficiency") is not None
                else None
            ),
        }

    def evaluation(self) -> dict:
        provider = collect_provider_metrics(self.hass, self.config)

        weight = provider.get("weight_kg") or self.input_value(CONF_WEIGHT)
        resting = provider.get("resting_hr") or self.input_value(CONF_RESTING_HR)

        manual_max = self.input_value(CONF_MAX_HR)
        max_hr = manual_max or predicted_max_hr_tanaka(self.age())
        max_hr_method = None if manual_max else METHOD_TANAKA_2001

        latest = self.latest_workout()
        if latest and latest.max_hr and latest.max_hr > max_hr:
            max_hr = latest.max_hr
            max_hr_method = "observed_workout_peak"

        vo2 = provider.get("vo2max") or self.input_value(CONF_VO2MAX)
        vo2_method = "provider_or_user"
        if vo2 is None and resting:
            vo2 = uth_vo2max(max_hr, resting)
            vo2_method = METHOD_UTH_2004 if vo2 is not None else None

        predicted = friend_predicted_vo2max(
            self.age(),
            self.config.get(CONF_SEX),
            weight,
        )
        pp = percent_predicted(vo2, predicted)

        hrv_status = hrv_personal_status(
            provider.get("hrv_last_night"),
            provider.get("hrv_baseline_low"),
            provider.get("hrv_baseline_high"),
        )

        threshold_hr = provider.get("threshold_hr") or self.input_value("threshold_hr")
        threshold_power = provider.get("ftp_running") or self.input_value("threshold_power")
        threshold_pace = self.input_value("threshold_pace")
        if threshold_pace is None:
            threshold_pace = threshold_pace_from_speed(provider.get("threshold_speed"))

        p2w = provider.get("power_to_weight_running")
        if p2w is None and threshold_power and weight:
            p2w = threshold_power / weight

        fitness_age = provider.get("fitness_age")
        age_difference = fitness_age - self.age() if fitness_age is not None else None

        acute = provider.get("acute_load")
        chronic = provider.get("chronic_load")
        ratio = provider.get("acute_chronic_ratio")
        if ratio is None and acute is not None and chronic:
            ratio = acute / chronic

        return {
            "age": self.age(),
            "weight": weight,
            "resting_hr": resting,
            "max_hr": max_hr,
            "max_hr_method": max_hr_method,
            "heart_rate_reserve": (
                heart_rate_reserve(max_hr, resting)
                if resting is not None else None
            ),
            "vo2max": vo2,
            "vo2max_method": vo2_method,
            "friend_predicted_vo2max": predicted,
            "vo2max_percent_predicted": pp,
            "cardiorespiratory_status": reference_status(pp),
            "hrv_weekly": provider.get("hrv_weekly"),
            "hrv_last_night": provider.get("hrv_last_night"),
            "hrv_baseline_low": provider.get("hrv_baseline_low"),
            "hrv_baseline_high": provider.get("hrv_baseline_high"),
            "hrv_status": hrv_status,
            "threshold_hr": threshold_hr,
            "threshold_pace": threshold_pace,
            "threshold_power": threshold_power,
            "power_to_weight": p2w,
            "fitness_age": fitness_age,
            "fitness_age_difference": age_difference,
            "training_readiness": provider.get("training_readiness"),
            "sleep_score": provider.get("sleep_score"),
            "acute_load": acute,
            "chronic_load": chronic,
            "acute_chronic_ratio": ratio,
            "provider_training_status": provider.get("provider_training_status"),
            "workout_long_term": self.workout_long_term_summary(),
            "home_assistant_long_term_statistics": self.long_term_statistics,
            "home_assistant_long_term_statistics_updated": (
                self.long_term_statistics_updated
            ),
            "provider_metrics": provider,
        }

    def _ai_language(self) -> str:
        """Return this Fitness profile's configured output language.

        Existing profiles created before the language option was introduced
        fall back to Home Assistant's UI language, then English.
        """
        configured = self.config.get(CONF_LANGUAGE)
        language = str(
            configured
            or getattr(self.hass.config, "language", None)
            or "en"
        ).lower()
        code = language.split("-")[0].split("_")[0]
        return code if code in SUPPORTED_LANGUAGES else "en"

    def _prompt_strings(self) -> dict[str, str]:
        """Localized AI instructions."""
        # AI prompts use English language names for unambiguous model
        # instruction; the profile selector itself shows native names.
        language_names = {
            "en": "English",
            "el": "Greek",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "it": "Italian",
            "pt": "Portuguese",
            "nl": "Dutch",
            "pl": "Polish",
            "ru": "Russian",
            "uk": "Ukrainian",
            "tr": "Turkish",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
        }
        lang = self._ai_language()
        output_language = language_names.get(lang, "English")

        general = (
            "Evaluate the person's overall fitness and recovery from the structured "
            "results below. Return EXACTLY two parts. The first line must be "
            "`VERDICT: <short overall evaluation>`. The verdict must be a brief phrase "
            "such as Excellent, Good, Okay, Needs attention, or Insufficient data, "
            f"translated naturally into {output_language}. Then write exactly ONE "
            "natural paragraph of roughly 100-170 words in the same language. "
            "Do NOT list, quote, or systematically repeat sensor values. Do NOT turn "
            "the paragraph into a sensor summary. Instead explain what the combined "
            "results mean for this person, taking age into account when relevant. "
            "Describe the overall condition, the most meaningful strengths, and at "
            "most one or two realistic areas that could improve when the evidence "
            "supports them. Mention recovery or training balance only when useful. "
            "Prefer personal longitudinal trends and baselines over interpreting a "
            "single day's value when long-term Home Assistant statistics are supplied. "
            "Distinguish training/performance fitness from medical health. "
            "Do not diagnose disease. Do not add a generic medical disclaimer unless "
            "the supplied data genuinely suggests a safety concern. Treat proprietary "
            "provider scores as context, not scientific truth. Do not interpret one "
            "acute/chronic workload ratio as an injury-risk prediction."
        )

        workout = (
            "Evaluate the latest completed workout using the workout data and current "
            "fitness context below. Return EXACTLY two parts. The first line must be "
            "`VERDICT: <short workout evaluation>`, for example Good, Productive, "
            "Easy, Hard, or Insufficient data, translated naturally into "
            f"{output_language}. Then write exactly ONE natural paragraph of roughly "
            "80-150 words in the same language. Do NOT list or repeat the workout "
            "statistics one by one. Use within-workout distribution, TRIMP, recovery, "
            "efficiency/decoupling, comparable-workout personal context, and personal "
            "long-term trends when available rather "
            "than relying only on averages. Explain what kind of session it appears to have "
            "been, whether the effort seems appropriate for the person's current "
            "fitness, what it likely trained, and one useful observation for future "
            "training. Use only supplied data and do not diagnose disease."
        )

        return {
            "language": output_language,
            "general": general,
            "workout": workout,
        }

    @staticmethod
    def _parse_ai_result(
        result: str | None,
    ) -> tuple[str | None, str | None]:
        """Split the AI output into a safe short state and one paragraph."""
        if not result:
            return None, None

        clean = str(result).strip()
        lines = [
            line.strip()
            for line in clean.splitlines()
            if line.strip()
        ]

        verdict = None
        body_lines = lines

        if lines and lines[0].upper().startswith("VERDICT:"):
            verdict = lines[0].split(":", 1)[1].strip()
            body_lines = lines[1:]

        # Force the long part into a single readable paragraph even if a model
        # ignores the no-list instruction.
        body = " ".join(body_lines)
        body = re.sub(r"[*#]+", "", body)
        body = re.sub(r"(^|\s)[-•]\s+", " ", body)
        body = re.sub(r"\s+", " ", body).strip()

        # Never allow old/non-compliant AI output to become a >255-char state.
        if not verdict:
            verdict = "Updated"

        return verdict[:120], body or None

    def _general_ai_prompt(self) -> str:
        evaluation = {
            key: value
            for key, value in self.evaluation().items()
            if key != "provider_metrics" and value is not None
        }
        strings = self._prompt_strings()

        return (
            strings["general"]
            + f"\nOutput language: {strings['language']}."
            + "\n\nStructured evaluation data:\n"
            + json.dumps(
                evaluation,
                ensure_ascii=False,
                default=str,
            )
        )

    def _workout_ai_prompt(self) -> str | None:
        workout = self.latest_workout()
        if not self._workout_has_real_information(workout):
            return None

        evaluation = {
            key: value
            for key, value in self.evaluation().items()
            if key != "provider_metrics" and value is not None
        }
        strings = self._prompt_strings()

        return (
            strings["workout"]
            + f"\nOutput language: {strings['language']}."
            + "\n\nWorkout:\n"
            + json.dumps(
                workout.as_dict(),
                ensure_ascii=False,
                default=str,
            )
            + "\n\nCurrent evaluation context:\n"
            + json.dumps(
                evaluation,
                ensure_ascii=False,
                default=str,
            )
        )

    async def _call_ai(self, prompt: str, task_name: str) -> str | None:
        entity = str(self.config.get(CONF_AI_ENTITY) or "").strip() or None

        # Preferred path: Home Assistant AI Task.
        #
        # ai_task.generate_data does NOT support an action target. A specific
        # AI Task is supplied with entity_id in the action data. If entity_id
        # is omitted Home Assistant uses the preferred/default AI Task entity.
        if self.hass.services.has_service("ai_task", "generate_data"):
            service_data = {
                "task_name": task_name,
                "instructions": prompt,
            }
            if entity and entity.startswith("ai_task."):
                service_data["entity_id"] = entity

            try:
                response = await self.hass.services.async_call(
                    "ai_task",
                    "generate_data",
                    service_data,
                    blocking=True,
                    return_response=True,
                )
                if isinstance(response, dict):
                    data = response.get("data")
                    if isinstance(data, str):
                        return data.strip()
                    if data is not None:
                        return json.dumps(
                            data,
                            ensure_ascii=False,
                            default=str,
                        )
            except Exception:
                pass

        # Optional fallback for users who explicitly point Fitness at a
        # conversation/LLM agent rather than an AI Task entity.
        if entity and entity.startswith("conversation.") and self.hass.services.has_service(
            "conversation", "process"
        ):
            try:
                response = await self.hass.services.async_call(
                    "conversation",
                    "process",
                    {"text": prompt, "agent_id": entity},
                    blocking=True,
                    return_response=True,
                )
                if isinstance(response, dict):
                    speech = (
                        response.get("response", {})
                        .get("speech", {})
                        .get("plain", {})
                        .get("speech")
                    )
                    return speech or None
            except Exception:
                pass

        return None

    async def async_generate_ai(self, *, general: bool, workout: bool):
        if not self.config.get(CONF_AI_ENABLED):
            return
        async with self._ai_lock:
            if workout:
                prompt = self._workout_ai_prompt()
                if prompt:
                    result = await self._call_ai(
                        prompt,
                        f"Fitness workout evaluation {self.config.get(CONF_PROFILE_NAME)}",
                    )
                    if result:
                        verdict, body = self._parse_ai_result(result)
                        self.ai_workout_verdict = verdict
                        self.ai_workout = body
            if general:
                result = await self._call_ai(
                    self._general_ai_prompt(),
                    f"Fitness general evaluation {self.config.get(CONF_PROFILE_NAME)}",
                )
                if result:
                    verdict, body = self._parse_ai_result(result)
                    self.ai_general_verdict = verdict
                    self.ai_general = body

            self.ai_last_generated = datetime.now(timezone.utc).isoformat()
            await self._save()
            self._notify()
