"""Central Fitness profile/session/workout/evaluation manager."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from datetime import datetime, timezone, timedelta
from statistics import mean, median, pstdev
from typing import Callable, Any
from zoneinfo import ZoneInfo

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .explanations import provenance_text
from .live import get_live_runtime
from .const import (
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_FEEDBACK_AREA_IDS,
    CONF_FEEDBACK_LIGHT_IDS,
    CONF_LANGUAGE,
    CONF_NOTIFY_ENTITY_IDS,
    CONF_TTS_ENTITY_ID,
    CONF_TTS_MEDIA_PLAYER_IDS,
    CONF_DATE_OF_BIRTH,
    CONF_DETAILED_STRENGTH_ANALYSIS,
    CONF_WORKOUT_RETENTION_DAYS,
    CONF_BIRTH_DAY,
    CONF_BIRTH_MONTH,
    CONF_BIRTH_YEAR,
    CONF_MAX_HR,
    CONF_PERIODIC_LIVE_ANNOUNCEMENTS,
    CONF_PERIODIC_LIVE_INTERVAL_MINUTES,
    CONF_PROFILE_NAME,
    CONF_SLEEP_DEVICE_IDS,
    CONF_RESTING_HR,
    CONF_SEX,
    CONF_VO2MAX,
    CONF_WEIGHT,
    DOMAIN,
    DEFAULT_WORKOUT_RETENTION_DAYS,
    MAX_WORKOUT_RETENTION_DAYS,
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
    static_congratulation,
    static_periodic_live_message,
    static_session_message,
    static_workout_message,
)
from .providers.devices import (
    all_live_candidate_entity_ids,
    discover_candidates,
    discover_sources,
    source_device_ids,
    source_is_usable,
)
from .providers.entities import (
    is_entity_reference,
    numeric_entity_state,
    resolve_number_or_entity,
)
from .providers.evaluation import collect_provider_metrics, workout_device_entity_ids
from .providers.sleep import SleepRecord, merged_sleeps, newest_sleep
from .history import ingest_recorder, remember, summarize_all, validate_sleep, validate_workout
from .providers.sleep_adapters.registry import (
    discover_sleep_records,
    latest_sleep as discover_latest_sleep,
    sleep_as_android_event_entity_ids,
    sleep_device_entity_ids,
)
from .providers.sleep_adapters.sleep_as_android import record_from_event_history, records_from_event_history
from .strength import analyze_strength
from .providers.workouts import (
    Workout,
    _dt,
    _same_real_workout,
    _sport_key,
    discover_external_workouts,
    merged_workouts,
    newest,
    workout_sport_kind,
)


_LOGGER = logging.getLogger(__name__)

class FitnessManager:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.listeners: list[Callable[[], None]] = []
        self.live_listeners: list[Callable[[], None]] = []
        self.sleep_listeners: list[Callable[[], None]] = []
        self.workout_history_listeners: list[Callable[[], None]] = []
        self._sleep_tracking_started_at: str | None = None
        self._sleep_event_record: SleepRecord | None = None
        self._sleep_history_refresh_task = None
        self._sleep_as_android_active = False
        # Keep the current Sleep as Android event timeline in memory so a
        # completed sleep can be published immediately at STOPPED. Recorder is
        # authoritative for restart/backfill, but its asynchronous write must
        # never delay the just-finished night from reaching Fitness.
        self._sleep_as_android_live_events: dict[str, list[dict[str, Any]]] = {
            "tracking": [],
            "phase": [],
        }
        # Canonical merged nightly records retained for evidence-based sleep
        # trends. These are Fitness facts, not provider-specific duplicates.
        self.sleep_history: list[dict[str, Any]] = []
        self.remove_listeners: list[Callable[[], None]] = []
        self.store = Store(
            hass,
            STORE_VERSION,
            f"{STORE_KEY_PREFIX}.{entry.entry_id}",
        )
        self.history: list[dict] = []
        # User-deleted canonical workouts are retained as compact tombstones so
        # provider/history reconciliation cannot resurrect them on the next sync.
        self.deleted_workouts: list[dict[str, Any]] = []
        # One cutoff is used for bulk user deletion so deleting years of history
        # does not require thousands of per-workout tombstones.
        self.deleted_workouts_before: str | None = None
        self.session_armed = False
        self.session_active = False
        self.session_paused = False
        self.session_started: datetime | None = None
        self._session_pause_started: datetime | None = None
        self._session_paused_seconds = 0.0
        self._session_segment = 0
        self._pause_distance_raw: float | None = None
        self._session_distance_excluded = 0.0
        self.samples: list[dict[str, Any]] = []
        self.capture_control = "idle"
        self.session_rpe: int | None = None

        # Live sensors may update many times per second. Keep the hot path small:
        # cache discovered source mappings, record at most one workout sample per
        # second, and publish live entity updates at most twice per second.
        self._live_sources_cache: dict = {}
        self._live_candidates_cache: dict = {}
        self._live_source_initial_entity: dict[str, str] = {}
        self._live_source_switches: list[dict[str, Any]] = []
        self._last_sample_monotonic: float | None = None
        self._last_live_notify_monotonic: float | None = None

        # HR intensity basis is calculated once when live timing begins instead
        # of running the full provider/workout evaluation on every sensor event.
        self._session_intensity_max_hr: float | None = None
        self._session_intensity_resting_hr: float | None = None

        # Zone optical feedback requires a stable zone for 10 seconds.
        self._candidate_live_intensity: str | None = None
        self._candidate_live_intensity_since: float | None = None

        # Pre-workout states of ANT+ Capture switches. Persisted so a Home
        # Assistant restart cannot make Fitness forget which switches it
        # temporarily enabled for a workout.

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
        self.metric_history: dict[str, list[dict[str, Any]]] = {}
        self.history_validation: dict[str, dict[str, Any]] = {}
        # Evaluation is expensive (provider registry scans + longitudinal
        # summaries). HA reads every Evaluation entity during startup, so doing
        # this independently for each entity can block the event loop for many
        # seconds. Cache one coherent snapshot until source data changes.
        self._evaluation_cache: dict[str, Any] | None = None
        # Startup-critical entity properties must never trigger provider scans or
        # longitudinal calculations.  These caches are populated after HA has
        # reached EVENT_HOMEASSISTANT_STARTED and invalidated on relevant changes.
        self._latest_workout_cache: Workout | None = None
        self._latest_workout_cache_ready = False
        self._readiness_cache: dict[str, Any] | None = None
        self._recovery_time_cache: dict[str, Any] | None = None
        self.post_start_ready = False

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
        self._live_calculation_task: asyncio.Task | None = None
        self._live_session_statistics_cache: dict[str, Any] = {}
        self._live_derived_cache: dict[str, Any] = {}
        self._live_coaching_context_cache: dict[str, Any] = {}
        self._last_live_calculation_at: str | None = None
        self._session_profile_context: dict[str, Any] = {}

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

        # Serialize every TTS announcement for this Fitness profile. Home
        # Assistant's blocking tts.speak only waits for the service call itself,
        # not for audible playback to finish.
        self._tts_playback_lock = asyncio.Lock()

        # Workout lifecycle light cues are serialized separately from the
        # heartbeat/intensity pulses. They reuse the same original-state
        # snapshot only while intensity feedback is suspended.
        self._session_status_light_lock = asyncio.Lock()
        self._light_feedback_serial_lock = asyncio.Lock()
        self._session_status_light_active = False
        self._session_status_light_task: asyncio.Task | None = None
        self._session_waiting_red = False

    @property
    def config(self):
        return {**self.entry.data, **self.entry.options}

    async def async_setup(self):
        """Restore persisted state without doing provider discovery during HA bootstrap."""
        stored = await self.store.async_load() or {}
        self.history = list(stored.get("history") or [])
        self.deleted_workouts = list(stored.get("deleted_workouts") or [])
        self.deleted_workouts_before = stored.get("deleted_workouts_before")
        self.ai_general = stored.get("ai_general")
        self.ai_workout = stored.get("ai_workout")
        self.ai_general_verdict = stored.get("ai_general_verdict")
        self.ai_workout_verdict = stored.get("ai_workout_verdict")
        self.ai_last_generated = stored.get("ai_last_generated")
        self.long_term_statistics = dict(stored.get("long_term_statistics") or {})
        self.long_term_statistics_updated = stored.get("long_term_statistics_updated")
        self.sleep_history = list(stored.get("sleep_history") or [])
        self.metric_history = {
            str(k): list(v)
            for k, v in dict(stored.get("metric_history") or {}).items()
            if isinstance(v, list)
        }
        self.history_validation = dict(stored.get("history_validation") or {})
        self.materialized_sensor_keys = set(stored.get("materialized_sensor_keys") or [])
        self._last_announced_workout_signature = stored.get("last_announced_workout_signature")
        self.selected_feedback_area_id = stored.get("selected_feedback_area_id")

        self._prune_workout_history()

        # Restore only Fitness-owned persisted history here.  Provider/registry
        # discovery is deliberately deferred until Home Assistant has announced
        # that bootstrap is complete.
        if self.sleep_history:
            self._latest_sleep_cache = newest_sleep(self._sleep_records_from_history())
        else:
            self._latest_sleep_cache = None

        self._latest_workout_cache = newest(self.local_workouts())
        self._latest_workout_cache_ready = True

        self._external_workout_announcements_armed = False
        self._external_workout_baseline_pending = True
        self._last_external_signature = self._last_announced_workout_signature or None

        if self.hass.is_running:
            self.hass.async_create_task(self._async_post_start_setup())
        else:
            started_unsub = None

            @callback
            def _home_assistant_started(_event: Event) -> None:
                # async_listen_once removes itself before invoking this callback.
                # Drop our stored unsubscriber now so async_shutdown never tries
                # to remove the already-consumed HA job a second time.
                nonlocal started_unsub
                if started_unsub is not None:
                    try:
                        self.remove_listeners.remove(started_unsub)
                    except ValueError:
                        pass
                    started_unsub = None
                self.hass.async_create_background_task(
                    self._async_post_start_setup(),
                    "fitness post-start setup",
                )

            started_unsub = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED,
                _home_assistant_started,
            )
            self.remove_listeners.append(started_unsub)

    async def _async_post_start_setup(self) -> None:
        """Initialize provider mappings only after HA bootstrap has completed."""
        # Give HA one event-loop turn after the started event before registry work.
        await asyncio.sleep(0)

        valid_area_ids = {area_id for area_id, _name in self.available_feedback_areas()}
        if self.selected_feedback_area_id and self.selected_feedback_area_id not in valid_area_ids:
            self.selected_feedback_area_id = None
        if not self.selected_feedback_area_id:
            configured_areas = [
                area_id
                for area_id in list(self.config.get(CONF_FEEDBACK_AREA_IDS) or [])
                if area_id in valid_area_ids
            ]
            self.selected_feedback_area_id = configured_areas[0] if configured_areas else None

        await asyncio.sleep(0)
        live_ids = set(all_live_candidate_entity_ids(self.hass, self.config))
        workout_ids = set(workout_device_entity_ids(self.hass, self.config))
        sleep_ids = set(sleep_device_entity_ids(self.hass, self.config))
        profile_ids: set[str] = set()
        for key in (CONF_WEIGHT, CONF_RESTING_HR, CONF_MAX_HR, CONF_VO2MAX):
            raw = self.config.get(key)
            if is_entity_reference(raw):
                profile_ids.add(str(raw).strip())

        await asyncio.sleep(0)
        self._latest_sleep_cache = discover_latest_sleep(self.hass, self.config) or self._latest_sleep_cache
        if self._latest_sleep_cache is not None:
            self._remember_sleep_record(self._latest_sleep_cache, persist=False)

        self._live_candidates_cache = discover_candidates(self.hass, self.config)
        self._live_sources_cache = {
            metric: items[0]
            for metric, items in self._live_candidates_cache.items()
            if items
        }
        self._live_source_initial_entity = {
            metric: source.entity_id
            for metric, source in self._live_sources_cache.items()
        }

        if live_ids:
            self.remove_listeners.append(
                async_track_state_change_event(
                    self.hass, sorted(live_ids), self._async_live_source_change
                )
            )
        if workout_ids:
            self.remove_listeners.append(
                async_track_state_change_event(
                    self.hass, sorted(workout_ids), self._async_workout_source_change
                )
            )
        if sleep_ids:
            self.remove_listeners.append(
                async_track_state_change_event(
                    self.hass, sorted(sleep_ids), self._async_sleep_source_change
                )
            )
        profile_only_ids = profile_ids - live_ids - workout_ids - sleep_ids
        if profile_only_ids:
            self.remove_listeners.append(
                async_track_state_change_event(
                    self.hass, sorted(profile_only_ids), self._async_profile_source_change
                )
            )

        # Refresh the canonical completed-workout cache once after providers have
        # restored. Entity state reads from now on are cache-only.
        self._latest_workout_cache_ready = False
        self.latest_workout()

        self.hass.async_create_task(self._async_arm_external_workout_announcements())
        self.hass.async_create_task(self._async_delayed_long_term_refresh())
        self._schedule_sleep_as_android_history_refresh(delay=5.0, retries=0)
        if self.config.get(CONF_AI_ENABLED) and not self.ai_general:
            self.hass.async_create_task(self.async_generate_ai(general=True, workout=False))

        self.post_start_ready = True
        self._invalidate_evaluation_cache()
        self._notify()
        self._notify_sleep()
        self._notify_workout_history()

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

        if (
            self._live_calculation_task
            and not self._live_calculation_task.done()
        ):
            self._live_calculation_task.cancel()

        if self._recovery_task and not self._recovery_task.done():
            self._recovery_task.cancel()
        if self._sleep_history_refresh_task and not self._sleep_history_refresh_task.done():
            self._sleep_history_refresh_task.cancel()

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

    def add_live_listener(self, listener):
        """Register a listener for high-frequency live entity updates only."""
        self.live_listeners.append(listener)
        return lambda: self.live_listeners.remove(listener)

    def add_sleep_listener(self, listener):
        self.sleep_listeners.append(listener)
        return lambda: self.sleep_listeners.remove(listener)

    def add_workout_history_listener(self, listener):
        """Register a listener for canonical workout-history changes only."""
        self.workout_history_listeners.append(listener)
        return lambda: self.workout_history_listeners.remove(listener)

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

    def forget_materialized_sensor(
        self,
        key: str,
        *,
        persist: bool = True,
    ) -> bool:
        """Forget an optional sensor that no longer represents usable data."""
        if key not in self.materialized_sensor_keys:
            return False
        self.materialized_sensor_keys.discard(key)
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

    def _invalidate_evaluation_cache(self) -> None:
        self._evaluation_cache = None
        self._readiness_cache = None
        self._recovery_time_cache = None

    def _notify(self):
        self._invalidate_evaluation_cache()
        """Notify all entity listeners without one broken entity blocking others."""
        for listener in list(self.listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001 - entity listeners must be isolated
                _LOGGER.exception(
                    "Fitness entity listener failed; continuing remaining updates"
                )

    def _notify_live(self):
        """Notify only live Fitness entities."""
        for listener in list(self.live_listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001 - entity listeners must be isolated
                _LOGGER.exception(
                    "Fitness live entity listener failed; continuing remaining updates"
                )

    def _notify_sleep(self):
        self._invalidate_evaluation_cache()
        for listener in list(self.sleep_listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Fitness sleep entity listener failed")

    def _notify_workout_history(self):
        self._latest_workout_cache_ready = False
        self._invalidate_evaluation_cache()
        """Notify only entities that render canonical workout history."""
        for listener in list(self.workout_history_listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Fitness workout-history listener failed")

    def _sleep_records_from_history(self) -> list[SleepRecord]:
        records: list[SleepRecord] = []
        valid_fields = set(SleepRecord.__dataclass_fields__)
        for item in self.sleep_history:
            if not isinstance(item, dict):
                continue
            payload = {key: value for key, value in item.items() if key in valid_fields}
            try:
                records.append(SleepRecord(**payload))
            except (TypeError, ValueError):
                continue
        return records

    def _remember_sleep_record(
        self,
        record: SleepRecord | None,
        *,
        persist: bool = True,
    ) -> bool:
        """Merge one canonical sleep into bounded longitudinal history."""
        if record is None or not (record.start or record.end or record.duration_s):
            return False

        before = json.dumps(self.sleep_history, sort_keys=True, default=str)
        records = self._sleep_records_from_history()
        records.append(record)
        merged = merged_sleeps(records)
        merged.sort(
            key=lambda item: _dt(item.end or item.start)
            or datetime.min.replace(tzinfo=timezone.utc)
        )
        # Keep enough history for 90-day trends plus modest gaps.
        self.sleep_history = [item.as_dict() for item in merged[-120:]]
        after = json.dumps(self.sleep_history, sort_keys=True, default=str)
        changed = before != after
        if changed and persist:
            self.hass.async_create_task(self._save())
        return changed

    def latest_sleep(self):
        return getattr(self, "_latest_sleep_cache", None)

    def _schedule_sleep_as_android_history_refresh(
        self, *, delay: float = 1.5, retries: int = 3
    ) -> None:
        """Debounce Recorder reconstruction and tolerate delayed Recorder writes."""
        if not sleep_as_android_event_entity_ids(self.hass, self.config):
            return
        if self._sleep_history_refresh_task and not self._sleep_history_refresh_task.done():
            self._sleep_history_refresh_task.cancel()
        self._sleep_history_refresh_task = self.hass.async_create_task(
            self._async_refresh_sleep_as_android_history(delay=delay, retries=retries)
        )

    async def _async_refresh_sleep_as_android_history(
        self, *, delay: float = 0.0, retries: int = 3
    ) -> None:
        ids = sleep_as_android_event_entity_ids(self.hass, self.config)
        tracking = ids.get("tracking")
        phase = ids.get("phase")
        if not tracking:
            return
        entity_ids = [tracking] + ([phase] if phase else [])
        reconstructed = []
        # Recorder commits state/event changes asynchronously. A STOPPED event
        # can therefore reach the state listener before Recorder history sees
        # it. Retry a few times instead of silently losing the finished night.
        retry_delays = [delay] + [2.0, 5.0, 10.0][:max(0, retries)]
        for wait in retry_delays:
            if wait:
                await asyncio.sleep(wait)
            try:
                from functools import partial
                from homeassistant.components.recorder import get_instance
                from homeassistant.components.recorder.history import get_significant_states
                history = await get_instance(self.hass).async_add_executor_job(
                    partial(
                        get_significant_states,
                        self.hass,
                        datetime.now(timezone.utc) - timedelta(days=8),
                        entity_ids=entity_ids,
                        include_start_time_state=False,
                        significant_changes_only=False,
                        minimal_response=False,
                        no_attributes=False,
                    )
                )
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.debug("Sleep as Android Recorder reconstruction unavailable: %s", err)
                return
            reconstructed = records_from_event_history(
                tracking_entity_id=tracking,
                phase_entity_id=phase,
                tracking_states=list(history.get(tracking) or []),
                phase_states=list(history.get(phase) or []) if phase else [],
            ) if isinstance(history, dict) else []
            if reconstructed:
                break
        if not reconstructed:
            _LOGGER.debug(
                "Sleep as Android Recorder history still has no completed session after retries"
            )
            return
        self._sleep_event_record = reconstructed[-1]
        changed = False
        # Persist every completed night in the Recorder window, not merely the
        # latest one. This makes 7-day sleep metrics genuinely longitudinal.
        for record in reconstructed:
            changed = self._remember_sleep_record(record, persist=False) or changed
        records = discover_sleep_records(self.hass, self.config)
        records.extend(reconstructed)
        self._latest_sleep_cache = newest_sleep(records)
        changed = self._remember_sleep_record(self._latest_sleep_cache, persist=False) or changed
        if changed:
            self.hass.async_create_task(self._save())
        self._notify_sleep()
        self._notify()

    @callback
    def _async_sleep_source_change(self, event: Event):
        """Ignore an active SAA night; publish it only after tracking stops."""
        entity_id = str(event.data.get("entity_id") or "")
        new_state = event.data.get("new_state")
        ids = sleep_as_android_event_entity_ids(self.hass, self.config)
        tracking_entity = ids.get("tracking")
        phase_entity = ids.get("phase")

        if new_state is not None and entity_id in {tracking_entity, phase_entity}:
            event_type = str(new_state.attributes.get("event_type") or "").lower()
            kind = "tracking" if entity_id == tracking_entity else "phase"
            snapshot = {
                "attributes": dict(new_state.attributes),
                "last_updated": getattr(new_state, "last_updated", None),
                "last_changed": getattr(new_state, "last_changed", None),
            }

            if entity_id == tracking_entity and event_type == "started":
                self._sleep_as_android_active = True
                self._sleep_as_android_live_events = {"tracking": [], "phase": []}
                self._sleep_as_android_live_events["tracking"].append(snapshot)
                return

            if self._sleep_as_android_active:
                self._sleep_as_android_live_events[kind].append(snapshot)
                if entity_id == tracking_entity and event_type == "stopped":
                    self._sleep_as_android_active = False
                    # Publish immediately from the live event timeline. This is
                    # independent of Recorder commit latency and therefore makes
                    # Sleep as Android the latest Fitness sleep as soon as STOPPED
                    # arrives. Recorder then backfills/persists the same session.
                    immediate = record_from_event_history(
                        tracking_entity_id=tracking_entity,
                        phase_entity_id=phase_entity,
                        tracking_states=list(self._sleep_as_android_live_events["tracking"]),
                        phase_states=list(self._sleep_as_android_live_events["phase"]),
                    )
                    if immediate is not None:
                        self._sleep_event_record = immediate
                        records = discover_sleep_records(self.hass, self.config)
                        records.append(immediate)
                        self._latest_sleep_cache = newest_sleep(records)
                        changed = self._remember_sleep_record(self._latest_sleep_cache)
                        self._notify_sleep()
                        if changed:
                            self._notify()
                    # Recorder writes asynchronously; retry until the final
                    # STOPPED/phase transitions become visible there.
                    self._schedule_sleep_as_android_history_refresh(delay=1.5, retries=3)
                # paused/resumed and every phase transition remain silent while
                # the sleep is active: no partial night is published.
                return

            if entity_id == tracking_entity and event_type == "stopped":
                # HA may have restarted during the sleep, so the in-memory START
                # can be missing. Recorder reconstruction is the recovery path.
                self._schedule_sleep_as_android_history_refresh(delay=1.5, retries=3)
                return
            # SAA phase events outside a tracked active sleep are not published.
            return

        records = discover_sleep_records(self.hass, self.config)
        if self._sleep_event_record is not None:
            records.append(self._sleep_event_record)
        self._latest_sleep_cache = newest_sleep(records)
        changed = self._remember_sleep_record(self._latest_sleep_cache)
        self._notify_sleep()
        if changed:
            self._notify()

    async def _save(self):
        self._prune_workout_history()
        await self.store.async_save(
            {
                "history": self.history,
                "deleted_workouts": self.deleted_workouts[-1000:],
                "deleted_workouts_before": self.deleted_workouts_before,
                "ai_general": self.ai_general,
                "ai_workout": self.ai_workout,
                "ai_general_verdict": self.ai_general_verdict,
                "ai_workout_verdict": self.ai_workout_verdict,
                "ai_last_generated": self.ai_last_generated,
                "long_term_statistics": self.long_term_statistics,
                "long_term_statistics_updated": self.long_term_statistics_updated,
                "metric_history": self.metric_history,
                "history_validation": self.history_validation,
                "sleep_history": self.sleep_history[-120:],
                "materialized_sensor_keys": sorted(
                    self.materialized_sensor_keys
                ),
                "last_announced_workout_signature": (
                    self._last_announced_workout_signature
                ),
                "selected_feedback_area_id": (
                    self.selected_feedback_area_id
                ),
            }
        )

    def _notify_live_throttled(self) -> None:
        """Publish live entity changes at most twice per second."""
        now = asyncio.get_running_loop().time()
        if (
            self._last_live_notify_monotonic is not None
            and now - self._last_live_notify_monotonic < 0.5
        ):
            return
        self._last_live_notify_monotonic = now
        self._notify_live()

    @callback
    def _async_live_source_change(self, event: Event):
        """Minimal hot path for high-frequency live workout sensor updates."""
        # Completely ignore high-frequency live sensor traffic while Fitness is
        # idle. No Fitness entities need to be republished until a workout is
        # armed or active.
        if not self.session_armed and not self.session_active:
            return

        if self.session_armed and not self.session_active:
            if self._has_valid_live_workout_data():
                self._begin_session_from_live_data()

        if self.session_active and not self.session_paused:
            self._capture_sample()
            self._check_live_intensity_feedback()

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

        # Raw live sensors deliberately keep publishing while paused. Fitness
        # simply stops consuming those values for workout calculations.
        self._notify_live_throttled()

    @callback
    def _async_workout_source_change(self, event: Event):
        """Schedule completed-workout discovery after a relevant provider update."""
        self._latest_workout_cache_ready = False
        self._schedule_external_workout_recheck()

    @callback
    def _async_profile_source_change(self, event: Event):
        """Refresh profile-derived entities without scanning workout providers."""
        self._notify()

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

        # Build canonical history before establishing the announcement baseline.
        # Current provider history, provider-specific historical APIs and HA
        # Recorder snapshots all pass through the same workout merger.
        await self._async_reconcile_external_workouts()
        await self.async_import_provider_workout_history()
        await self.async_import_workouts_from_ha_history()

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
        """Return the optical HRR zone used only for light feedback.

        The six-color optical scale intentionally stays separate from the
        scientific ACSM intensity entity: under Zone 1 is purple, then
        Zones 1-5 are blue/green/yellow/orange/red.
        """
        live = self.live_values()
        hrr = percent_hrr(
            live.get(METRIC_HEART_RATE),
            self._session_intensity_max_hr,
            self._session_intensity_resting_hr,
        )
        if hrr is None:
            return None
        try:
            value = float(hrr)
        except (TypeError, ValueError):
            return None
        if value < 30:
            return "under_zone_1"
        if value < 40:
            return "zone_1"
        if value < 60:
            return "zone_2"
        if value < 75:
            return "zone_3"
        if value < 90:
            return "zone_4"
        return "zone_5"

    def _check_live_intensity_feedback(self):
        """Give optical zone feedback only after 10 stable seconds."""
        if self._session_status_light_active:
            return

        intensity = self._current_live_intensity()
        if intensity is None:
            self._candidate_live_intensity = None
            self._candidate_live_intensity_since = None
            return

        loop_now = asyncio.get_running_loop().time()

        if intensity != self._candidate_live_intensity:
            self._candidate_live_intensity = intensity
            self._candidate_live_intensity_since = loop_now
            return

        if self._candidate_live_intensity_since is None:
            self._candidate_live_intensity_since = loop_now
            return

        if loop_now - self._candidate_live_intensity_since < 10.0:
            return

        if intensity == self._last_live_intensity:
            return

        self._last_live_intensity = intensity
        self._last_live_intensity_accepted_at = datetime.now(
            timezone.utc
        )

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
        self._feedback_generation += 1

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
        async with self._light_feedback_serial_lock:
            async with self._session_status_light_lock:
                light_ids = self._feedback_light_ids()
                if not light_ids:
                    self._session_status_light_active = False
                    self._session_waiting_red = False
                    return
                snapshot_ok = await self._async_prepare_session_status_lights(light_ids)
                if not snapshot_ok:
                    self._session_status_light_active = False
                    self._session_waiting_red = False
                    return
                async with self._feedback_lock:
                    await self._async_set_feedback_color(light_ids, self._session_status_intensity("red"))
                # Keep the original snapshot alive. Green-on-live will restore it.
                self._session_waiting_red = True
                self.last_feedback_light_result = "waiting_for_live_data_red"
                self._notify()

    async def _async_session_status_cue(
        self, status: str, *, seconds: float = 3.0,
        finish_waiting: bool = False, resume_intensity: bool = False,
    ) -> None:
        """Show one serialized lifecycle color and always restore lights."""
        async with self._light_feedback_serial_lock:
            async with self._session_status_light_lock:
                light_ids = self._feedback_light_ids()
                if not light_ids:
                    self._session_status_light_active = False
                    self._session_waiting_red = False
                    return
                preserve = bool(finish_waiting and self._session_waiting_red and self._feedback_scene_active)
                snapshot_ok = await self._async_prepare_session_status_lights(light_ids, preserve_existing_snapshot=preserve)
                if not snapshot_ok:
                    self._session_status_light_active = False
                    self._session_waiting_red = False
                    return
                mapped = self._session_status_intensity(status)
                if mapped is None:
                    self._session_status_light_active = False
                    return
                try:
                    async with self._feedback_lock:
                        await self._async_set_feedback_color(light_ids, mapped)
                    self.last_feedback_light_result = f"session_status_{status}"
                    self._notify()
                    await asyncio.sleep(max(0.0, float(seconds)))
                finally:
                    async with self._feedback_lock:
                        await self._async_restore_feedback_lights(clear_snapshot=True)
                    self._session_waiting_red = False
                    self._session_status_light_active = False
                    self._notify()
                    if resume_intensity and self.session_active:
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
            "intensity_zone_stability_seconds": 10,
            "live_sample_max_hz": 1,
            "live_entity_publish_max_hz": 2,
            "live_derived_calculation_interval_seconds": 30,
            "last_live_calculation_at": self._last_live_calculation_at,
            "live_sources": {
                metric: self.live_source_info(metric)
                for metric in (
                    METRIC_HEART_RATE,
                    METRIC_POWER,
                    METRIC_CADENCE,
                    METRIC_SPEED,
                    METRIC_DISTANCE,
                    METRIC_ALTITUDE,
                )
            },
            "live_source_switches": list(self._live_source_switches),
            "last_feedback_bpm": self.last_feedback_bpm,
            "last_feedback_pulse_interval_seconds": (
                self.last_feedback_pulse_interval
            ),
            "last_feedback_pulse_count": self.last_feedback_pulse_count,
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
                "rgbw_color": attrs.get("rgbw_color"),
                "rgbww_color": attrs.get("rgbww_color"),
                "hs_color": attrs.get("hs_color"),
                "xy_color": attrs.get("xy_color"),
                "color_temp_kelvin": attrs.get("color_temp_kelvin"),
                "color_temp": attrs.get("color_temp"),
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
                        {"transition": 0},
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
                if color_mode == "rgb":
                    rgb = saved.get("rgb_color")
                    if rgb is not None:
                        service_data["rgb_color"] = list(rgb)
                elif color_mode == "rgbw":
                    rgbw = saved.get("rgbw_color")
                    if rgbw is not None:
                        service_data["rgbw_color"] = list(rgbw)
                    elif saved.get("rgb_color") is not None:
                        service_data["rgb_color"] = list(saved["rgb_color"])
                elif color_mode == "rgbww":
                    rgbww = saved.get("rgbww_color")
                    if rgbww is not None:
                        service_data["rgbww_color"] = list(rgbww)
                    elif saved.get("rgb_color") is not None:
                        service_data["rgb_color"] = list(saved["rgb_color"])
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
                    mired = saved.get("color_temp")
                    if kelvin is not None:
                        service_data["color_temp_kelvin"] = kelvin
                    elif mired is not None:
                        service_data["color_temp"] = mired

                effect = saved.get("effect")
                if effect not in (None, "none", "None"):
                    service_data["effect"] = effect

                service_data["transition"] = 0
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
                        "transition": 0,
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
        """Show one serialized 3 s zone colour and always restore lights."""
        async with self._light_feedback_serial_lock:
            self._feedback_generation += 1
            light_ids = self._feedback_light_ids()
            current_hr = self.live_values().get(METRIC_HEART_RATE)
            try: bpm = int(round(float(current_hr))) if current_hr is not None else None
            except (TypeError, ValueError): bpm = None
            self.last_feedback_intensity = intensity
            self.last_feedback_time = datetime.now(timezone.utc).isoformat()
            self.last_feedback_bpm = bpm
            self.last_feedback_pulse_interval = 3.0
            self.last_feedback_pulse_count = 1
            snapshot_ok = False
            if not light_ids: self.last_feedback_light_result = "no_usable_lights"
            async with self._feedback_lock:
                if self._feedback_scene_active:
                    snapshot_ok = bool(self._feedback_light_snapshot)
                else:
                    snapshot_ok = await self._async_snapshot_feedback_lights(light_ids)
            self._notify()
            try:
                if light_ids and snapshot_ok:
                    async with self._feedback_lock:
                        await self._async_set_feedback_color(light_ids, intensity)
                    await asyncio.sleep(3.0)
            finally:
                if snapshot_ok:
                    async with self._feedback_lock:
                        await self._async_restore_feedback_lights(clear_snapshot=True)
                self._notify()

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
        """Generate only start/ready/stop lifecycle guidance."""
        if event not in {
            "waiting_live",
            "started_with_live",
            "live_available",
            "stopped_without_live",
            "paused",
            "resumed",
            "recovery_wait",
            "recovery_checkpoint",
            "recovery_complete",
            "rpe_reminder",
            "no_recovery",
        }:
            return None

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
                "naturally, say the workout timer has started, and finish with one "
                "short original motivational line."
            ),
            "live_available": (
                "Say that live data is now available, name the supplied sensors, "
                "say the workout timer has started, tell the user they can begin, "
                "and finish with one short original motivational line."
            ),
            "stopped_without_live": (
                "Say the workout was stopped before live sensor data arrived and "
                "therefore no live workout was recorded."
            ),
            "paused": (
                "Say the workout is paused and that paused time and movement "
                "are excluded."
            ),
            "resumed": (
                "Say the workout resumed, timing and calculations are active "
                "again, and finish with one short encouraging motivational line."
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
                "Say the post-exercise heart-rate recovery test is complete and all "
                "available recovery data has been saved. Do not ask for RPE in this "
                "sentence because a separate RPE reminder follows when needed."
            ),
            "rpe_reminder": (
                "Tell the user the recovery test is done when this follows recovery, "
                "then ask how hard the completed exercise felt and request one whole "
                "RPE number from 1 to 10 using the Fitness RPE control. Keep it friendly."
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
            f"MANDATORY OUTPUT LANGUAGE: {self._prompt_strings()['language']}. "
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

    def _compute_live_calculation_snapshot(self) -> None:
        """Refresh all derived live calculations from the canonical samples."""
        if not self.session_active or self.session_paused:
            self._live_session_statistics_cache = {}
            self._live_derived_cache = {}
            self._live_coaching_context_cache = {}
            return
        live=self.live_values(); ctx=self._session_profile_context
        def vals(metric):
            out=[]
            for sample in self.samples:
                value=sample.get(metric)
                if value is not None:
                    try: out.append(float(value))
                    except (TypeError,ValueError): pass
            return out
        hr=vals(METRIC_HEART_RATE); power=vals(METRIC_POWER); cadence=vals(METRIC_CADENCE); speed=vals(METRIC_SPEED)
        duration=self.session_duration(); resting=ctx.get('resting_hr'); max_hr=ctx.get('max_hr')
        trimp=banister_trimp(duration/60.0,mean(hr) if hr else None,resting,max_hr,self.config.get(CONF_SEX))
        coupling=aerobic_efficiency_and_decoupling(self.samples,duration)
        has_basis=bool(hr) and resting is not None and max_hr is not None
        intensity_time=time_in_hrr_intensity(self.samples,resting,max_hr) if has_basis else {}
        self._live_session_statistics_cache={
            'average_hr':mean(hr) if hr else None,'maximum_hr':max(hr) if hr else None,
            'average_power':mean(power) if power else None,'maximum_power':max(power) if power else None,
            'average_cadence':mean(cadence) if cadence else None,'average_speed':mean(speed) if speed else None,
            'banister_trimp':trimp,'mechanical_work_kj':mechanical_work_kj(self.samples),
            'aerobic_efficiency':coupling.get('efficiency'),'aerobic_efficiency_kind':coupling.get('efficiency_kind'),
            'aerobic_decoupling_percent':coupling.get('decoupling_percent'),
            'time_very_light_s':intensity_time.get('very_light') if has_basis else None,
            'time_light_s':intensity_time.get('light') if has_basis else None,
            'time_moderate_s':intensity_time.get('moderate') if has_basis else None,
            'time_vigorous_s':intensity_time.get('vigorous') if has_basis else None,
            'time_near_maximal_s':intensity_time.get('near_maximal') if has_basis else None,
        }
        heart_rate=live.get(METRIC_HEART_RATE); current_power=live.get(METRIC_POWER); current_speed=live.get(METRIC_SPEED)
        pace=pace_from_speed_kmh(current_speed); threshold_hr=ctx.get('threshold_hr'); threshold_power=ctx.get('threshold_power'); threshold_pace=ctx.get('threshold_pace'); weight=ctx.get('weight')
        hrmax_pct=percent_max_hr(heart_rate,max_hr); hrr_pct=percent_hrr(heart_rate,max_hr,resting)
        hr_thr=relative_percent(heart_rate,threshold_hr); power_thr=relative_percent(current_power,threshold_power)
        threshold_speed=speed_from_pace_min_km(threshold_pace); speed_thr=relative_percent(current_speed,threshold_speed)
        p2w=current_power/weight if current_power is not None and weight else None
        self._live_derived_cache={'heart_rate_percent_max':hrmax_pct,'heart_rate_reserve_percent':hrr_pct,'heart_rate_intensity':acsm_hrr_intensity(hrr_pct),'heart_rate_relative_threshold':hr_thr,'current_power_to_weight':p2w,'power_relative_threshold':power_thr,'current_pace':pace,'speed_relative_threshold':speed_thr}
        inferred_sport = self._infer_sport().lower()
        activity_kind = (
            'running' if inferred_sport == 'run'
            else 'cycling' if inferred_sport == 'ride'
            else 'exercise'
        )
        self._live_coaching_context_cache={
            'session_duration_minutes':round(duration/60.0,1),'activity_kind':activity_kind,'heart_rate_bpm':round(heart_rate) if heart_rate is not None else None,
            'heart_rate_percent_max':round(hrmax_pct,1) if hrmax_pct is not None else None,'heart_rate_reserve_percent':round(hrr_pct,1) if hrr_pct is not None else None,
            'heart_rate_intensity':acsm_hrr_intensity(hrr_pct),'heart_rate_relative_threshold_percent':round(hr_thr,1) if hr_thr is not None else None,
            'power_w':round(current_power) if current_power is not None else None,'power_to_weight_w_kg':round(p2w,2) if p2w is not None else None,
            'power_relative_threshold_percent':round(power_thr,1) if power_thr is not None else None,
            'cadence_per_min':round(live.get(METRIC_CADENCE)) if live.get(METRIC_CADENCE) is not None else None,
            'speed_kmh':round(current_speed,2) if current_speed is not None else None,'pace_min_km':round(pace,2) if pace is not None else None,
            'distance_km':round(live.get(METRIC_DISTANCE),3) if live.get(METRIC_DISTANCE) is not None else None,
            'altitude_m':round(live.get(METRIC_ALTITUDE),1) if live.get(METRIC_ALTITUDE) is not None else None,
            'available_live_metrics':{
                key:value for key,value in {
                    'heart_rate_bpm':round(heart_rate) if heart_rate is not None else None,
                    'power_w':round(current_power) if current_power is not None else None,
                    'cadence_per_min':round(live.get(METRIC_CADENCE)) if live.get(METRIC_CADENCE) is not None else None,
                    'speed_kmh':round(current_speed,2) if current_speed is not None else None,
                    'distance_km':round(live.get(METRIC_DISTANCE),3) if live.get(METRIC_DISTANCE) is not None else None,
                    'altitude_m':round(live.get(METRIC_ALTITUDE),1) if live.get(METRIC_ALTITUDE) is not None else None,
                }.items()
                if value is not None
            },
            'speed_relative_threshold_percent':round(speed_thr,1) if speed_thr is not None else None,
            'heart_rate_trend':self._recent_live_trend(METRIC_HEART_RATE),'power_trend':self._recent_live_trend(METRIC_POWER),
            'cadence_trend':self._recent_live_trend(METRIC_CADENCE),'speed_trend':self._recent_live_trend(METRIC_SPEED),
        }
        self._last_live_calculation_at=datetime.now(timezone.utc).isoformat()

    async def _async_live_calculation_loop(self) -> None:
        """Recompute derived live state only every 30 seconds."""
        try:
            while self.session_active:
                await asyncio.sleep(30.0)
                if not self.session_active:
                    break
                if self.session_paused:
                    continue
                self._compute_live_calculation_snapshot()
                self._notify()
        except asyncio.CancelledError:
            return

    def live_derived_values(self) -> dict[str, Any]:
        return (
            self._live_derived_cache
            if self.session_active and not self.session_paused
            else {}
        )

    def live_coaching_context(self) -> dict:
        """Return cached 30-second coaching context."""
        return (
            dict(self._live_coaching_context_cache)
            if self.session_active and not self.session_paused
            else {}
        )

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
                f"MANDATORY OUTPUT LANGUAGE: {strings['language']}. "
                "Always state elapsed workout time. Always state the actual current "
                "heart rate when available and the actual current speed when available. "
                "Then use the most useful available calculated Fitness values (for "
                "example %HRR/intensity, threshold-relative HR/power/speed, power-to-"
                "weight, pace, or recent trend) to interpret the effort. Use every "
                "primary live value from available_live_metrics as context but keep "
                "the spoken result concise. "
                "Call the activity running only when activity_kind is running, cycling "
                "only when activity_kind is cycling; otherwise call it a workout or "
                "exercise and do not guess a sport. Prioritize individualized relative "
                "intensity: %HRR, heart rate "
                "versus threshold, power versus threshold, current power-to-weight, "
                "and pace/speed versus threshold when available. Use recent trends "
                "to notice useful patterns such as heart rate rising while power is "
                "stable, or power increasing while heart rate remains stable. "
                "Do not claim cardiac drift from a short trend alone. Keep exact live "
                "values truthful and never substitute averages for current values. "
                "Use simple athlete-friendly language to say whether the effort looks "
                "easy, steady, near threshold, above threshold, or changing only when "
                "the supplied relative data supports that interpretation. Give one "
                "short actionable coaching cue and finish with one original "
                "motivational quote or motivational sentence. Do not diagnose disease, "
                "do not "
                "invent zones, and do not treat FTP, critical power and lactate-"
                "threshold power as interchangeable. Keep it about 35-65 spoken words, "
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


    def _static_periodic_extra_message(self, context: dict) -> str:
        """Localized extra primary live data for deterministic periodic TTS."""
        labels = {
            "en": ("Time", "Speed", "Distance", "Altitude"),
            "el": ("Χρόνος", "Ταχύτητα", "Απόσταση", "Υψόμετρο"),
            "de": ("Zeit", "Geschwindigkeit", "Distanz", "Höhe"),
            "fr": ("Temps", "Vitesse", "Distance", "Altitude"),
            "es": ("Tiempo", "Velocidad", "Distancia", "Altitud"),
            "it": ("Tempo", "Velocità", "Distanza", "Altitudine"),
            "pt": ("Tempo", "Velocidade", "Distância", "Altitude"),
            "nl": ("Tijd", "Snelheid", "Afstand", "Hoogte"),
            "pl": ("Czas", "Prędkość", "Dystans", "Wysokość"),
            "ru": ("Время", "Скорость", "Дистанция", "Высота"),
            "uk": ("Час", "Швидкість", "Дистанція", "Висота"),
            "tr": ("Süre", "Hız", "Mesafe", "Rakım"),
            "zh": ("时间", "速度", "距离", "海拔"),
            "ja": ("時間", "速度", "距離", "高度"),
            "ko": ("시간", "속도", "거리", "고도"),
        }.get(
            self._ai_language(),
            ("Time", "Speed", "Distance", "Altitude"),
        )

        parts = []

        duration = context.get("session_duration_minutes")
        speed = context.get("speed_kmh")
        distance = context.get("distance_km")
        altitude = context.get("altitude_m")

        if duration is not None:
            parts.append(f"{labels[0]} {duration:.0f} min.")

        if speed is not None:
            parts.append(f"{labels[1]} {speed:.1f} km/h.")

        if distance is not None:
            parts.append(f"{labels[2]} {distance:.2f} km.")

        if altitude is not None:
            parts.append(f"{labels[3]} {altitude:.0f} m.")

        return " ".join(parts)

    def _static_periodic_calculated_message(self, context: dict) -> str:
        """Return the most useful localized calculated live context for plain TTS."""
        code = self._ai_language()
        labels = {
            "en": ("HR reserve", "of HR threshold", "of power threshold", "of speed threshold"),
            "el": ("καρδιακό απόθεμα", "του ορίου παλμών", "του ορίου ισχύος", "του ορίου ταχύτητας"),
            "de": ("Herzfrequenzreserve", "der Herzfrequenzschwelle", "der Leistungsschwelle", "der Geschwindigkeitsschwelle"),
            "fr": ("réserve cardiaque", "du seuil cardiaque", "du seuil de puissance", "du seuil de vitesse"),
            "es": ("reserva cardíaca", "del umbral cardíaco", "del umbral de potencia", "del umbral de velocidad"),
            "it": ("riserva cardiaca", "della soglia cardiaca", "della soglia di potenza", "della soglia di velocità"),
            "pt": ("reserva cardíaca", "do limiar cardíaco", "do limiar de potência", "do limiar de velocidade"),
            "nl": ("hartslagreserve", "van de hartslagdrempel", "van de vermogensdrempel", "van de snelheidsdrempel"),
            "pl": ("rezerwa tętna", "progu tętna", "progu mocy", "progu prędkości"),
            "ru": ("резерв пульса", "от порога пульса", "от порога мощности", "от порога скорости"),
            "uk": ("резерв пульсу", "від порогу пульсу", "від порогу потужності", "від порогу швидкості"),
            "tr": ("kalp hızı rezervi", "kalp hızı eşiğinin", "güç eşiğinin", "hız eşiğinin"),
            "zh": ("心率储备", "心率阈值的", "功率阈值的", "速度阈值的"),
            "ja": ("心拍予備率", "心拍閾値の", "パワー閾値の", "速度閾値の"),
            "ko": ("심박 예비율", "심박 역치의", "파워 역치의", "속도 역치의"),
        }.get(code, ("HR reserve", "of HR threshold", "of power threshold", "of speed threshold"))
        candidates = [
            (context.get("heart_rate_reserve_percent"), f"{labels[0]} {{:.0f}}%."),
            (context.get("heart_rate_relative_threshold_percent"), f"{{:.0f}}% {labels[1]}."),
            (context.get("power_relative_threshold_percent"), f"{{:.0f}}% {labels[2]}."),
            (context.get("speed_relative_threshold_percent"), f"{{:.0f}}% {labels[3]}."),
        ]
        parts = []
        for value, template in candidates:
            if value is None:
                continue
            parts.append(template.format(float(value)))
            if len(parts) >= 2:
                break
        return " ".join(parts)

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

        more = self._static_periodic_extra_message(context)
        calculated = self._static_periodic_calculated_message(context)

        pieces = [piece for piece in (base, more, calculated) if piece]
        base = " ".join(pieces)

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
            base = f"{base} {extra}"

        motivation = {
            "en": "Keep it controlled and keep moving—you are building the session one minute at a time.",
            "el": "Κράτησε τον έλεγχο και συνέχισε—χτίζεις την προπόνηση λεπτό προς λεπτό.",
            "de": "Bleib kontrolliert und mach weiter—Minute für Minute baust du diese Einheit auf.",
            "fr": "Reste maîtrisé et continue—tu construis ta séance minute après minute.",
            "es": "Mantén el control y sigue—estás construyendo la sesión minuto a minuto.",
            "it": "Resta in controllo e continua—stai costruendo la sessione minuto dopo minuto.",
            "pt": "Mantém o controlo e continua—estás a construir o treino minuto a minuto.",
            "nl": "Blijf gecontroleerd doorgaan—minuut voor minuut bouw je deze training op.",
            "pl": "Zachowaj kontrolę i działaj dalej—budujesz ten trening minuta po minucie.",
            "ru": "Сохраняй контроль и продолжай—ты строишь тренировку минуту за минутой.",
            "uk": "Зберігай контроль і продовжуй—ти будуєш тренування хвилина за хвилиною.",
            "tr": "Kontrollü kal ve devam et—antrenmanı dakika dakika oluşturuyorsun.",
            "zh": "保持控制并继续前进——你正在一分一秒地完成这次训练。",
            "ja": "コントロールを保って続けましょう。一分一分がこのセッションを作っています。",
            "ko": "컨트롤을 유지하며 계속하세요. 한 분 한 분이 이번 운동을 만들어 갑니다.",
        }.get(language, "Keep it controlled and keep moving—you are building the session one minute at a time.")
        return f"{base} {motivation}"

    async def _async_periodic_live_announcements(self):
        """Evaluate and speak the ongoing workout every configured X minutes."""
        interval = self._periodic_live_interval_seconds()
        loop = asyncio.get_running_loop()
        next_due = loop.time() + interval

        try:
            while self.session_active:
                await asyncio.sleep(max(0.0, next_due - loop.time()))

                if not self.session_active:
                    break

                # Refresh immediately before each scheduled evaluation so an AI
                # request delayed by serialization starts from current workout
                # statistics rather than a stale previous 30-second snapshot.
                self._compute_live_calculation_snapshot()

                message = await self._async_periodic_live_message()
                if message and self.session_active:
                    self.last_periodic_live_announcement_time = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    self.last_periodic_live_message = message
                    await self._async_speak(message)
                    self._notify()

                # Keep cadence anchored to workout time. If one message was
                # delayed, do not redefine "every X minutes" from its finish.
                next_due += interval
                while next_due <= loop.time():
                    next_due += interval

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

    async def _async_wait_for_tts_playback(
        self,
        media_players: list[str],
        *,
        start_timeout: float = 5.0,
        finish_timeout: float = 120.0,
    ) -> None:
        """Wait until TTS playback has started and then fully finished.

        The TTS service returning does not mean audio playback is complete.
        Fitness therefore watches the target media-player states. A short start
        timeout prevents a player that never exposes `playing` from blocking
        announcements forever, and a hard finish timeout protects against a
        device that remains stuck in `playing`.
        """
        if not media_players:
            return

        loop = asyncio.get_running_loop()
        start_deadline = loop.time() + max(0.0, start_timeout)
        saw_playing: set[str] = set()

        # First wait for each responsive target to expose playback. If no
        # target ever reports playing, release after the short grace period.
        while loop.time() < start_deadline:
            for entity_id in media_players:
                state = self.hass.states.get(entity_id)
                if state is not None and state.state == "playing":
                    saw_playing.add(entity_id)

            if saw_playing:
                break

            await asyncio.sleep(0.1)

        if not saw_playing:
            return

        finish_deadline = loop.time() + max(0.0, finish_timeout)

        # Once playback was observed, do not permit the next Fitness TTS until
        # every player that actually entered `playing` has left that state.
        while loop.time() < finish_deadline:
            still_playing = False

            for entity_id in saw_playing:
                state = self.hass.states.get(entity_id)
                if state is not None and state.state == "playing":
                    still_playing = True
                    break

            if not still_playing:
                return

            await asyncio.sleep(0.1)

    async def _async_speak(self, message: str):
        """Speak one Fitness message at a time and wait for playback to end."""
        async with self._tts_playback_lock:
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
            successful_players: list[str] = []

            # Dispatch the same announcement to all selected targets first.
            # Do not wait for player 1 to finish before starting player 2: they
            # belong to the same announcement and should speak together.
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
                    successful_players.append(media_player)
                except Exception:
                    failed += 1
                    continue

            if success and not failed:
                self.last_feedback_tts_result = "playing"
            elif success and failed:
                self.last_feedback_tts_result = "partial_playing"
            else:
                self.last_feedback_tts_result = "failed"
                return

            self._notify()

            # Crucial: keep the lock until audible playback has ended. Any
            # session, recovery, periodic, or intensity announcement arriving
            # meanwhile waits here instead of interrupting the current speech.
            await self._async_wait_for_tts_playback(successful_players)

            if success and not failed:
                self.last_feedback_tts_result = "success"
            else:
                self.last_feedback_tts_result = "partial_success"

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

        workout = self._apply_beta2_workout_metrics(workout)

        if self._remember_completed_workout(workout):
            await self._save()
            self._notify_workout_history()
            self._notify()

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

        rich_count = sum(
            value is not None
            for value in (
                workout.duration_s,
                workout.distance_m,
                workout.avg_hr,
                workout.max_hr,
                workout.avg_power,
                workout.avg_cadence,
                workout.banister_trimp,
                workout.hrr_60s,
                workout.hrr_120s,
            )
        )
        rich = rich_count >= 3

        spoken = message

        if self.config.get(CONF_AI_ENABLED) and self.ai_workout:
            sentences = [
                s
                for s in re.split(r"(?<=[.!?])\s+", self.ai_workout)
                if s.strip()
            ]

            if rich and len(sentences) > 2:
                spoken = " ".join(
                    [sentences[0], sentences[-1]]
                ).strip()
            else:
                spoken = (
                    " ".join(sentences[:2]).strip()
                    or self.ai_workout
                )

        elif rich:
            spoken = (
                f"{static_message} "
                f"{static_congratulation(self._ai_language())}"
            )

        await self._async_speak(spoken)
        await self._async_notify(
            title=static_title,
            message=message,
        )
        if (
            workout.session_rpe is None
            and workout.source != "fitness_live_capture"
            and "fitness_live_capture" not in (workout.sources or [])
        ):
            self._queue_session_guidance("rpe_reminder")

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

    @staticmethod
    def _live_quantity(metric: str) -> str | None:
        return {
            METRIC_HEART_RATE: "heart_rate",
            METRIC_POWER: "power",
            METRIC_CADENCE: "cadence",
            METRIC_SPEED: "speed",
            METRIC_DISTANCE: "distance",
            METRIC_ALTITUDE: "altitude",
        }.get(metric)

    def _switch_live_source_if_needed(self, metric: str):
        """Keep current source while usable; fail over before returning missing."""
        candidates = self._live_candidates_cache.get(metric) or []
        current = self._live_sources_cache.get(metric)

        if current is not None and source_is_usable(self.hass, current):
            return current

        for candidate in candidates:
            if not source_is_usable(self.hass, candidate):
                continue

            if current is None or candidate.entity_id != current.entity_id:
                previous = current.entity_id if current else None
                self._live_sources_cache[metric] = candidate
                self._live_source_switches.append(
                    {
                        "metric": metric,
                        "from": previous,
                        "to": candidate.entity_id,
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat(),
                    }
                )
            return candidate

        return current

    def live_values(self, raw: bool = False) -> dict[str, float | None]:
        """Return canonical measurements using sticky per-metric failover."""
        if not raw and not self.session_active:
            return {
                METRIC_HEART_RATE: None,
                METRIC_POWER: None,
                METRIC_CADENCE: None,
                METRIC_SPEED: None,
                METRIC_DISTANCE: None,
                METRIC_ALTITUDE: None,
            }

        if not self._live_candidates_cache:
            self._live_candidates_cache = discover_candidates(
                self.hass,
                self.config,
            )
        if not self._live_sources_cache:
            self._live_sources_cache = {
                metric: items[0]
                for metric, items in self._live_candidates_cache.items()
                if items
            }

        native = get_live_runtime(self.hass).live_values(self.entry.entry_id)
        result = {}
        for metric in (
            METRIC_HEART_RATE,
            METRIC_POWER,
            METRIC_CADENCE,
            METRIC_SPEED,
            METRIC_DISTANCE,
            METRIC_ALTITUDE,
        ):
            source = self._switch_live_source_if_needed(metric)
            result[metric] = native.get(metric)
            if result[metric] is None:
                result[metric] = (
                    numeric_entity_state(
                        self.hass,
                        source.entity_id,
                        quantity=self._live_quantity(metric),
                    )
                    if source is not None
                    else None
                )
        return result

    def live_sources(self):
        """Return current active source for each metric after sticky failover."""
        for metric in (
            METRIC_HEART_RATE,
            METRIC_POWER,
            METRIC_CADENCE,
            METRIC_SPEED,
            METRIC_DISTANCE,
            METRIC_ALTITUDE,
        ):
            self._switch_live_source_if_needed(metric)
        return self._live_sources_cache

    def live_source_info(self, metric: str) -> dict[str, Any]:
        """Describe current source/fallback status for a live metric."""
        source = self.live_sources().get(metric)
        if source is None:
            return {}

        state = self.hass.states.get(source.entity_id)
        integration = None
        device_name = None

        registry = er.async_get(self.hass)
        entry = registry.async_get(source.entity_id)
        if entry is not None:
            if entry.config_entry_id:
                config_entry = self.hass.config_entries.async_get_entry(
                    entry.config_entry_id
                )
                integration = config_entry.domain if config_entry else None
            if entry.device_id:
                device = dr.async_get(self.hass).async_get(entry.device_id)
                if device is not None:
                    device_name = device.name_by_user or device.name

        initial = self._live_source_initial_entity.get(metric)
        switches = [
            item
            for item in self._live_source_switches
            if item.get("metric") == metric
        ]

        return {
            "source_entity": source.entity_id,
            "source_device": source.device_id,
            "source_device_name": device_name,
            "source_integration": integration,
            "source_available": source_is_usable(self.hass, source),
            "source_unit": (
                state.attributes.get("unit_of_measurement")
                if state is not None else None
            ),
            "discovery_score": source.score,
            "fallback_active": bool(
                initial and source.entity_id != initial
            ),
            "source_switch_count": len(switches),
            "last_source_switch": switches[-1] if switches else None,
        }

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
        self.session_paused = False
        self.recovery_active = False
        self.session_started = datetime.now(timezone.utc)
        self._session_pause_started = None
        self._session_paused_seconds = 0.0
        self._session_segment = 0
        self._pause_distance_raw = None
        self._session_distance_excluded = 0.0
        self.samples = []

        # Re-rank all live candidates at the beginning of each workout.
        # During the workout selection becomes sticky: only failure causes a
        # switch, and a recovered preferred sensor does not steal the metric
        # back until the next workout.
        self._live_candidates_cache = discover_candidates(
            self.hass,
            self.config,
        )
        self._live_sources_cache = {
            metric: items[0]
            for metric, items in self._live_candidates_cache.items()
            if items
        }
        self._live_source_initial_entity = {
            metric: source.entity_id
            for metric, source in self._live_sources_cache.items()
        }
        self._live_source_switches = []

        self._last_live_intensity = None
        self._last_live_intensity_accepted_at = None
        self._candidate_live_intensity = None
        self._candidate_live_intensity_since = None
        self._last_sample_monotonic = None
        self._last_live_notify_monotonic = None

        # One full evaluation at session start is acceptable; never repeat it
        # for every HR/cadence/power event.
        session_evaluation = self.evaluation()
        self._session_profile_context = {
            "max_hr": session_evaluation.get("max_hr"),
            "resting_hr": session_evaluation.get("resting_hr"),
            "weight": session_evaluation.get("weight"),
            "threshold_hr": session_evaluation.get("threshold_hr"),
            "threshold_pace": session_evaluation.get("threshold_pace"),
            "threshold_power": session_evaluation.get("threshold_power"),
        }
        self._session_intensity_max_hr = self._session_profile_context.get("max_hr")
        self._session_intensity_resting_hr = self._session_profile_context.get("resting_hr")

        self.last_feedback_intensity = None
        self.last_feedback_time = None
        self.last_feedback_light_result = None
        self.last_feedback_tts_result = None
        self.last_feedback_message = None

        self._capture_sample(force=True)
        self._compute_live_calculation_snapshot()
        if self._live_calculation_task is None or self._live_calculation_task.done():
            self._live_calculation_task = self.hass.async_create_task(self._async_live_calculation_loop())

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

    def _capture_sample(self, *, force: bool = False) -> bool:
        """Capture at most one canonical active-workout sample per second.

        Pause windows are never sampled. ``_timestamp_epoch`` follows active
        workout time instead of wall-clock time so integration-based metrics
        cannot accidentally integrate across a pause gap.
        """
        if self.session_paused:
            return False

        loop_now = asyncio.get_running_loop().time()
        if (
            not force
            and self._last_sample_monotonic is not None
            and loop_now - self._last_sample_monotonic < 1.0
        ):
            return False

        values = self.live_values(raw=True)
        if not any(v is not None for v in values.values()):
            return False

        raw_distance = values.get(METRIC_DISTANCE)
        if raw_distance is not None and self._session_distance_excluded:
            try:
                values[METRIC_DISTANCE] = (
                    float(raw_distance) - self._session_distance_excluded
                )
            except (TypeError, ValueError):
                pass

        now = datetime.now(timezone.utc)
        active_epoch = (
            self.session_started.timestamp() + self.session_duration(now=now)
            if self.session_started is not None
            else now.timestamp()
        )
        self.samples.append(
            {
                "timestamp": now.isoformat(),
                "_timestamp_epoch": active_epoch,
                "_segment": self._session_segment,
                **values,
            }
        )
        self._last_sample_monotonic = loop_now
        return True

    async def async_start_session(self):
        """Arm workout capture; the timer starts only on first valid live data."""
        if self.session_active or self.session_armed:
            return

        if self._recovery_task and not self._recovery_task.done():
            self._recovery_task.cancel()
            self._recovery_task = None

        self.recovery_active = False
        self.session_armed = True
        self.session_paused = False
        self.session_started = None
        self._session_pause_started = None
        self._session_paused_seconds = 0.0
        self._session_segment = 0
        self._pause_distance_raw = None
        self._session_distance_excluded = 0.0
        self.samples = []
        self.session_rpe = None

        self._last_live_intensity = None
        self._last_live_intensity_accepted_at = None
        self.last_feedback_intensity = None
        self.last_feedback_time = None
        self.last_feedback_light_result = None
        self.last_feedback_tts_result = None
        self.last_feedback_message = None

        self.capture_control = await get_live_runtime(self.hass).async_prepare_session(self.entry)

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

    async def async_pause_session(self):
        """Pause Fitness consumption while leaving live source capture running."""
        if not self.session_active or self.session_paused:
            return

        # Capture the final active point before the exclusion window starts.
        self._capture_sample(force=True)
        self._compute_live_calculation_snapshot()

        raw_distance = self.live_values(raw=True).get(METRIC_DISTANCE)
        try:
            self._pause_distance_raw = (
                float(raw_distance) if raw_distance is not None else None
            )
        except (TypeError, ValueError):
            self._pause_distance_raw = None

        self.session_paused = True
        self._session_pause_started = datetime.now(timezone.utc)
        self._candidate_live_intensity = None
        self._candidate_live_intensity_since = None
        self._last_live_intensity = None
        self._last_live_intensity_accepted_at = None

        # Derived values are intentionally unavailable during pause. Direct
        # source sensors still update through the live-only notification path.
        self._live_session_statistics_cache = {}
        self._live_derived_cache = {}
        self._live_coaching_context_cache = {}

        if (
            self._live_calculation_task
            and not self._live_calculation_task.done()
        ):
            self._live_calculation_task.cancel()
        self._live_calculation_task = None

        if (
            self._periodic_live_announcement_task
            and not self._periodic_live_announcement_task.done()
        ):
            self._periodic_live_announcement_task.cancel()
        self._periodic_live_announcement_task = None

        if self._feedback_scene_active:
            await self._async_restore_feedback_lights(clear_snapshot=True)

        self._queue_session_guidance("paused")
        self._notify()
        self._notify_live()

    async def async_resume_session(self):
        """Resume workout calculations after a paused exclusion window."""
        if not self.session_active or not self.session_paused:
            return

        now = datetime.now(timezone.utc)
        if self._session_pause_started is not None:
            self._session_paused_seconds += max(
                0.0,
                (now - self._session_pause_started).total_seconds(),
            )

        raw_distance = self.live_values(raw=True).get(METRIC_DISTANCE)
        try:
            resumed_distance = (
                float(raw_distance) if raw_distance is not None else None
            )
        except (TypeError, ValueError):
            resumed_distance = None

        if (
            self._pause_distance_raw is not None
            and resumed_distance is not None
            and resumed_distance >= self._pause_distance_raw
        ):
            self._session_distance_excluded += (
                resumed_distance - self._pause_distance_raw
            )

        self._session_pause_started = None
        self._pause_distance_raw = None
        self.session_paused = False
        self._session_segment += 1
        self._last_sample_monotonic = None
        self._last_live_notify_monotonic = None

        # The first resumed sample starts a fresh active segment. Its adjusted
        # cumulative distance is continuous with the pre-pause workout.
        self._capture_sample(force=True)
        self._compute_live_calculation_snapshot()

        if (
            self._live_calculation_task is None
            or self._live_calculation_task.done()
        ):
            self._live_calculation_task = self.hass.async_create_task(
                self._async_live_calculation_loop()
            )

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

        self._queue_session_guidance("resumed")
        self._notify()
        self._notify_live()

    async def async_stop_session(self):
        """Stop workout timing; optionally keep capture for 120 s HR recovery."""
        if self.session_armed and not self.session_active:
            self.session_armed = False
            self._session_intensity_max_hr = None
            self._session_intensity_resting_hr = None
            self._candidate_live_intensity = None
            self._candidate_live_intensity_since = None
            self.capture_control = await get_live_runtime(self.hass).async_finish_session(self.entry, keep_heart_rate=False)

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

        self._capture_sample(force=True)
        self._compute_live_calculation_snapshot()
        stop_time = datetime.now(timezone.utc)
        if self._live_calculation_task and not self._live_calculation_task.done():
            self._live_calculation_task.cancel()
        self._live_calculation_task = None

        previous_signature = self._workout_signature(
            self.latest_workout()
        )

        workout = self._finalize_local_workout(stop_time)

        # The workout itself is over now. Live entities immediately become
        # unavailable even if ANT capture remains on for recovery.
        self.session_active = False
        self.session_armed = False
        self.session_paused = False
        self._session_pause_started = None

        # Visual indication that workout timing is over and post-exercise
        # handling has begun. It restores the exact pre-cue light state.
        self._queue_session_status_cue("red")

        if (
            self._periodic_live_announcement_task
            and not self._periodic_live_announcement_task.done()
        ):
            self._periodic_live_announcement_task.cancel()
        self._periodic_live_announcement_task = None

        history_changed = False
        if workout is not None:
            history_changed = self._remember_completed_workout(workout)

        if history_changed:
            await self._save()
            self._notify_workout_history()
        self._notify()

        # HR recovery requires post-exercise HR samples. Keep ANT capture alive
        # for up to two minutes when HR was present at workout end.
        last_hr = None
        for sample in reversed(self.samples):
            if sample.get(METRIC_HEART_RATE) is not None:
                last_hr = float(sample[METRIC_HEART_RATE])
                break

        if workout is not None and last_hr is not None:
            # Release every non-HR live sensor immediately, but keep whichever
            # assigned transport can still supply heart rate for HRR. The live
            # runtime retains the pre-workout capture snapshot for final restore.
            self.capture_control = await get_live_runtime(self.hass).async_finish_session(
                self.entry, keep_heart_rate=True
            )
            self.recovery_active = True
            self._recovery_reference_hr = last_hr
            self._recovery_workout_start = workout.start
            self._queue_session_guidance("recovery_wait")
            self._recovery_task = self.hass.async_create_task(
                self._async_collect_heart_rate_recovery()
            )
        else:
            self.capture_control = await get_live_runtime(self.hass).async_finish_session(self.entry, keep_heart_rate=False)
            if workout is not None:
                self._queue_session_guidance("no_recovery")
                if workout.session_rpe is None:
                    self._queue_session_guidance("rpe_reminder")

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
            self.capture_control = await get_live_runtime(self.hass).async_finish_session(self.entry, keep_heart_rate=False)
            return

        checkpoints = (
            # Keep the scientifically useful 10 s sample, but do not interrupt
            # the user with a 10-second announcement/light cue.
            (10, "hrr_10s", False),
            (30, "hrr_30s", True),
            (60, "hrr_60s", True),
            (90, None, True),
            (120, "hrr_120s", False),
        )
        elapsed = 0
        recovery_completed = False

        try:
            for seconds, field_name, announce_checkpoint in checkpoints:
                await asyncio.sleep(seconds - elapsed)
                elapsed = seconds

                hr = self.live_values(raw=True).get(
                    METRIC_HEART_RATE
                )
                remaining = max(0, 120 - seconds)

                checkpoint_color = {
                    30: "yellow",
                    60: "orange",
                    90: "blue",
                    120: "green",
                }.get(seconds)
                if checkpoint_color is not None:
                    self._queue_session_status_cue(checkpoint_color)

                # Speak only 30/60/90 s checkpoints. At 120 s the dedicated
                # completion message replaces an awkward "0 seconds left" cue.
                if announce_checkpoint:
                    self._queue_session_guidance(
                        "recovery_checkpoint",
                        seconds=seconds,
                        remaining=remaining,
                        collected=(hr is not None),
                    )

                if hr is None:
                    continue

                recovery = max(0.0, reference - float(hr))

                if field_name is not None:
                    for item in reversed(self.history):
                        if item.get("start") == workout_start:
                            item[field_name] = round(recovery, 1)
                            break

                await self._save()
                self._notify()

            recovery_completed = True

        except asyncio.CancelledError:
            return
        finally:
            self.recovery_active = False
            self._recovery_reference_hr = None
            self._recovery_workout_start = None
            self._session_intensity_max_hr = None
            self._session_intensity_resting_hr = None
            self._candidate_live_intensity = None
            self._candidate_live_intensity_since = None
            self.capture_control = await get_live_runtime(self.hass).async_finish_recovery(self.entry)
            await self._save()
            self._notify()

            if recovery_completed:
                await self._async_announce_session_guidance(
                    "recovery_complete"
                )
                completed = self.latest_workout()
                if completed is not None and completed.session_rpe is None:
                    await self._async_announce_session_guidance(
                        "rpe_reminder"
                    )

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

    def session_duration(self, *, now: datetime | None = None) -> float:
        """Return active workout seconds, excluding all pause windows."""
        if not self.session_active or not self.session_started:
            return 0.0

        current = now or datetime.now(timezone.utc)
        paused = self._session_paused_seconds
        if self.session_paused and self._session_pause_started is not None:
            paused += max(
                0.0,
                (current - self._session_pause_started).total_seconds(),
            )

        return max(
            0.0,
            (current - self.session_started).total_seconds() - paused,
        )

    def session_status(self) -> str:
        if self.session_active and self.session_paused:
            return "paused"
        if self.session_active:
            return "active"
        if self.session_armed:
            return "waiting_for_live_data"
        if self.recovery_active:
            return "recovery"
        return "idle"

    def _infer_sport(self) -> str:
        """Infer a sport only from strong live-source evidence.

        Heart-rate-only sessions and generic cadence sensors are deliberately
        named Workout. A provider sync may later supply the authoritative sport
        when both records are merged.
        """
        sources = self.live_sources()
        text = " ".join(
            f"{metric} {source.entity_id}"
            for metric, source in sources.items()
        ).lower()
        has_running_evidence = any(
            token in text
            for token in ("stryd", "footpod", "foot_pod", "running_power", "run_speed")
        )
        has_cycling_evidence = any(
            token in text
            for token in ("cycling", "bicycle", "bike_power", "bike_speed", "trainer")
        )
        if has_running_evidence:
            return "Run"
        if has_cycling_evidence:
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
            messages = {
                "en": "No sufficiently comparable prior Fitness workouts are available yet.",
                "el": "Δεν υπάρχουν ακόμη αρκετές προηγούμενες προπονήσεις Fitness που να είναι συγκρίσιμες.",
                "de": "Es sind noch nicht genügend vergleichbare frühere Fitness-Trainings verfügbar.",
                "fr": "Il n’y a pas encore assez d’entraînements Fitness antérieurs comparables.",
                "es": "Aún no hay suficientes entrenamientos anteriores de Fitness que sean comparables.",
                "it": "Non sono ancora disponibili abbastanza allenamenti Fitness precedenti comparabili.",
                "pt": "Ainda não existem treinos Fitness anteriores suficientemente comparáveis.",
                "nl": "Er zijn nog niet genoeg vergelijkbare eerdere Fitness-trainingen beschikbaar.",
                "pl": "Nie ma jeszcze wystarczającej liczby porównywalnych wcześniejszych treningów Fitness.",
                "ru": "Пока недостаточно сопоставимых предыдущих тренировок Fitness.",
                "uk": "Поки що недостатньо зіставних попередніх тренувань Fitness.",
                "tr": "Henüz yeterince karşılaştırılabilir önceki Fitness antrenmanı yok.",
                "zh": "目前还没有足够可比较的历史 Fitness 训练。",
                "ja": "比較可能な過去の Fitness ワークアウトがまだ十分にありません。",
                "ko": "아직 비교할 수 있는 이전 Fitness 운동이 충분하지 않습니다.",
            }
            lang = str(self._ai_language() or "en").lower().split("-")[0].split("_")[0]
            workout.personal_context_summary = messages.get(lang, messages["en"])
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
            templates = {
                "en": "{count} comparable prior workouts were found, but no directly comparable derived metrics were available.",
                "el": "Βρέθηκαν {count} συγκρίσιμες προηγούμενες προπονήσεις, αλλά δεν υπήρχαν άμεσα συγκρίσιμες υπολογισμένες μετρήσεις.",
                "de": "{count} vergleichbare frühere Trainings wurden gefunden, aber keine direkt vergleichbaren berechneten Messwerte waren verfügbar.",
                "fr": "{count} entraînements antérieurs comparables ont été trouvés, mais aucune mesure calculée directement comparable n’était disponible.",
                "es": "Se encontraron {count} entrenamientos anteriores comparables, pero no había métricas calculadas directamente comparables.",
                "it": "Sono stati trovati {count} allenamenti precedenti comparabili, ma non erano disponibili metriche calcolate direttamente confrontabili.",
                "pt": "Foram encontrados {count} treinos anteriores comparáveis, mas não havia métricas calculadas diretamente comparáveis.",
                "nl": "Er zijn {count} vergelijkbare eerdere trainingen gevonden, maar er waren geen direct vergelijkbare berekende waarden beschikbaar.",
                "pl": "Znaleziono {count} porównywalnych wcześniejszych treningów, ale brakowało bezpośrednio porównywalnych obliczonych metryk.",
                "ru": "Найдено сопоставимых предыдущих тренировок: {count}, но напрямую сравнимых расчётных показателей нет.",
                "uk": "Знайдено зіставних попередніх тренувань: {count}, але безпосередньо порівнюваних розрахованих показників немає.",
                "tr": "{count} karşılaştırılabilir önceki antrenman bulundu, ancak doğrudan karşılaştırılabilir hesaplanmış metrik yoktu.",
                "zh": "找到了 {count} 次可比较的历史训练，但没有可直接比较的计算指标。",
                "ja": "比較可能な過去のワークアウトが {count} 件見つかりましたが、直接比較できる計算指標はありませんでした。",
                "ko": "비교 가능한 이전 운동 {count}개를 찾았지만 직접 비교할 수 있는 계산 지표가 없었습니다.",
            }
            lang = str(self._ai_language() or "en").lower().split("-")[0].split("_")[0]
            workout.personal_context_summary = templates.get(lang, templates["en"]).format(count=len(comparable))

        return workout

    def session_rpe_value(self) -> int | None:
        """Return current live RPE or RPE of the latest completed workout."""
        if self.session_active or self.session_armed:
            return self.session_rpe
        workout = self.latest_workout()
        if workout is None or workout.session_rpe is None:
            return None
        return int(round(workout.session_rpe))

    @staticmethod
    def _fitness_load_decomposition(workout: Workout) -> tuple[float | None, float | None]:
        """Transparent Fitness-owned intensity-time load split (not energy systems)."""
        zones = (
            (workout.time_very_light_s, 0.5, 0.0),
            (workout.time_light_s, 1.0, 0.0),
            (workout.time_moderate_s, 1.5, 0.15),
            (workout.time_vigorous_s, 2.0, 0.55),
            (workout.time_near_maximal_s, 2.5, 0.85),
        )
        available=[z for z in zones if z[0] is not None]
        if not available:
            return None, None
        total=sum(float(seconds)*weight for seconds,weight,_high in available)
        if total <= 0:
            return None, None
        high=sum(float(seconds)*weight*high for seconds,weight,high in available)
        high_pct=max(0.0,min(100.0,high/total*100.0))
        return round(100.0-high_pct,1), round(high_pct,1)

    def _apply_beta2_workout_metrics(self, workout: Workout) -> Workout:
        """Apply provider-independent RPE/load and optional strength analysis."""
        if workout.session_rpe is not None:
            raw_rpe=float(workout.session_rpe)
            if 1 <= raw_rpe <= 10:
                rpe=int(round(raw_rpe))
                workout.session_rpe=float(rpe)
                if workout.duration_s is not None and workout.duration_s > 0:
                    workout.session_rpe_load=round(rpe*(float(workout.duration_s)/60.0),1)
            else:
                workout.session_rpe=None
                workout.session_rpe_load=None
        aerobic, high=self._fitness_load_decomposition(workout)
        workout.fitness_aerobic_load=aerobic
        workout.fitness_high_intensity_load=high

        prior=self.local_workouts()
        if workout.session_rpe_load is not None:
            historical=[float(w.session_rpe_load) for w in prior[-28:] if w.session_rpe_load is not None]
            if len(historical) >= 2:
                baseline=mean(historical)
                if baseline > 0:
                    workout.session_rpe_load_vs_28d_percent=round((workout.session_rpe_load-baseline)/baseline*100.0,1)

        if self.config.get(CONF_DETAILED_STRENGTH_ANALYSIS) and workout_sport_kind(workout) == "strength":
            details=analyze_strength(workout, prior)
            if details:
                workout.extra=dict(workout.extra or {})
                workout.extra["fitness_strength"]=details
                workout.strength_total_sets=float(details.get("total_sets") or 0) or None
                workout.strength_best_estimated_1rm_kg=details.get("best_estimated_1rm_kg")
                workout.strength_progression_percent=details.get("mean_e1rm_change_percent")
                if workout.exercise_count is None: workout.exercise_count=details.get("exercise_count")
                if workout.total_reps is None: workout.total_reps=details.get("total_reps")
                if workout.volume_kg is None: workout.volume_kg=details.get("volume_kg")
        return workout

    async def async_set_session_rpe(self, value: int) -> None:
        """Set integer RPE for current session or latest completed workout and recalculate."""
        value=max(1,min(10,int(round(value))))
        if self.session_active or self.session_armed:
            self.session_rpe=value
            self._notify()
            return
        latest=self.latest_workout()
        if latest is None:
            self.session_rpe=value
            self._notify()
            return
        target_start=latest.start
        changed=False
        for idx in range(len(self.history)-1,-1,-1):
            if self.history[idx].get("start") == target_start:
                updated=Workout(**self.history[idx])
                previous_rpe = updated.session_rpe
                updated.extra = dict(updated.extra or {})
                rpe_meta = dict(updated.extra.get("fitness_rpe") or {})
                if previous_rpe is not None and rpe_meta.get("provider"):
                    rpe_meta.setdefault("provider_base_rpe", int(round(previous_rpe)))
                rpe_meta["active_source"] = "user_override"
                rpe_meta["user_override_rpe"] = value
                updated.extra["fitness_rpe"] = rpe_meta
                updated.session_rpe=float(value)
                updated=self._apply_beta2_workout_metrics(updated)
                updated=self._apply_personal_workout_context(updated)
                self.history[idx]=updated.as_dict()
                changed=True
                break
        if not changed:
            previous_rpe = latest.session_rpe
            latest.extra = dict(latest.extra or {})
            rpe_meta = dict(latest.extra.get("fitness_rpe") or {})
            if previous_rpe is not None and rpe_meta.get("provider"):
                rpe_meta.setdefault("provider_base_rpe", int(round(previous_rpe)))
            rpe_meta["active_source"] = "user_override"
            rpe_meta["user_override_rpe"] = value
            latest.extra["fitness_rpe"] = rpe_meta
            latest.session_rpe=float(value)
            latest=self._apply_beta2_workout_metrics(latest)
            self._remember_completed_workout(latest)
        await self._save()
        self._notify()
        await self._async_refresh_long_term_statistics()

    def _finalize_local_workout(self, stop_time: datetime) -> Workout | None:
        if self.session_started is None:
            return None

        duration = self.session_duration(now=stop_time)
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
        altitude_points = [
            (
                sample.get("_segment", 0),
                float(sample[METRIC_ALTITUDE]),
            )
            for sample in self.samples
            if sample.get(METRIC_ALTITUDE) is not None
        ]
        if len(altitude_points) >= 2:
            elevation_gain = sum(
                max(0.0, b_value - a_value)
                for (a_segment, a_value), (b_segment, b_value)
                in zip(altitude_points, altitude_points[1:])
                if a_segment == b_segment
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
            session_rpe=self.session_rpe,
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

        workout = self._apply_beta2_workout_metrics(workout)
        return self._apply_personal_workout_context(workout)

    def workout_retention_days(self) -> int:
        """Return configured canonical workout retention in days.

        Zero explicitly means unlimited. The default is intentionally long but
        bounded so the JSON-backed canonical store does not grow forever on a
        long-running Home Assistant installation.
        """
        raw = self.config.get(
            CONF_WORKOUT_RETENTION_DAYS,
            DEFAULT_WORKOUT_RETENTION_DAYS,
        )
        try:
            days = int(raw)
        except (TypeError, ValueError):
            days = DEFAULT_WORKOUT_RETENTION_DAYS
        return max(0, min(days, MAX_WORKOUT_RETENTION_DAYS))

    def _retention_cutoff(self) -> datetime | None:
        """Return the oldest automatically retained workout timestamp."""
        days = self.workout_retention_days()
        if days == 0:
            return None
        return datetime.now(timezone.utc) - timedelta(days=days)

    def _bulk_deleted_cutoff(self) -> datetime | None:
        """Return the permanent user bulk-deletion cutoff when configured."""
        return _dt(getattr(self, "deleted_workouts_before", None))

    def _workout_is_outside_retention(self, workout: Workout | None) -> bool:
        if workout is None:
            return True
        start = _dt(workout.start)
        cutoff = self._retention_cutoff()
        return bool(start is not None and cutoff is not None and start < cutoff)

    def _prune_workout_history(self) -> bool:
        """Apply configured automatic retention and explicit bulk deletion."""
        before = len(self.history)
        retention_cutoff = self._retention_cutoff()
        deleted_cutoff = self._bulk_deleted_cutoff()
        kept: list[dict] = []
        for item in self.history:
            try:
                start = _dt(item.get("start"))
            except AttributeError:
                kept.append(item)
                continue
            if start is None:
                kept.append(item)
                continue
            if retention_cutoff is not None and start < retention_cutoff:
                continue
            if deleted_cutoff is not None and start < deleted_cutoff:
                continue
            kept.append(item)
        self.history = kept

        # Individual tombstones older than a permanent bulk-deletion cutoff are
        # redundant and can be discarded safely.
        if deleted_cutoff is not None:
            self.deleted_workouts = [
                item
                for item in self.deleted_workouts
                if _dt(item.get("start")) is None
                or _dt(item.get("start")) >= deleted_cutoff
            ]
        return len(self.history) != before

    async def async_delete_workouts_before(self, days: int) -> int:
        """Delete canonical workouts older than *days* and block re-import.

        The resulting cutoff is persistent. Provider or Recorder reconciliation
        cannot resurrect workouts older than the most recent explicit bulk
        deletion cutoff.
        """
        days = max(1, min(int(days), MAX_WORKOUT_RETENTION_DAYS))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        existing = self._bulk_deleted_cutoff()
        if existing is None or cutoff > existing:
            self.deleted_workouts_before = cutoff.isoformat()

        before = len(self.history)
        self._prune_workout_history()
        deleted = before - len(self.history)
        await self._save()
        if deleted:
            self._notify_workout_history()
            self._notify()
        return deleted

    async def _async_reconcile_external_workouts(self) -> bool:
        """Merge every currently exposed provider workout into history."""
        candidates = discover_external_workouts(self.hass, self.config)
        changed = False
        for workout in sorted(
            candidates,
            key=lambda item: _dt(item.start)
            or datetime.min.replace(tzinfo=timezone.utc),
        ):
            if workout is None or not workout.start:
                continue
            workout = self._apply_beta2_workout_metrics(workout)
            workout = self._apply_personal_workout_context(workout)
            changed = self._remember_completed_workout(workout) or changed
        if changed:
            await self._save()
            self._notify_workout_history()
            self._notify()
        return changed

    async def async_import_provider_workout_history(self) -> int:
        """Import historical workouts exposed by provider-specific HA APIs."""
        try:
            from .providers.workout_history import async_provider_history_workouts
            candidates = await async_provider_history_workouts(self.hass, self.config)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            _LOGGER.debug("Provider workout history import unavailable: %s", err)
            return 0

        changed = False
        for workout in sorted(
            candidates,
            key=lambda item: _dt(item.start)
            or datetime.min.replace(tzinfo=timezone.utc),
        ):
            workout = self._apply_beta2_workout_metrics(workout)
            workout = self._apply_personal_workout_context(workout)
            changed = self._remember_completed_workout(workout) or changed
        if changed:
            await self._save()
            self._notify_workout_history()
            self._notify()
        return len(candidates)

    async def async_import_workouts_from_ha_history(self, *, days: int = 365) -> int:
        """Reconstruct completed workouts from selected entities in Recorder."""
        entity_ids = sorted(set(workout_device_entity_ids(self.hass, self.config)))
        if not entity_ids:
            return 0
        try:
            from functools import partial
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.history import get_significant_states

            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=max(1, min(int(days), 3650)))
            history = await get_instance(self.hass).async_add_executor_job(
                partial(
                    get_significant_states,
                    self.hass,
                    start_time,
                    end_time=end_time,
                    entity_ids=entity_ids,
                    include_start_time_state=False,
                    significant_changes_only=False,
                    minimal_response=False,
                    no_attributes=False,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            _LOGGER.debug("Workout Recorder history import unavailable: %s", err)
            return 0

        try:
            from .providers.workout_history import workouts_from_recorder_history
            candidates = workouts_from_recorder_history(self.hass, self.config, history)
        except Exception as err:
            _LOGGER.exception("Unable to parse completed workouts from Recorder: %s", err)
            return 0

        changed = False
        for workout in sorted(
            candidates,
            key=lambda item: _dt(item.start)
            or datetime.min.replace(tzinfo=timezone.utc),
        ):
            workout = self._apply_beta2_workout_metrics(workout)
            workout = self._apply_personal_workout_context(workout)
            changed = self._remember_completed_workout(workout) or changed
        if changed:
            await self._save()
            self._notify_workout_history()
            self._notify()
        return len(candidates)

    @staticmethod
    def _calendar_uid(entry_id: str, workout: Workout | None) -> str | None:
        """Return the source-independent calendar UID for a workout."""
        if workout is None:
            return None
        start = _dt(workout.start)
        if start is None:
            return None
        return f"fitness-{entry_id}-t5-{int(start.timestamp()) // 300}"

    def _workout_is_deleted(self, workout: Workout | None) -> bool:
        """Return True when a user-deleted workout matches this candidate."""
        if workout is None or not workout.start:
            return False
        start = _dt(workout.start)
        bulk_cutoff = self._bulk_deleted_cutoff()
        if start is not None and bulk_cutoff is not None and start < bulk_cutoff:
            return True
        for item in self.deleted_workouts:
            if not isinstance(item, dict):
                continue
            try:
                tombstone = Workout(
                    source="fitness_deleted",
                    name=item.get("name"),
                    sport=item.get("sport"),
                    start=item.get("start"),
                    end=item.get("end"),
                    duration_s=item.get("duration_s"),
                    distance_m=item.get("distance_m"),
                )
            except TypeError:
                continue
            if _same_real_workout(workout, tombstone):
                return True
        return False

    async def async_delete_calendar_workout(self, uid: str, entry_id: str) -> bool:
        """Delete one canonical workout and remember that deletion.

        A tombstone is necessary because Garmin/Strava/Recorder history can
        expose the same physical workout again after the user deletes it.
        """
        target = None
        for workout in self.local_workouts():
            if self._calendar_uid(entry_id, workout) == uid:
                target = workout
                break
        if target is None:
            return False

        kept: list[dict] = []
        for item in self.history:
            try:
                candidate = Workout(**item)
            except TypeError:
                kept.append(item)
                continue
            if _same_real_workout(candidate, target):
                continue
            kept.append(item)

        self.history = kept
        tombstone = {
            "start": target.start,
            "end": target.end,
            "duration_s": target.duration_s,
            "distance_m": target.distance_m,
            "sport": target.sport,
            "name": target.name,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        }
        if not any(
            item.get("start") == tombstone["start"]
            and item.get("sport") == tombstone["sport"]
            for item in self.deleted_workouts
            if isinstance(item, dict)
        ):
            self.deleted_workouts.append(tombstone)
            self.deleted_workouts = self.deleted_workouts[-1000:]

        await self._save()
        self._notify_workout_history()
        self._notify()
        return True

    def _remember_completed_workout(self, workout: Workout | None) -> bool:
        """Merge a completed workout into persistent history without duplicates."""
        if workout is None or not workout.start:
            return False
        if self._workout_is_outside_retention(workout):
            return False
        if self._workout_is_deleted(workout):
            return False
        before = json.dumps(self.history, sort_keys=True, default=str)
        records = self.local_workouts()
        records.append(workout)
        merged = merged_workouts(records)
        merged.sort(
            key=lambda item: _dt(item.start)
            or datetime.min.replace(tzinfo=timezone.utc)
        )
        self.history = [item.as_dict() for item in merged]
        self._prune_workout_history()
        after = json.dumps(self.history, sort_keys=True, default=str)
        return before != after

    def local_workouts(self) -> list[Workout]:
        """Return canonical de-duplicated Fitness workout history.

        Historical storage may still contain two provider representations that
        were written before a later merge rule became available. Re-clustering
        on read prevents those stale duplicates from inflating 7/28-day load,
        workout counts, recovery estimates, or training-adaptation status.
        """
        result = []
        for item in self.history:
            try:
                result.append(Workout(**item))
            except TypeError:
                continue
        return merged_workouts(result)

    def latest_workout(self) -> Workout | None:
        """Return the canonical latest workout without repeated registry scans."""
        if self._latest_workout_cache_ready:
            return self._latest_workout_cache
        candidates = self.local_workouts() + discover_external_workouts(
            self.hass, self.config
        )
        self._latest_workout_cache = newest(candidates)
        self._latest_workout_cache_ready = True
        return self._latest_workout_cache

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
        """Return cached derived session statistics refreshed every 30 seconds."""
        return (
            self._live_session_statistics_cache
            if self.session_active and not self.session_paused
            else {}
        )

    async def _async_delayed_long_term_refresh(self) -> None:
        await asyncio.sleep(8)
        await self._async_refresh_long_term_statistics()

    @staticmethod
    def _summarize_stat_periods(periods: list[dict[str, Any]]) -> dict[str, Any]:
        """Legacy helper retained for compatibility tests; validate before summarizing."""
        temp: dict[str, list[dict[str, Any]]] = {"legacy": []}
        ingest_recorder(temp, "legacy", periods, "recorder_legacy")
        summaries, _audits = summarize_all(temp)
        return summaries.get("legacy", {})

    async def _async_refresh_long_term_statistics(self) -> None:
        """Refresh canonical Fitness history; Recorder is bootstrap ingestion only."""
        now = datetime.now(timezone.utc)
        provider = collect_provider_metrics(self.hass, self.config)
        entity_to_metric: dict[str, str] = {}
        metric_keys = (
            "vo2max", "resting_hr", "weight_kg", "hrv_weekly",
            "hrv_last_night", "fitness_age", "threshold_hr",
            "threshold_speed", "ftp_running", "power_to_weight_running",
            "training_readiness", "sleep_score",
        )
        for key in metric_keys:
            entity_id = provider.get(f"{key}_entity")
            if isinstance(entity_id, str):
                entity_to_metric[entity_id] = key

        config_metrics = {
            CONF_WEIGHT: "weight", CONF_RESTING_HR: "resting_hr",
            CONF_MAX_HR: "max_hr", CONF_VO2MAX: "vo2max",
            "threshold_hr": "threshold_hr", "threshold_pace": "threshold_pace",
            "threshold_power": "threshold_power",
        }
        for key, metric in config_metrics.items():
            raw = self.config.get(key)
            if is_entity_reference(raw):
                entity_to_metric[str(raw).strip()] = metric

        # First persist the already normalized/selected Fitness facts. They
        # outrank any imported Recorder observation for the same day.
        for metric in metric_keys:
            value = provider.get(metric)
            if value is None:
                continue
            source_entity = provider.get(f"{metric}_entity")
            remember(
                self.metric_history, metric, value, now,
                source_type="fitness_merged_current",
                source_entity=source_entity,
                sources=[str(source_entity)] if source_entity else [],
                imported=False, now=now,
            )
        for config_key, metric in ((CONF_WEIGHT,"weight"),(CONF_RESTING_HR,"resting_hr"),(CONF_VO2MAX,"vo2max")):
            value = self.input_value(config_key)
            if value is not None:
                remember(self.metric_history, metric, value, now, source_type="fitness_merged_current", imported=False, now=now)

        # Existing installations retain up to 90 days by importing Recorder
        # rows into Fitness storage. Recorder never directly produces a result.
        if entity_to_metric and self.hass.services.has_service("recorder", "get_statistics"):
            try:
                response = await self.hass.services.async_call(
                    "recorder", "get_statistics",
                    {"statistic_ids": sorted(entity_to_metric),
                     "start_time": (now - timedelta(days=90)).isoformat(),
                     "period": "day", "types": ["mean", "min", "max", "state"]},
                    blocking=True, return_response=True,
                )
            except Exception:
                response = None
            if isinstance(response, dict):
                raw_statistics = response.get("statistics")
                if not isinstance(raw_statistics, dict):
                    raw_statistics = response
                for entity_id, metric in entity_to_metric.items():
                    periods = raw_statistics.get(entity_id)
                    if isinstance(periods, list):
                        ingest_recorder(self.metric_history, metric, periods, entity_id, now)

        self.long_term_statistics, self.history_validation = summarize_all(self.metric_history, now)
        self.long_term_statistics_updated = now.isoformat()
        await self._save()
        self._notify()

    def workout_long_term_summary(self) -> dict[str, Any]:
        """Evidence-oriented trends from actual stored, merged Fitness workouts."""
        raw_workouts = self.local_workouts()
        now = datetime.now(timezone.utc)
        workout_rejections: dict[str, int] = {}
        workouts = []
        for workout in raw_workouts:
            reason = validate_workout(workout, now)
            if reason:
                workout_rejections[reason] = workout_rejections.get(reason, 0) + 1
                continue
            workouts.append(workout)

        def parse_start(workout):
            try:
                dt = datetime.fromisoformat(str(workout.start).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                return None

        recent: list[tuple[datetime, Workout]] = []
        for workout in workouts:
            dt = parse_start(workout)
            if dt is None:
                continue
            age_days = (now - dt).total_seconds() / 86400
            if 0 <= age_days <= 90:
                recent.append((dt, workout))
        recent.sort(key=lambda item: item[0])

        def within(days: int):
            return [(dt, w) for dt, w in recent if (now - dt).total_seconds() <= days * 86400]

        def load(days: int):
            vals = [float(w.banister_trimp) for _dt, w in within(days) if w.banister_trimp is not None]
            return sum(vals) if vals else None

        load7, load28 = load(7), load(28)
        change = None
        if load7 is not None and load28 is not None and load28 > 0:
            weekly_baseline = load28 / 4.0
            if weekly_baseline > 0:
                change = (load7 - weekly_baseline) / weekly_baseline * 100.0

        w7, w28 = within(7), within(28)
        duration7 = sum(float(w.duration_s or 0) for _dt, w in w7 if w.duration_s is not None)
        duration28 = sum(float(w.duration_s or 0) for _dt, w in w28 if w.duration_s is not None)
        distance7 = sum(float(w.distance_m or 0) for _dt, w in w7 if w.distance_m is not None)
        distance28 = sum(float(w.distance_m or 0) for _dt, w in w28 if w.distance_m is not None)

        recovery_intervals = []
        for (prev_dt, prev), (next_dt, _next) in zip(recent, recent[1:]):
            prev_end = prev_dt + timedelta(seconds=float(prev.duration_s or 0))
            hours = (next_dt - prev_end).total_seconds() / 3600.0
            if 0 <= hours <= 14 * 24:
                recovery_intervals.append(hours)

        hrr_workouts = [(dt, w) for dt, w in recent if w.hrr_60s is not None]
        latest_hrr_workout = hrr_workouts[-1][1] if hrr_workouts else None
        prior_hrr = [float(w.hrr_60s) for _dt, w in hrr_workouts[:-1]]
        baseline_hrr = mean(prior_hrr) if len(prior_hrr) >= 2 else None
        hrr120_workouts = [(dt, w) for dt, w in recent if w.hrr_120s is not None]
        latest_hrr120 = hrr120_workouts[-1][1] if hrr120_workouts else None
        prior_hrr120 = [float(w.hrr_120s) for _dt, w in hrr120_workouts[:-1]]
        baseline_hrr120 = mean(prior_hrr120) if len(prior_hrr120) >= 2 else None
        rpe_load7 = sum(float(w.session_rpe_load) for _dt,w in w7 if w.session_rpe_load is not None) or None
        rpe_load28 = sum(float(w.session_rpe_load) for _dt,w in w28 if w.session_rpe_load is not None) or None

        return {
            "history_valid": bool(workouts),
            "history_source": "fitness_canonical_workout_history",
            "history_raw_records": len(raw_workouts),
            "history_valid_records": len(workouts),
            "history_rejected_records": sum(workout_rejections.values()),
            "history_rejection_reasons": dict(sorted(workout_rejections.items())),
            "workouts_7d": len(w7) if w7 else None,
            "workouts_28d": len(w28) if w28 else None,
            "active_training_days_7d": len({dt.date() for dt, _ in w7}) if w7 else None,
            "active_training_days_28d": len({dt.date() for dt, _ in w28}) if w28 else None,
            "training_duration_7d_min": round(duration7 / 60.0, 1) if duration7 else None,
            "training_duration_28d_min": round(duration28 / 60.0, 1) if duration28 else None,
            "distance_7d_km": round(distance7 / 1000.0, 2) if distance7 else None,
            "distance_28d_km": round(distance28 / 1000.0, 2) if distance28 else None,
            "banister_trimp_7d": round(load7, 1) if load7 is not None else None,
            "banister_trimp_28d": round(load28, 1) if load28 is not None else None,
            "banister_trimp_28d_weekly_equivalent": round(load28 / 4.0, 1) if load28 is not None else None,
            "training_load_change_7_vs_28_percent": round(change, 1) if change is not None else None,
            "median_recovery_interval_28d_h": round(median(recovery_intervals[-20:]), 1) if recovery_intervals else None,
            "last_recovery_interval_h": round(recovery_intervals[-1], 1) if recovery_intervals else None,
            "hrr_samples_90d": len(hrr_workouts),
            "latest_hrr_30s": round(float(latest_hrr_workout.hrr_30s), 1) if latest_hrr_workout and latest_hrr_workout.hrr_30s is not None else None,
            "latest_hrr_60s": round(float(latest_hrr_workout.hrr_60s), 1) if latest_hrr_workout else None,
            "latest_hrr_120s": round(float(latest_hrr_workout.hrr_120s), 1) if latest_hrr_workout and latest_hrr_workout.hrr_120s is not None else None,
            "hrr_60s_baseline_90d": round(baseline_hrr, 1) if baseline_hrr is not None else None,
            "hrr_60s_latest_vs_90d_bpm": round(float(latest_hrr_workout.hrr_60s) - baseline_hrr, 1) if latest_hrr_workout and baseline_hrr is not None else None,
            "hrr_120s_samples_90d": len(hrr120_workouts),
            "hrr_120s_baseline_90d": round(baseline_hrr120, 1) if baseline_hrr120 is not None else None,
            "hrr_120s_latest_vs_90d_bpm": round(float(latest_hrr120.hrr_120s) - baseline_hrr120, 1) if latest_hrr120 and baseline_hrr120 is not None else None,
            "session_rpe_load_7d": round(rpe_load7,1) if rpe_load7 is not None else None,
            "session_rpe_load_28d": round(rpe_load28,1) if rpe_load28 is not None else None,
        }

    def sleep_long_term_summary(self) -> dict[str, Any]:
        """Longitudinal sleep duration, regularity and HRV context.

        Long-term nightly metrics count one main sleep per local wake date. This
        prevents provider duplicates or fragmented records for the same night
        from inflating 7-day sleep deficit and sample counts.

        HRV recovery uses a Fitness-owned personal baseline built from prior
        nights only: a recent 7-night mean is compared with a preceding 28-day
        baseline. The latest night is never included in its own baseline.
        """
        raw_records = self._sleep_records_from_history()
        now = datetime.now(timezone.utc)
        sleep_rejections: dict[str, int] = {}
        records = []
        for record in raw_records:
            reason = validate_sleep(record, now)
            if reason:
                sleep_rejections[reason] = sleep_rejections.get(reason, 0) + 1
                continue
            records.append(record)
        tz = ZoneInfo(getattr(self.hass.config, "time_zone", "UTC") or "UTC")

        # One main sleep per local wake date. Provider copies of the same night
        # can occasionally survive timestamp clustering when their boundaries
        # differ substantially. Counting both would make a 7-day deficit grow
        # simply because another provider synchronized later. For longitudinal
        # nightly metrics, keep the longest/richest validated record for that
        # wake date. Short naps therefore do not replace the main night's sleep.
        nightly_by_date: dict[Any, tuple[datetime, SleepRecord]] = {}
        duplicate_nightly_records = 0
        for record in records:
            stamp = _dt(record.end or record.start)
            if stamp is None:
                continue
            age_days = (now - stamp).total_seconds() / 86400
            if not (0 <= age_days <= 90):
                continue
            wake_date = stamp.astimezone(tz).date()
            current = nightly_by_date.get(wake_date)
            if current is None:
                nightly_by_date[wake_date] = (stamp, record)
                continue
            duplicate_nightly_records += 1
            _current_stamp, current_record = current
            current_duration = float(current_record.duration_s or 0.0)
            candidate_duration = float(record.duration_s or 0.0)
            current_richness = sum(
                getattr(current_record, name) is not None
                for name in ("duration_s", "light_sleep_s", "deep_sleep_s", "rem_sleep_s", "awake_s", "hrv_ms", "score")
            )
            candidate_richness = sum(
                getattr(record, name) is not None
                for name in ("duration_s", "light_sleep_s", "deep_sleep_s", "rem_sleep_s", "awake_s", "hrv_ms", "score")
            )
            if (candidate_duration, candidate_richness, stamp) > (current_duration, current_richness, _current_stamp):
                nightly_by_date[wake_date] = (stamp, record)

        dated = sorted(nightly_by_date.values(), key=lambda item: item[0])

        def subset(days: int):
            return [(stamp, r) for stamp, r in dated if (now - stamp).total_seconds() <= days * 86400]

        def field_values(field: str, days: int):
            return [float(getattr(r, field)) for _stamp, r in subset(days) if getattr(r, field) is not None]

        def avg(field: str, days: int, minimum: int):
            vals = field_values(field, days)
            return mean(vals) if len(vals) >= minimum else None

        duration7, duration28 = avg("duration_s", 7, 5), avg("duration_s", 28, 21)
        hrv7 = avg("hrv_ms", 7, 5)
        latest = self.latest_sleep()
        latest_duration = latest.duration_s if latest else None
        latest_hrv = latest.hrv_ms if latest else None

        # Personal HRV baseline: use prior nights only. A weekly average is
        # preferred for the current/recent signal because day-to-day HRV is
        # noisy; compare it with a longer preceding baseline. Keep the legacy
        # 28-day field name for API compatibility, but its value now correctly
        # excludes the newest night from the reference distribution.
        latest_stamp = _dt(latest.end or latest.start) if latest else None
        prior_hrv_28 = [
            float(r.hrv_ms)
            for stamp, r in dated
            if r.hrv_ms is not None
            and (latest_stamp is None or stamp < latest_stamp)
            and (now - stamp).total_seconds() <= 28 * 86400
        ]
        hrv28 = mean(prior_hrv_28) if len(prior_hrv_28) >= 14 else None
        recent_hrv_values = field_values("hrv_ms", 7)
        recent_hrv = mean(recent_hrv_values) if len(recent_hrv_values) >= 5 else None
        hrv_recent_vs_baseline = (
            (recent_hrv - hrv28) / abs(hrv28) * 100.0
            if recent_hrv is not None and hrv28 not in (None, 0)
            else None
        )
        latest_hrv_vs_baseline = (
            (float(latest_hrv) - hrv28) / abs(hrv28) * 100.0
            if latest_hrv is not None and hrv28 not in (None, 0)
            else None
        )

        def circular_sd(kind: str, days: int, minimum: int = 5):
            vals = []
            for _stamp, record in subset(days):
                start_dt, end_dt = _dt(record.start), _dt(record.end)
                if not start_dt or not end_dt or end_dt <= start_dt:
                    continue
                if kind == "start": target = start_dt.astimezone(tz)
                elif kind == "end": target = end_dt.astimezone(tz)
                else: target = (start_dt + (end_dt - start_dt) / 2).astimezone(tz)
                vals.append(target.hour * 60 + target.minute + target.second / 60)
            if len(vals) < minimum:
                return None
            anchor = vals[0]
            unwrapped = [anchor + (((v - anchor + 720) % 1440) - 720) for v in vals]
            return pstdev(unwrapped)

        durations28 = field_values("duration_s", 28)
        duration_sd28 = pstdev([v / 60.0 for v in durations28]) if len(durations28) >= 21 else None
        bedtime_sd = circular_sd("start", 28)
        waketime_sd = circular_sd("end", 28)
        midpoint_sd = circular_sd("midpoint", 28)

        seven = field_values("duration_s", 7)
        twenty_eight = field_values("duration_s", 28)
        deficit7 = None
        nights_below7_7 = None
        nightly_deficit_series: list[dict[str, Any]] = []
        if self.age() >= 18 and len(seven) >= 5:
            for stamp, record in subset(7):
                if record.duration_s is None:
                    continue
                deficit_min = max(0.0, 7 * 3600 - float(record.duration_s)) / 60.0
                nightly_deficit_series.append({
                    "date": stamp.astimezone(tz).date().isoformat(),
                    "sleep_minutes": round(float(record.duration_s) / 60.0, 1),
                    "deficit_minutes": round(deficit_min, 1),
                })
            deficit7 = sum(item["deficit_minutes"] for item in nightly_deficit_series)
            nights_below7_7 = sum(1 for item in nightly_deficit_series if item["deficit_minutes"] > 0)
        nights_below7_28 = None
        below7_pct28 = None
        if self.age() >= 18 and len(twenty_eight) >= 14:
            nights_below7_28 = sum(1 for seconds in twenty_eight if seconds < 7 * 3600)
            below7_pct28 = nights_below7_28 / len(twenty_eight) * 100.0

        return {
            "history_valid": bool(records),
            "history_source": "fitness_canonical_sleep_history",
            "history_raw_records": len(raw_records),
            "history_valid_records": len(records),
            "history_unique_nights": len(dated),
            "history_duplicate_nightly_records_ignored": duplicate_nightly_records,
            "history_rejected_records": sum(sleep_rejections.values()),
            "history_rejection_reasons": dict(sorted(sleep_rejections.items())),
            "nights_7d": len(seven) or None,
            "nights_28d": len(twenty_eight) or None,
            "sleep_duration_7d_mean_min": round(duration7 / 60.0, 1) if duration7 is not None else None,
            "sleep_duration_28d_mean_min": round(duration28 / 60.0, 1) if duration28 is not None else None,
            "sleep_duration_vs_28d_min": round((latest_duration - duration28) / 60.0, 1) if latest_duration is not None and duration28 is not None else None,
            "sleep_duration_variability_28d_min": round(duration_sd28, 1) if duration_sd28 is not None else None,
            "bedtime_variability_28d_min": round(bedtime_sd, 1) if bedtime_sd is not None else None,
            "wake_time_variability_28d_min": round(waketime_sd, 1) if waketime_sd is not None else None,
            "sleep_midpoint_variability_28d_min": round(midpoint_sd, 1) if midpoint_sd is not None else None,
            "sleep_deficit_7d_min": round(deficit7, 1) if deficit7 is not None else None,
            "sleep_deficit_nightly_series": nightly_deficit_series,
            "nights_below_7h_7d": nights_below7_7,
            "nights_below_7h_28d": nights_below7_28,
            "nights_below_7h_28d_percent": round(below7_pct28, 1) if below7_pct28 is not None else None,
            "sleep_hrv_7d_mean_ms": round(hrv7, 1) if hrv7 is not None else None,
            "sleep_hrv_28d_mean_ms": round(hrv28, 1) if hrv28 is not None else None,
            "sleep_hrv_baseline_28d_mean_ms": round(hrv28, 1) if hrv28 is not None else None,
            "sleep_hrv_baseline_nights": len(prior_hrv_28),
            "sleep_hrv_latest_vs_28d_percent": round(latest_hrv_vs_baseline, 1) if latest_hrv_vs_baseline is not None else None,
            "sleep_hrv_7d_vs_baseline_percent": round(hrv_recent_vs_baseline, 1) if hrv_recent_vs_baseline is not None else None,
            # Backward-compatible key: now uses the less noisy recent weekly
            # signal when available, otherwise the latest-night deviation.
            "sleep_hrv_vs_28d_percent": round(
                hrv_recent_vs_baseline if hrv_recent_vs_baseline is not None else latest_hrv_vs_baseline, 1
            ) if (hrv_recent_vs_baseline is not None or latest_hrv_vs_baseline is not None) else None,
        }

    def recorder_long_term_evaluation(self) -> dict[str, Any]:
        """Derive transparent trends from validated canonical Fitness history."""
        def stat(metric: str) -> dict[str, Any]:
            value = self.long_term_statistics.get(metric)
            return value if isinstance(value, dict) else {}

        provider = collect_provider_metrics(self.hass, self.config)
        resting_stats = stat("resting_hr")
        vo2_stats = stat("vo2max")
        current_resting = provider.get("resting_hr") or self.input_value(CONF_RESTING_HR)
        current_vo2 = provider.get("vo2max") or self.input_value(CONF_VO2MAX)

        resting_7 = resting_stats.get("mean_7d") if resting_stats.get("days_7d", 0) >= 5 else None
        resting_28 = resting_stats.get("mean_28d") if resting_stats.get("days_28d", 0) >= 21 else None
        vo2_28 = vo2_stats.get("mean_28d") if vo2_stats.get("days_28d", 0) >= 21 else None
        vo2_90 = vo2_stats.get("mean_90d") if vo2_stats.get("days_90d", 0) >= 60 else None
        vo2_short = vo2_stats.get("trend_14_vs_previous_14_percent")
        vo2_slope = vo2_stats.get("slope_percent_per_30d") if vo2_stats.get("days_90d", 0) >= 30 else None

        return {
            "resting_hr_current": current_resting,
            "resting_hr_7d_mean": resting_7,
            "resting_hr_28d_mean": resting_28,
            "resting_hr_vs_28d": round(float(current_resting) - float(resting_28), 1) if current_resting is not None and resting_28 is not None else None,
            "vo2max_current": current_vo2,
            "vo2max_28d_mean": vo2_28,
            "vo2max_90d_mean": vo2_90,
            "vo2max_trend_14_vs_previous_14_percent": vo2_short,
            "vo2max_slope_percent_per_30d": vo2_slope,
            "vo2max_days_28d": vo2_stats.get("days_28d", 0),
            "vo2max_days_90d": vo2_stats.get("days_90d", 0),
            "vo2max_daily": vo2_stats.get("daily", []),
            "resting_hr_days_28d": resting_stats.get("days_28d", 0),
            "resting_hr_daily": resting_stats.get("daily", []),
        }

    @staticmethod
    def _readiness_clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, float(value)))

    def recovery_time_evaluation(self) -> dict[str, Any]:
        if self._recovery_time_cache is not None:
            return self._recovery_time_cache
        """Estimate readiness timing for the next workout.

        The state answers a practical planning question: approximately how many
        hours remain until the user is likely recovered enough for another
        workout of meaningful training value. It is intentionally not a claim
        that every physiological system has fully returned to baseline.

        The estimate combines the latest canonical workout dose with available
        longitudinal recovery signals. Session-RPE/TRIMP are treated as evidence
        about one recovery demand rather than as competing independent clocks.
        """
        latest = self.latest_workout()
        if latest is None or not latest.start:
            return {
                "remaining_hours": None,
                "reason": "no_completed_workout",
                "confidence_percent": 0,
                "data_source": "fitness_canonical_workout_history",
                "method": "fitness_next_workout_recovery_estimate_v2",
                "diagnostic_interpretation": False,
            }

        start = _dt(latest.start)
        if start is None:
            return {
                "remaining_hours": None,
                "reason": "invalid_workout_time",
                "confidence_percent": 0,
                "data_source": "fitness_canonical_workout_history",
                "method": "fitness_next_workout_recovery_estimate_v2",
                "diagnostic_interpretation": False,
            }

        end = _dt(latest.end)
        if end is None:
            end = start + timedelta(seconds=float(latest.duration_s or 0))
        now = datetime.now(timezone.utc)
        elapsed_h = max(0.0, (now - end).total_seconds() / 3600.0)
        duration_min = max(0.0, float(latest.duration_s or 0) / 60.0)

        evidence: dict[str, Any] = {}
        demand_components: dict[str, float] = {}
        confidence = 25.0

        # A modest universal starting point: even a short workout has an acute
        # recovery cost, but duration alone should not dictate the entire clock.
        central_hours = 10.0

        if duration_min > 0:
            duration_component = min(10.0, 0.135 * duration_min)
            central_hours += duration_component
            demand_components["duration"] = round(duration_component, 1)
            evidence["duration_minutes"] = round(duration_min, 1)
            confidence += 10.0

        rpe = None
        if latest.session_rpe is not None:
            rpe = max(1.0, min(10.0, float(latest.session_rpe)))
            rpe_component = max(0.0, rpe - 3.0) * 1.7
            central_hours += rpe_component
            demand_components["session_rpe"] = round(rpe_component, 1)
            evidence["session_rpe"] = int(round(rpe))
            confidence += 20.0

        # sRPE already contains duration and perceived effort. Use it only as a
        # bounded refinement, not as a second full recovery-time equation.
        if latest.session_rpe_load is not None:
            rpe_load = max(0.0, float(latest.session_rpe_load))
            srpe_component = min(4.0, rpe_load / 180.0)
            central_hours += srpe_component
            demand_components["session_rpe_load"] = round(srpe_component, 1)
            evidence["session_rpe_load"] = round(rpe_load, 1)
            confidence += 10.0

        # TRIMP is another internal-load signal; again it refines rather than
        # independently setting the recovery clock.
        if latest.banister_trimp is not None:
            trimp = max(0.0, float(latest.banister_trimp))
            trimp_component = min(4.0, trimp / 30.0)
            central_hours += trimp_component
            demand_components["banister_trimp"] = round(trimp_component, 1)
            evidence["banister_trimp"] = round(trimp, 1)
            confidence += 8.0

        vigorous_min = float(latest.time_vigorous_s or 0) / 60.0
        near_max_min = float(latest.time_near_maximal_s or 0) / 60.0
        if vigorous_min > 0 or near_max_min > 0:
            intensity_component = min(6.0, 0.10 * vigorous_min + 0.35 * near_max_min)
            central_hours += intensity_component
            demand_components["high_intensity_time"] = round(intensity_component, 1)
            evidence["vigorous_minutes"] = round(vigorous_min, 1)
            evidence["near_maximal_minutes"] = round(near_max_min, 1)
            confidence += 7.0

        sport = str(latest.sport or "").strip().lower()
        resistance_training = any(
            token in sport for token in ("strength", "weight", "resistance")
        )
        if resistance_training:
            # Resistance exercise can leave neuromuscular/muscular recovery
            # requirements that are not fully represented by autonomic signals.
            strength_component = 4.0
            if rpe is not None and rpe >= 8:
                strength_component += 4.0
            central_hours += strength_component
            demand_components["resistance_training"] = round(strength_component, 1)
            evidence["resistance_training"] = True

        # Personal recovery signals can move the estimate, but are deliberately
        # bounded because no single HRV/RHR/readiness marker proves complete
        # muscular, metabolic or connective-tissue recovery.
        readiness = self.readiness_evaluation()
        sleep = self.sleep_long_term_summary()
        recorder = self.recorder_long_term_evaluation()
        workout_long = self.workout_long_term_summary()

        adjustment = 1.0
        modifiers: list[dict[str, Any]] = []
        recovery_signals: dict[str, str] = {}

        ready = readiness.get("score")
        if ready is not None:
            ready = float(ready)
            evidence["readiness_score"] = round(ready, 1)
            confidence += 10.0
            if ready < 35:
                adjustment += 0.15
                modifiers.append({"signal": "low_readiness", "factor": 1.15})
            elif ready < 50:
                adjustment += 0.08
                modifiers.append({"signal": "reduced_readiness", "factor": 1.08})
            elif ready >= 85:
                adjustment -= 0.06
                modifiers.append({"signal": "high_readiness", "factor": 0.94})
            elif ready >= 70:
                adjustment -= 0.03
                modifiers.append({"signal": "supportive_readiness", "factor": 0.97})

        hrv_delta = sleep.get("sleep_hrv_7d_vs_baseline_percent")
        if hrv_delta is None:
            recovery_signals["hrv"] = "insufficient_data"
        else:
            hrv_delta = float(hrv_delta)
            evidence["hrv_7d_vs_baseline_percent"] = round(hrv_delta, 1)
            confidence += 8.0
            if hrv_delta <= -10:
                recovery_signals["hrv"] = "below_baseline"
                adjustment += 0.10
                modifiers.append({"signal": "hrv_below_baseline", "factor": 1.10})
            elif hrv_delta <= -5:
                recovery_signals["hrv"] = "slightly_below_baseline"
                adjustment += 0.04
                modifiers.append({"signal": "hrv_slightly_below_baseline", "factor": 1.04})
            elif hrv_delta >= 5:
                recovery_signals["hrv"] = "above_baseline"
                adjustment -= 0.03
                modifiers.append({"signal": "hrv_above_baseline", "factor": 0.97})
            else:
                recovery_signals["hrv"] = "near_baseline"

        rhr_delta = recorder.get("resting_hr_vs_28d")
        if rhr_delta is None:
            recovery_signals["resting_hr"] = "insufficient_data"
        else:
            rhr_delta = float(rhr_delta)
            evidence["resting_hr_vs_28d_bpm"] = round(rhr_delta, 1)
            confidence += 7.0
            if rhr_delta >= 5:
                recovery_signals["resting_hr"] = "above_baseline"
                adjustment += 0.08
                modifiers.append({"signal": "resting_hr_elevated", "factor": 1.08})
            elif rhr_delta >= 3:
                recovery_signals["resting_hr"] = "slightly_above_baseline"
                adjustment += 0.04
                modifiers.append({"signal": "resting_hr_slightly_elevated", "factor": 1.04})
            elif rhr_delta <= -2:
                recovery_signals["resting_hr"] = "supportive"
                adjustment -= 0.02
                modifiers.append({"signal": "resting_hr_supportive", "factor": 0.98})
            else:
                recovery_signals["resting_hr"] = "near_baseline"

        hrr_delta = workout_long.get("hrr_60s_latest_vs_90d_bpm")
        if hrr_delta is None:
            recovery_signals["hrr"] = "insufficient_data"
        else:
            hrr_delta = float(hrr_delta)
            evidence["hrr_60s_vs_personal_baseline_bpm"] = round(hrr_delta, 1)
            confidence += 5.0
            if hrr_delta <= -5:
                recovery_signals["hrr"] = "below_baseline"
                adjustment += 0.05
                modifiers.append({"signal": "hrr_below_baseline", "factor": 1.05})
            elif hrr_delta >= 5:
                recovery_signals["hrr"] = "above_baseline"
                adjustment -= 0.02
                modifiers.append({"signal": "hrr_above_baseline", "factor": 0.98})
            else:
                recovery_signals["hrr"] = "near_baseline"

        sleep_component = (readiness.get("components") or {}).get("sleep") or {}
        sleep_component_score = sleep_component.get("score")
        if sleep_component_score is None:
            recovery_signals["sleep"] = "insufficient_data"
        else:
            sleep_component_score = float(sleep_component_score)
            evidence["sleep_recovery_score"] = round(sleep_component_score, 1)
            if sleep_component_score >= 75:
                recovery_signals["sleep"] = "supportive"
            elif sleep_component_score < 50:
                recovery_signals["sleep"] = "reduced"
            else:
                recovery_signals["sleep"] = "neutral"

        adjustment = max(0.82, min(1.30, adjustment))
        central_hours = max(8.0, min(60.0, central_hours * adjustment))

        # A range is more honest than a single exact physiological clock. The
        # central estimate drives planning; the range communicates uncertainty.
        range_fraction = 0.16 if confidence >= 80 else 0.22 if confidence >= 60 else 0.28
        low_hours = max(6.0, central_hours * (1.0 - range_fraction))
        high_hours = min(72.0, central_hours * (1.0 + range_fraction))

        remaining = max(0.0, central_hours - elapsed_h)
        progress = 100.0 if central_hours <= 0 else max(
            0.0, min(100.0, elapsed_h / central_hours * 100.0)
        )
        ready_at = end + timedelta(hours=central_hours)

        if remaining <= 0:
            level = "ready"
        elif remaining <= 6:
            level = "nearly_ready"
        elif remaining <= 18:
            level = "recovering"
        elif remaining <= 36:
            level = "substantial_recovery"
        else:
            level = "high_recovery_demand"

        limiting_factor = "workout_dose"
        if resistance_training:
            limiting_factor = "muscular_recovery"
        if recovery_signals.get("hrv") == "below_baseline":
            limiting_factor = "autonomic_recovery"
        if recovery_signals.get("sleep") == "reduced":
            limiting_factor = "sleep_recovery"
        if ready is not None and ready < 35:
            limiting_factor = "overall_readiness"

        result = {
            "remaining_hours": round(remaining, 1),
            "ready_for_next_workout_at": ready_at.isoformat(),
            # Backward-compatible alias retained for existing automations/UI
            # while v2 uses estimated_recovery_hours as the canonical name.
            "estimated_total_recovery_hours": round(central_hours, 1),
            "estimated_recovery_hours": round(central_hours, 1),
            "estimated_recovery_low_hours": round(low_hours, 1),
            "estimated_recovery_high_hours": round(high_hours, 1),
            "elapsed_hours_since_workout": round(elapsed_h, 1),
            "recovery_progress_percent": round(progress, 0),
            "level": level,
            "confidence_percent": round(min(100.0, confidence), 0),
            "limiting_factor": limiting_factor,
            "recovery_signals": recovery_signals,
            "last_workout_start": latest.start,
            "last_workout_end": end.isoformat(),
            "sport": latest.sport,
            "evidence": evidence,
            "workout_demand_components_hours": demand_components,
            "recovery_modifiers": modifiers,
            "data_source": "fitness_canonical_workout_and_recovery_history",
            "method": "fitness_next_workout_recovery_estimate_v2",
            "formula": (
                "bounded workout-dose model (duration + RPE + bounded sRPE/TRIMP "
                "+ intensity + sport context) × bounded personal recovery adjustment; "
                "remaining time = central estimate − elapsed time"
            ),
            "planning_interpretation": "ready_for_next_workout_estimate",
            "physiological_recovery_interpretation": "available_markers_only",
            "full_physiological_recovery_claimed": False,
            "diagnostic_interpretation": False,
        }
        self._recovery_time_cache = result
        return result

    def readiness_evaluation(self) -> dict[str, Any]:
        if self._readiness_cache is not None:
            return self._readiness_cache
        """Return a transparent Fitness-owned 0-100 training readiness score.

        Every component uses normalized/merged Fitness data. Missing components
        are omitted and the remaining weights are renormalized. The score is
        unavailable until at least two independent domains are present, including
        sleep or autonomic recovery evidence.
        """
        now = datetime.now(timezone.utc)
        sleep = self.sleep_long_term_summary()
        workout = self.workout_long_term_summary()
        longitudinal = self.recorder_long_term_evaluation()
        latest_sleep = self.latest_sleep()
        latest_workout = self.latest_workout()

        components: dict[str, dict[str, Any]] = {}

        def add_component(key: str, score: float | None, base_weight: float, evidence: dict[str, Any]):
            if score is None:
                return
            clean_evidence = {k: v for k, v in evidence.items() if v is not None}
            components[key] = {
                "score": round(self._readiness_clamp(score), 1),
                "base_weight": base_weight,
                "evidence": clean_evidence,
            }

        # Autonomic recovery: personal HRV and resting-HR deviation from the
        # user's own validated rolling baseline. No population cutoff is used.
        autonomic_parts: list[float] = []
        hrv_vs = sleep.get("sleep_hrv_vs_28d_percent")
        if hrv_vs is not None:
            autonomic_parts.append(self._readiness_clamp(70.0 + float(hrv_vs) * 3.0, 20.0, 100.0))
        rhr_vs = longitudinal.get("resting_hr_vs_28d")
        if rhr_vs is not None:
            autonomic_parts.append(self._readiness_clamp(78.0 - float(rhr_vs) * 7.0, 20.0, 100.0))
        add_component(
            "autonomic",
            mean(autonomic_parts) if autonomic_parts else None,
            0.30,
            {
                "sleep_hrv_latest_ms": getattr(latest_sleep, "hrv_ms", None) if latest_sleep else None,
                "sleep_hrv_28d_mean_ms": sleep.get("sleep_hrv_28d_mean_ms"),
                "sleep_hrv_vs_28d_percent": hrv_vs,
                "resting_hr_current_bpm": longitudinal.get("resting_hr_current"),
                "resting_hr_28d_mean_bpm": longitudinal.get("resting_hr_28d_mean"),
                "resting_hr_vs_28d_bpm": rhr_vs,
            },
        )

        # Sleep recovery: current merged sleep plus validated recent sleep
        # history. Provider-specific scores, when present, are only one optional
        # input inside the merged Fitness sleep record.
        sleep_parts: list[float] = []
        duration_h = None
        if latest_sleep and latest_sleep.duration_s is not None:
            duration_h = float(latest_sleep.duration_s) / 3600.0
            if duration_h < 4.0:
                duration_score = 20.0
            elif duration_h < 7.0:
                duration_score = 20.0 + (duration_h - 4.0) / 3.0 * 80.0
            elif duration_h <= 9.0:
                duration_score = 100.0
            elif duration_h <= 10.0:
                duration_score = 100.0 - (duration_h - 9.0) * 10.0
            else:
                duration_score = 90.0
            sleep_parts.append(duration_score)
        merged_sleep_score = getattr(latest_sleep, "score", None) if latest_sleep else None
        if merged_sleep_score is not None:
            sleep_parts.append(self._readiness_clamp(float(merged_sleep_score)))
        deficit = sleep.get("sleep_deficit_7d_min")
        if deficit is not None:
            sleep_parts.append(self._readiness_clamp(100.0 - float(deficit) / 420.0 * 80.0, 20.0, 100.0))
        midpoint_sd = sleep.get("sleep_midpoint_variability_28d_min")
        if midpoint_sd is not None:
            sleep_parts.append(self._readiness_clamp(110.0 - float(midpoint_sd) * 0.5, 20.0, 100.0))
        add_component(
            "sleep",
            mean(sleep_parts) if sleep_parts else None,
            0.30,
            {
                "last_sleep_duration_h": round(duration_h, 2) if duration_h is not None else None,
                "merged_sleep_score": merged_sleep_score,
                "sleep_deficit_7d_min": deficit,
                "sleep_midpoint_variability_28d_min": midpoint_sd,
                "nights_7d": sleep.get("nights_7d"),
                "nights_28d": sleep.get("nights_28d"),
            },
        )

        # Training recovery: time since the last canonical workout, recent
        # personal load relative to the user's 28-day weekly equivalent, and
        # the last workout's own TRIMP when available.
        training_score = None
        hours_since = None
        latest_trimp = None
        recent_load = workout.get("banister_trimp_7d")
        baseline_load = workout.get("banister_trimp_28d_weekly_equivalent")
        load_ratio = None
        if latest_workout and latest_workout.start:
            start = _dt(latest_workout.start)
            if start is not None:
                end = _dt(latest_workout.end) or (start + timedelta(seconds=float(latest_workout.duration_s or 0)))
                hours_since = max(0.0, (now - end).total_seconds() / 3600.0)
                if hours_since < 6:
                    training_score = 30.0
                elif hours_since < 12:
                    training_score = 45.0
                elif hours_since < 24:
                    training_score = 65.0
                elif hours_since < 36:
                    training_score = 82.0
                elif hours_since < 48:
                    training_score = 90.0
                else:
                    training_score = 96.0
            latest_trimp = latest_workout.banister_trimp
        if training_score is not None and latest_trimp is not None:
            if float(latest_trimp) >= 150:
                training_score -= 18.0
            elif float(latest_trimp) >= 100:
                training_score -= 10.0
            elif float(latest_trimp) >= 60:
                training_score -= 4.0
        if recent_load is not None and baseline_load not in (None, 0):
            load_ratio = float(recent_load) / float(baseline_load)
            if training_score is None:
                training_score = 82.0
            if load_ratio >= 1.6:
                training_score -= 18.0
            elif load_ratio >= 1.3:
                training_score -= 10.0
            elif load_ratio >= 1.1:
                training_score -= 4.0
            elif load_ratio < 0.75:
                training_score += 4.0
        add_component(
            "training",
            training_score,
            0.25,
            {
                "hours_since_last_workout": round(hours_since, 1) if hours_since is not None else None,
                "last_workout_trimp": round(float(latest_trimp), 1) if latest_trimp is not None else None,
                "trimp_7d": recent_load,
                "trimp_28d_weekly_equivalent": baseline_load,
                "recent_to_baseline_load_ratio": round(load_ratio, 3) if load_ratio is not None else None,
                "workouts_7d": workout.get("workouts_7d"),
            },
        )

        # Post-exercise recovery response: only personal HRR comparison is used;
        # without a personal baseline this optional component remains absent.
        hrr_delta = workout.get("hrr_60s_latest_vs_90d_bpm")
        recovery_score = None
        if hrr_delta is not None:
            recovery_score = self._readiness_clamp(75.0 + float(hrr_delta) * 2.5, 25.0, 100.0)
        add_component(
            "recovery_response",
            recovery_score,
            0.15,
            {
                "latest_hrr_60s_bpm": workout.get("latest_hrr_60s"),
                "hrr_60s_personal_baseline_bpm": workout.get("hrr_60s_baseline_90d"),
                "hrr_60s_latest_vs_baseline_bpm": hrr_delta,
                "hrr_samples_90d": workout.get("hrr_samples_90d"),
            },
        )

        available = list(components)
        required_domain_present = "sleep" in components or "autonomic" in components
        if len(available) < 2 or not required_domain_present:
            return {
                "score": None,
                "level": "insufficient_data",
                "confidence_percent": round(sum(item["base_weight"] for item in components.values()) * 100.0, 0),
                "components_available": available,
                "available_components": available,
                "components": components,
                "reason": "insufficient_evidence",
                "data_source": "fitness_canonical_recovery_data",
                "updated_at": now.isoformat(),
            }

        weight_total = sum(item["base_weight"] for item in components.values())
        score = sum(item["score"] * item["base_weight"] for item in components.values()) / weight_total
        score = round(self._readiness_clamp(score), 1)
        for item in components.values():
            item["effective_weight_percent"] = round(item["base_weight"] / weight_total * 100.0, 1)

        if score >= 85:
            level = "excellent"
        elif score >= 70:
            level = "high"
        elif score >= 50:
            level = "moderate"
        elif score >= 30:
            level = "low"
        else:
            level = "very_low"

        result = {
            "score": score,
            "level": level,
            "confidence_percent": round(weight_total * 100.0, 0),
            "components_available": available,
            "available_components": available,
            "components": components,
            "reason": None,
            "data_source": "fitness_canonical_recovery_data",
            "updated_at": now.isoformat(),
            "formula": "weighted mean of available Fitness recovery domains; base weights autonomic 30%, sleep 30%, training recovery 25%, post-exercise recovery response 15%; missing domains are omitted and weights are renormalized",
        }
        self._readiness_cache = result
        return result

    @staticmethod
    def _pearson_correlation(pairs: list[tuple[float, float]]) -> float | None:
        if len(pairs) < 6:
            return None
        xs = [x for x, _ in pairs]
        ys = [y for _, y in pairs]
        xbar, ybar = mean(xs), mean(ys)
        sx = sum((x - xbar) ** 2 for x in xs)
        sy = sum((y - ybar) ** 2 for y in ys)
        if sx <= 0 or sy <= 0:
            return None
        return sum((x - xbar) * (y - ybar) for x, y in pairs) / math.sqrt(sx * sy)

    def training_recovery_relationship_summary(self) -> dict[str, Any]:
        """Describe personal association between workout TRIMP and next sleep."""
        now = datetime.now(timezone.utc)
        workouts = []
        for workout in self.local_workouts():
            if workout.banister_trimp is None or not workout.start:
                continue
            start = _dt(workout.start)
            if start is None or (now - start).total_seconds() > 90 * 86400:
                continue
            end = _dt(workout.end)
            if end is None:
                end = start + timedelta(seconds=float(workout.duration_s or 0))
            workouts.append((end, float(workout.banister_trimp)))
        workouts.sort(key=lambda item: item[0])

        duration_pairs: list[tuple[float, float]] = []
        hrv_pairs: list[tuple[float, float]] = []
        used_workout_ends: set[str] = set()
        for sleep in self._sleep_records_from_history():
            sleep_start = _dt(sleep.start)
            if sleep_start is None or (now - sleep_start).total_seconds() > 90 * 86400:
                continue
            candidates = [(end, load) for end, load in workouts if 0 <= (sleep_start - end).total_seconds() <= 18 * 3600]
            if not candidates:
                continue
            end, load = candidates[-1]
            key = end.isoformat()
            if key in used_workout_ends:
                continue
            used_workout_ends.add(key)
            if sleep.duration_s is not None:
                duration_pairs.append((load, float(sleep.duration_s) / 60.0))
            if sleep.hrv_ms is not None:
                hrv_pairs.append((load, float(sleep.hrv_ms)))

        sleep_r = self._pearson_correlation(duration_pairs)
        hrv_r = self._pearson_correlation(hrv_pairs)
        primary = sleep_r if sleep_r is not None else hrv_r
        return {
            "primary_correlation": round(primary, 3) if primary is not None else None,
            "primary_measure": "next_sleep_duration" if sleep_r is not None else ("next_sleep_hrv" if hrv_r is not None else None),
            "trimp_vs_next_sleep_duration_r": round(sleep_r, 3) if sleep_r is not None else None,
            "trimp_vs_next_sleep_hrv_r": round(hrv_r, 3) if hrv_r is not None else None,
            "sleep_duration_pairs": len(duration_pairs),
            "sleep_hrv_pairs": len(hrv_pairs),
            "window_days": 90,
        }

    def _profile_input_provenance(
        self,
        config_key: str,
        quantity: str,
    ) -> dict[str, Any]:
        """Describe one configured number/entity without changing its value."""
        resolved = resolve_number_or_entity(
            self.hass,
            self.config.get(config_key),
            quantity=quantity,
        )
        if resolved.value is None:
            return {}
        result = {
            "role": config_key,
            "source_type": resolved.source,
            "value_used": resolved.value,
        }
        if resolved.entity_id:
            result.update(
                {
                    "entity_id": resolved.entity_id,
                    "raw_value": resolved.original_value,
                    "raw_unit": resolved.original_unit,
                    "normalized_unit": resolved.canonical_unit,
                }
            )
        else:
            result["configured_value"] = resolved.original_value
        return result

    def _provider_metric_provenance(
        self,
        provider: dict[str, Any],
        key: str,
        *,
        role: str | None = None,
    ) -> dict[str, Any]:
        """Describe one normalized provider metric and its HA source entity."""
        value = provider.get(key)
        entity_id = provider.get(f"{key}_entity")
        if value is None and not entity_id:
            return {}
        result = {
            "role": role or key,
            "source_type": "provider_entity",
            "value_used": value,
        }
        if entity_id:
            result["entity_id"] = entity_id
            state = self.hass.states.get(entity_id)
            if state is not None:
                result["raw_value"] = state.state
                result["raw_unit"] = state.attributes.get(
                    "unit_of_measurement"
                )
        return result

    def evaluation_provenance(self, metric: str) -> dict[str, Any]:
        """Return concrete, deterministic provenance for an evaluation metric."""
        e = self.evaluation()
        provider = e.get("provider_metrics") or {}
        inputs: list[dict[str, Any]] = []

        def add(item):
            if item:
                inputs.append(item)

        def profile(key, quantity, role=None):
            item = self._profile_input_provenance(key, quantity)
            if item and role:
                item["role"] = role
            return item

        def provider_item(key, role=None):
            return self._provider_metric_provenance(
                provider,
                key,
                role=role,
            )

        if metric == "age":
            inputs.extend(
                [
                    {
                        "role": "date_of_birth",
                        "source_type": "profile_configuration",
                        "configured_value": (
                            f"{self.config.get(CONF_BIRTH_YEAR):04d}-"
                            f"{self.config.get(CONF_BIRTH_MONTH):02d}-"
                            f"{self.config.get(CONF_BIRTH_DAY):02d}"
                            if all(
                                self.config.get(key) is not None
                                for key in (
                                    CONF_BIRTH_YEAR,
                                    CONF_BIRTH_MONTH,
                                    CONF_BIRTH_DAY,
                                )
                            )
                            else None
                        ),
                    }
                ]
            )
            return {
                "value_origin": "calculated_from_profile",
                "formula": "age = completed years between date_of_birth and today",
                "input_sources": inputs,
            }

        if metric == "weight":
            item = provider_item("weight_kg", "weight")
            if not item:
                item = profile(CONF_WEIGHT, "weight", "weight")
            add(item)
            return {
                "value_origin": "provider_or_profile_input",
                "formula": "direct normalized body-mass value; no derived Fitness formula",
                "input_sources": inputs,
            }

        if metric == "resting_hr":
            item = provider_item("resting_hr", "resting_hr")
            if not item:
                item = profile(CONF_RESTING_HR, "heart_rate", "resting_hr")
            add(item)
            return {
                "value_origin": "provider_or_profile_input",
                "formula": "direct resting-HR value; no derived Fitness formula",
                "input_sources": inputs,
            }

        if metric == "max_hr":
            manual = profile(CONF_MAX_HR, "heart_rate", "configured_max_hr")
            latest = self.latest_workout()
            if e.get("max_hr_method") == "observed_workout_peak" and latest:
                add(
                    {
                        "role": "maximum_hr",
                        "source_type": "completed_workout_observation",
                        "value_used": latest.max_hr,
                        "workout_source": latest.source,
                        "workout_start": latest.start,
                    }
                )
                formula = "max(configured_or_Tanaka_max_hr, observed_latest_workout_peak)"
                origin = "observed_workout_peak"
            elif manual:
                add(manual)
                formula = "configured maximum HR used directly"
                origin = "configured_input"
            else:
                add(
                    {
                        "role": "age",
                        "source_type": "profile_age",
                        "value_used": self.age(),
                    }
                )
                formula = "Tanaka et al. 2001: maximum_hr = 208 − 0.7 × age"
                origin = "tanaka_2001_prediction"
            return {
                "value_origin": origin,
                "formula": formula,
                "input_sources": inputs,
            }

        if metric == "heart_rate_reserve":
            max_info = self.evaluation_provenance("max_hr")
            rest_info = self.evaluation_provenance("resting_hr")
            inputs.extend(max_info.get("input_sources") or [])
            inputs.extend(rest_info.get("input_sources") or [])
            return {
                "value_origin": "fitness_calculation",
                "formula": "heart_rate_reserve = maximum_hr − resting_hr",
                "input_sources": inputs,
            }

        if metric == "vo2max":
            item = provider_item("vo2max", "vo2max")
            if not item:
                item = profile(CONF_VO2MAX, "vo2max", "vo2max")
            if item:
                add(item)
                return {
                    "value_origin": "provider_or_profile_input",
                    "formula": "direct normalized VO₂max value; no Fitness estimation",
                    "input_sources": inputs,
                }
            max_info = self.evaluation_provenance("max_hr")
            rest_info = self.evaluation_provenance("resting_hr")
            inputs.extend(max_info.get("input_sources") or [])
            inputs.extend(rest_info.get("input_sources") or [])
            return {
                "value_origin": "uth_2004_estimate",
                "formula": "Uth et al. 2004: VO₂max = 15.3 × maximum_hr / resting_hr",
                "input_sources": inputs,
                "method_caveat": (
                    "Uth 2004 was validated in well-trained men; Fitness exposes "
                    "the provenance when used outside that population."
                ),
            }

        if metric == "friend_predicted_vo2max":
            weight_info = self.evaluation_provenance("weight")
            inputs.extend(weight_info.get("input_sources") or [])
            add(
                {
                    "role": "age",
                    "source_type": "profile_age",
                    "value_used": self.age(),
                }
            )
            add(
                {
                    "role": "sex",
                    "source_type": "profile_configuration",
                    "configured_value": self.config.get(CONF_SEX),
                }
            )
            return {
                "value_origin": "friend_2017_reference_equation",
                "formula": (
                    "FRIEND 2017: 79.9 − 0.39×age − 13.7×gender "
                    "− 0.127×weight_lb; gender male=0, female=1"
                ),
                "input_sources": inputs,
            }

        if metric in ("vo2max_percent_predicted", "cardiorespiratory_status"):
            measured = self.evaluation_provenance("vo2max")
            predicted = self.evaluation_provenance(
                "friend_predicted_vo2max"
            )
            inputs.extend(measured.get("input_sources") or [])
            inputs.extend(predicted.get("input_sources") or [])
            formula = (
                "percent_predicted = measured_vo2max / FRIEND_predicted_vo2max × 100"
            )
            if metric == "cardiorespiratory_status":
                formula += (
                    "; display only: <90 below_reference, 90–110 around_reference, "
                    ">110 above_reference"
                )
            return {
                "value_origin": "fitness_reference_comparison",
                "formula": formula,
                "input_sources": inputs,
            }

        if metric in ("hrv_weekly", "hrv_last_night"):
            key = "hrv_weekly" if metric == "hrv_weekly" else "hrv_last_night"
            add(provider_item(key, metric))
            return {
                "value_origin": "provider_metric",
                "formula": "provider value exposed directly; Fitness does not recalculate HRV",
                "input_sources": inputs,
            }

        if metric == "hrv_status":
            add(provider_item("hrv_last_night", "nightly_hrv"))
            hrv_entity = provider.get("hrv_provider_status_entity")
            add(
                {
                    "role": "personal_hrv_baseline",
                    "source_type": "provider_entity_attributes",
                    "entity_id": hrv_entity,
                    "baseline_low": provider.get("hrv_baseline_low"),
                    "baseline_high": provider.get("hrv_baseline_high"),
                }
                if hrv_entity or provider.get("hrv_baseline_low") is not None
                else {}
            )
            return {
                "value_origin": "fitness_personal_baseline_comparison",
                "formula": (
                    "nightly_hrv < baseline_low → below; "
                    "nightly_hrv > baseline_high → above; otherwise within baseline"
                ),
                "input_sources": inputs,
            }

        if metric == "threshold_hr":
            item = provider_item("threshold_hr", "threshold_hr")
            if not item:
                item = profile("threshold_hr", "heart_rate", "threshold_hr")
            add(item)
            return {
                "value_origin": "provider_or_profile_threshold",
                "formula": "threshold HR used directly; Fitness does not estimate a physiological threshold",
                "input_sources": inputs,
            }

        if metric == "threshold_pace":
            item = profile("threshold_pace", "pace", "threshold_pace")
            if item:
                add(item)
                return {
                    "value_origin": "profile_threshold_pace",
                    "formula": "configured/entity pace normalized to min/km",
                    "input_sources": inputs,
                }
            item = provider_item("threshold_speed", "threshold_speed")
            add(item)
            return {
                "value_origin": "provider_threshold_speed_conversion",
                "formula": "threshold_pace_min_km = 1000 / threshold_speed_m_s / 60",
                "input_sources": inputs,
            }

        if metric == "threshold_power":
            item = provider_item("ftp_running", "running_ftp")
            if not item:
                item = profile("threshold_power", "power", "threshold_power")
            add(item)
            return {
                "value_origin": "provider_or_profile_threshold_power",
                "formula": "selected threshold/FTP power used directly; Fitness does not infer FTP",
                "input_sources": inputs,
            }

        if metric == "power_to_weight":
            item = provider_item(
                "power_to_weight_running",
                "provider_running_power_to_weight",
            )
            if item:
                add(item)
                return {
                    "value_origin": "provider_metric",
                    "formula": "provider power-to-weight value used directly",
                    "input_sources": inputs,
                }
            power_info = self.evaluation_provenance("threshold_power")
            weight_info = self.evaluation_provenance("weight")
            inputs.extend(power_info.get("input_sources") or [])
            inputs.extend(weight_info.get("input_sources") or [])
            return {
                "value_origin": "fitness_calculation",
                "formula": "threshold_power_to_weight = threshold_power_w / body_mass_kg",
                "input_sources": inputs,
            }

        provider_direct = {
            "fitness_age": "fitness_age",
            "training_readiness": "training_readiness",
            "sleep_score": "sleep_score",
            "provider_training_status": "provider_training_status",
        }
        if metric in provider_direct:
            key = provider_direct[metric]
            add(provider_item(key, metric))
            return {
                "value_origin": "provider_metric",
                "formula": "provider value exposed directly; provider algorithm may be proprietary",
                "input_sources": inputs,
            }

        if metric == "fitness_age_difference":
            add(provider_item("fitness_age", "fitness_age"))
            add(
                {
                    "role": "chronological_age",
                    "source_type": "profile_age",
                    "value_used": self.age(),
                }
            )
            return {
                "value_origin": "fitness_calculation_from_provider_context",
                "formula": "fitness_age_difference = provider_fitness_age − chronological_age",
                "input_sources": inputs,
            }

        if metric in ("acute_load", "chronic_load", "acute_chronic_ratio"):
            status_entity = provider.get(
                "provider_training_status_entity"
            )
            add(
                {
                    "role": "provider_training_status",
                    "source_type": "provider_entity_attributes",
                    "entity_id": status_entity,
                    "acute_load": provider.get("acute_load"),
                    "chronic_load": provider.get("chronic_load"),
                    "provider_ratio": provider.get(
                        "acute_chronic_ratio"
                    ),
                }
                if status_entity else {}
            )
            return {
                "value_origin": (
                    "provider_metric_or_fitness_ratio"
                    if metric == "acute_chronic_ratio"
                    else "provider_metric"
                ),
                "formula": (
                    "provider ratio used when present; otherwise acute_load / chronic_load"
                    if metric == "acute_chronic_ratio"
                    else "provider training-status load value used directly"
                ),
                "input_sources": inputs,
            }

        history_formulas = {
            "training_load_7d": (
                "Σ(Banister_TRIMP for completed workouts during previous 7 days)"
            ),
            "training_load_28d": (
                "Σ(Banister_TRIMP for completed workouts during previous 28 days)"
            ),
            "training_load_change_7_vs_28": (
                "compare daily TRIMP rate over 7 days with daily TRIMP rate over 28 days"
            ),
            "training_days_28d": (
                "count(unique calendar days with a completed workout during previous 28 days)"
            ),
            "hrr_60s_long_term": (
                "mean(60-second post-exercise HR recovery over workouts in previous 90 days)"
            ),
            "hrr_60s_vs_90d": (
                "latest 60-second HR recovery minus prior 90-day mean HR recovery"
            ),
        }
        if metric in history_formulas:
            latest = self.latest_workout()
            add(
                {
                    "role": "completed_workout_history",
                    "source_type": "fitness_merged_workout_history",
                    "latest_workout_source": (
                        latest.source if latest else None
                    ),
                    "history_records_available": len(
                        self.local_workouts()
                    ),
                    "home_assistant_long_term_statistics_updated": (
                        self.long_term_statistics_updated
                    ),
                }
            )
            return {
                "value_origin": "fitness_history_aggregation",
                "formula": history_formulas[metric],
                "input_sources": inputs,
            }

        sleep_history_metrics = {
            "sleep_duration_7d_mean", "sleep_duration_28d_mean",
            "sleep_duration_vs_28d", "sleep_duration_shortfall",
            "sleep_midpoint_variability_14d", "sleep_hrv_7d_mean",
            "sleep_hrv_28d_mean", "sleep_hrv_vs_28d",
        }
        if metric in sleep_history_metrics:
            sleep = self.latest_sleep()
            add({
                "role": "merged_sleep_history",
                "source_type": "fitness_merged_sleep_history",
                "history_records_available": len(self._sleep_records_from_history()),
                "latest_sleep_sources": (
                    list(sleep.provider_domains) if sleep else []
                ),
            })
            return {
                "value_origin": "fitness_sleep_history_aggregation",
                "formula": "See method/calculation attributes; only merged, de-duplicated sleep records are used.",
                "input_sources": inputs,
            }

        recorder_metrics = {
            "resting_hr_7d_mean": "resting_hr",
            "resting_hr_28d_mean": "resting_hr",
            "resting_hr_vs_28d": "resting_hr",
            "vo2max_28d_mean": "vo2max",
            "vo2max_trend_14_vs_previous_14": "vo2max",
        }
        if metric in recorder_metrics:
            source_metric = recorder_metrics[metric]
            summary = self.long_term_statistics.get(source_metric) or {}
            add({
                "role": source_metric,
                "source_type": "home_assistant_recorder_long_term_statistics",
                "entity_id": summary.get("entity_id") if isinstance(summary, dict) else None,
                "statistics_updated": self.long_term_statistics_updated,
            })
            return {
                "value_origin": "home_assistant_long_term_statistics_history",
                "formula": "See method/calculation attributes; daily Recorder statistics are aggregated longitudinally.",
                "input_sources": inputs,
            }

        return {
            "value_origin": "fitness_evaluation",
            "formula": "See method/calculation attributes for deterministic evaluation logic.",
            "input_sources": inputs,
        }

    def localized_evaluation_provenance(self, metric: str) -> dict[str, Any]:
        """Add localized human-facing context without translating technical data."""
        result = dict(self.evaluation_provenance(metric))
        language = self._ai_language()
        origin = result.get("value_origin", "")
        if "provider" in origin:
            kind = "provider"
            note_key = "provider_note"
        elif "history" in origin:
            kind = "history"
            note_key = "history_note"
        elif origin in {"configured_input", "provider_or_profile_input", "profile_threshold_pace"}:
            kind = "direct"
            note_key = "direct_note"
        else:
            kind = "calculated"
            note_key = None
        result["origin_description"] = provenance_text(language, kind)
        result["data_sources_description"] = provenance_text(language, "sources")
        if note_key:
            result["provenance_note"] = provenance_text(language, note_key)
        return result

    def evaluation(self) -> dict:
        if self._evaluation_cache is None:
            self._evaluation_cache = self._build_evaluation()
        return self._evaluation_cache

    def _build_evaluation(self) -> dict:
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

        # Evaluation reference comparisons require a provider/user VO2max. Do not
        # manufacture a cardiorespiratory status from a fallback estimate.
        vo2 = provider.get("vo2max") or self.input_value(CONF_VO2MAX)
        vo2_method = "provider_or_user" if vo2 is not None else None

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

        workout_summary = self.workout_long_term_summary()
        sleep_summary = self.sleep_long_term_summary()
        recorder_summary = self.recorder_long_term_evaluation()
        readiness_summary = self.readiness_evaluation()

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
            "readiness": readiness_summary,
            "workout_long_term": workout_summary,
            "sleep_long_term": sleep_summary,
            "recorder_long_term": recorder_summary,
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
            "You are the interpretation layer of the Fitness Home Assistant integration, "
            "not a generic JSON/data analyst. Evaluate the person's overall fitness, training, "
            "sleep and recovery ONLY from the curated fitness evidence below. Return EXACTLY two parts. "
            "Never discuss Home Assistant internals, sensor configuration, JSON structure, data collection "
            "troubleshooting, or recommend checking integrations unless the evidence explicitly contains an "
            "input-quality warning. The first line must be "
            "`VERDICT: <short overall evaluation>`. The verdict must be a brief phrase "
            "such as Excellent, Good, Okay, Needs attention, or Insufficient data, "
            f"translated naturally into {output_language}. EVERY word intended for the user must be in "
            f"{output_language}; do not switch to English even if field names are English. Then write exactly ONE "
            "natural paragraph of roughly 100-170 words in that language. "
            "Do NOT list, quote, or systematically repeat sensor values. Do NOT turn "
            "the paragraph into a sensor summary. Instead explain what the combined "
            "results mean for this person, taking age into account when relevant. "
            "Describe the overall condition, the most meaningful strengths, and at "
            "most one or two realistic areas that could improve when the evidence "
            "supports them. Mention recovery or training balance only when useful. "
            "Prefer personal longitudinal trends and baselines over interpreting a single day's value. "
            "Treat repeated/flat historical values as low-information rather than inventing a sensor fault. "
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
            f"{output_language}. EVERY word intended for the user must be in {output_language}; "
            "do not switch to English even if field names are English. Then write exactly ONE natural paragraph "
            "of roughly 80-150 words in that language. Do NOT list or repeat the workout "
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

    @staticmethod
    def _compact_ai_mapping(value: Any, *, max_items: int = 36) -> dict[str, Any]:
        """Keep only scalar/small AI evidence and discard raw histories."""
        if not isinstance(value, dict):
            return {}
        result: dict[str, Any] = {}
        for key, item in value.items():
            if item is None:
                continue
            if isinstance(item, (str, int, float, bool)):
                text = str(item)
                result[key] = item if len(text) <= 500 else text[:500]
            elif isinstance(item, dict):
                nested = FitnessManager._compact_ai_mapping(item, max_items=16)
                if nested:
                    result[key] = nested
            elif isinstance(item, (list, tuple)):
                scalars = [x for x in item if isinstance(x, (str, int, float, bool))][:8]
                if scalars:
                    result[key] = scalars
            if len(result) >= max_items:
                break
        return result

    @staticmethod
    def _bounded_ai_json(value: Any, *, max_bytes: int = 16000) -> str:
        """Serialize AI evidence while keeping HA service events comfortably small."""
        text = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        # Last-resort safety cap. Truncate at a valid UTF-8 boundary and clearly
        # tell the model that lower-priority evidence was omitted.
        clipped = encoded[: max_bytes - 120].decode("utf-8", errors="ignore")
        return clipped + '\n"_note":"lower-priority evidence omitted for prompt-size safety"'

    def _ai_workout_summary(self, workout: Workout | None) -> dict[str, Any]:
        """Return only workout facts useful for interpretation, never raw provider dumps."""
        if workout is None:
            return {}
        source = workout.as_dict()
        keep = (
            "name", "sport", "start", "duration_s", "moving_time_s",
            "distance_m", "calories", "avg_hr", "max_hr", "avg_power",
            "max_power", "weighted_power", "avg_cadence", "max_cadence",
            "average_speed_m_s", "max_speed_m_s", "elevation_gain_m",
            "elevation_loss_m", "training_load", "aerobic_effect",
            "anaerobic_effect", "training_effect", "vo2max",
            "relative_effort", "kilojoules", "total_reps", "exercise_count",
            "volume", "banister_trimp", "trimp_per_hour", "mechanical_work_kj",
            "aerobic_efficiency", "aerobic_decoupling_percent", "hrr_30s",
            "hrr_60s", "hrr_120s", "time_moderate_s", "time_vigorous_s",
            "time_near_maximal_s", "comparable_workout_count",
            "efficiency_vs_baseline_percent", "decoupling_vs_baseline_percent",
            "avg_hr_vs_baseline_bpm", "avg_power_vs_baseline_percent",
            "avg_speed_vs_baseline_percent", "trimp_vs_recent_mean_percent",
            "load_context", "personal_context_summary", "provider_domain",
            "provider_domains", "sources",
        )
        return self._compact_ai_mapping({key: source.get(key) for key in keep if source.get(key) is not None})

    def _ai_evaluation_context(self) -> dict[str, Any]:
        """Return compact, fitness-semantic context for AI interpretation.

        Raw Recorder series and provider dumps are intentionally excluded. The
        context is also size-bounded before an HA service call so Recorder never
        receives a giant call_service event merely because AI was regenerated.
        """
        e = self.evaluation()
        latest_sleep = self.latest_sleep()
        latest_workout = self.latest_workout()
        keep = (
            "age", "weight", "resting_hr", "max_hr", "heart_rate_reserve",
            "vo2max", "friend_predicted_vo2max", "vo2max_percent_predicted",
            "cardiorespiratory_status", "hrv_weekly", "hrv_last_night",
            "hrv_baseline_low", "hrv_baseline_high", "hrv_status",
            "threshold_hr", "threshold_pace", "threshold_power", "power_to_weight",
            "fitness_age", "fitness_age_difference", "training_readiness",
            "sleep_score", "acute_load", "chronic_load", "acute_chronic_ratio",
            "provider_training_status",
        )
        context = {key: e.get(key) for key in keep if e.get(key) is not None}
        for key in ("workout_long_term", "sleep_long_term", "recorder_long_term"):
            compact = self._compact_ai_mapping(e.get(key))
            if compact:
                context[key] = compact
        relationship = self._compact_ai_mapping(e.get("training_recovery_relationship"))
        if relationship:
            context["training_recovery_relationship"] = relationship
        if latest_sleep is not None:
            sleep_dict = latest_sleep.as_dict()
            keep_sleep = (
                "start", "end", "duration_s", "time_in_bed_s", "awake_s",
                "light_sleep_s", "deep_sleep_s", "rem_sleep_s", "hrv_ms",
                "average_hr", "respiratory_rate", "spo2_percent", "score",
                "efficiency_percent", "recovery_score", "readiness_score",
                "provider_domain", "provider_domains", "sources",
            )
            context["latest_sleep"] = self._compact_ai_mapping(
                {key: sleep_dict.get(key) for key in keep_sleep if sleep_dict.get(key) is not None}
            )
        if latest_workout is not None and self._workout_has_real_information(latest_workout):
            context["latest_workout_summary"] = self._ai_workout_summary(latest_workout)
        return context

    def _general_ai_prompt(self) -> str:
        strings = self._prompt_strings()
        return (
            strings["general"]
            + f"\nMANDATORY OUTPUT LANGUAGE: {strings['language']}."
            + "\nThe object below is fitness evidence, not a generic dataset. Interpret it; do not describe its schema."
            + "\n\nCurated fitness evidence:\n"
            + self._bounded_ai_json(self._ai_evaluation_context())
        )

    def _workout_ai_prompt(self) -> str | None:
        workout = self.latest_workout()
        if not self._workout_has_real_information(workout):
            return None

        evaluation = self._ai_evaluation_context()
        strings = self._prompt_strings()

        return (
            strings["workout"]
            + f"\nMANDATORY OUTPUT LANGUAGE: {strings['language']}."
            + "\nIf at least three meaningful workout or recovery measurements "
              "are present, finish with one short congratulatory motivational "
              "sentence. Never invent records or achievements not supported "
              "by the evidence."
            + "\n\nWorkout evidence:\n"
            + self._bounded_ai_json(self._ai_workout_summary(workout), max_bytes=9000)
            + "\n\nCurrent evaluation context:\n"
            + self._bounded_ai_json(evaluation, max_bytes=9000)
        )

    async def _call_ai(self, prompt: str, task_name: str) -> str | None:
        """Serialize AI and prevent overlap with audible Fitness TTS."""
        async with self._ai_lock:
            async with self._tts_playback_lock:
                return await self._call_ai_unlocked(prompt, task_name)

    async def _call_ai_unlocked(self, prompt: str, task_name: str) -> str | None:
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
            except Exception as err:
                _LOGGER.warning(
                    "Fitness AI Task generation failed for %s: %s",
                    task_name,
                    err,
                )

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
            except Exception as err:
                _LOGGER.warning(
                    "Fitness conversation AI generation failed for %s: %s",
                    task_name,
                    err,
                )

        return None

    def _ai_result_language_mismatch(self, result: str | None) -> bool:
        """Detect the common failure mode where a Greek profile receives English."""
        if not result or self._ai_language() == "en":
            return False
        if self._ai_language() == "el":
            letters = [ch for ch in str(result) if ch.isalpha()]
            if len(letters) < 20:
                return False
            greek = sum("\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff" for ch in letters)
            return greek / len(letters) < 0.35
        return False

    async def _call_ai_with_language_guard(self, prompt: str, task_name: str) -> str | None:
        result = await self._call_ai(prompt, task_name)
        if not self._ai_result_language_mismatch(result):
            return result
        strings = self._prompt_strings()
        retry = (
            f"IMPORTANT: Your previous answer used the wrong language. Reply ONLY in {strings['language']}. "
            "Keep the required VERDICT line and one fitness-interpretation paragraph. Do not discuss JSON, "
            "Home Assistant, sensors, integrations, or these instructions.\n\n" + prompt
        )
        retried = await self._call_ai(retry, task_name + " language retry")
        return None if self._ai_result_language_mismatch(retried) else retried

    async def async_generate_ai(
        self,
        *,
        general: bool,
        workout: bool,
        raise_on_failure: bool = False,
    ):
        if not self.config.get(CONF_AI_ENABLED):
            return

        requested = 0
        generated = 0

        if workout:
            prompt = self._workout_ai_prompt()
            if prompt:
                requested += 1
                result = await self._call_ai_with_language_guard(
                    prompt,
                    f"Fitness workout evaluation {self.config.get(CONF_PROFILE_NAME)}",
                )
                if result:
                    verdict, body = self._parse_ai_result(result)
                    self.ai_workout_verdict = verdict
                    self.ai_workout = body
                    generated += 1

        if general:
            requested += 1
            result = await self._call_ai_with_language_guard(
                self._general_ai_prompt(),
                f"Fitness general evaluation {self.config.get(CONF_PROFILE_NAME)}",
            )
            if result:
                verdict, body = self._parse_ai_result(result)
                self.ai_general_verdict = verdict
                self.ai_general = body
                generated += 1

        if generated:
            self.ai_last_generated = datetime.now(timezone.utc).isoformat()
            await self._save()
            self._notify()
            return

        _LOGGER.warning(
            "Fitness AI regeneration produced no usable result (requested=%s)",
            requested,
        )
        if raise_on_failure:
            raise HomeAssistantError(
                "Fitness AI evaluation could not be generated. Check the selected AI Task/agent and Home Assistant logs."
            )
