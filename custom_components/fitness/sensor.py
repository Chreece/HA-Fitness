"""Fitness sensor platform."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.const import PERCENTAGE, UnitOfPower

from .const import (
    DOMAIN,
    METRIC_ALTITUDE,
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
    METHOD_FRIEND_2017,
    METHOD_PERSONAL_HRV_BASELINE,
    METHOD_ACSM_HRR_INTENSITY,
    METHOD_THRESHOLD_RELATIVE,
)
from .entity import device_info
from .engine.live import (
    acsm_hrr_intensity,
    pace_from_speed_kmh,
    percent_hrr,
    percent_max_hr,
    relative_percent,
    speed_from_pace_min_km,
)
from .providers.entities import resolve_number_or_entity
from .explanations import sensor_explanation  # Deterministic; never AI-generated.


@dataclass(frozen=True, kw_only=True)
class Desc(SensorEntityDescription):
    kind: str
    metric: str
    unit: str | None = None


DESCRIPTIONS = (
    # Live device
    Desc(key="session_status", translation_key="session_status", kind="live", metric="session_status"),
    Desc(key="session_duration", translation_key="session_duration", kind="live", metric="session_duration", unit="s"),
    Desc(key="current_heart_rate", translation_key="current_heart_rate", kind="live", metric=METRIC_HEART_RATE, unit="bpm"),
    Desc(key="current_power", translation_key="current_power", kind="live", metric=METRIC_POWER, unit="W"),
    Desc(key="current_cadence", translation_key="current_cadence", kind="live", metric=METRIC_CADENCE, unit="1/min"),
    Desc(key="current_speed", translation_key="current_speed", kind="live", metric=METRIC_SPEED, unit="km/h"),
    Desc(key="current_distance", translation_key="current_distance", kind="live", metric=METRIC_DISTANCE, unit="km"),
    Desc(key="current_altitude", translation_key="current_altitude", kind="live", metric=METRIC_ALTITUDE, unit="m"),

    # Live derived metrics. Creation is capability-driven in async_setup_entry.
    Desc(key="heart_rate_percent_max", translation_key="heart_rate_percent_max", kind="live", metric="heart_rate_percent_max", unit="%"),
    Desc(key="heart_rate_reserve_percent", translation_key="heart_rate_reserve_percent", kind="live", metric="heart_rate_reserve_percent", unit="%"),
    Desc(key="heart_rate_intensity", translation_key="heart_rate_intensity", kind="live", metric="heart_rate_intensity"),
    Desc(key="heart_rate_relative_threshold", translation_key="heart_rate_relative_threshold", kind="live", metric="heart_rate_relative_threshold", unit="%"),
    Desc(key="current_power_to_weight", translation_key="current_power_to_weight", kind="live", metric="current_power_to_weight", unit="W/kg"),
    Desc(key="power_relative_threshold", translation_key="power_relative_threshold", kind="live", metric="power_relative_threshold", unit="%"),
    Desc(key="current_pace", translation_key="current_pace", kind="live", metric="current_pace", unit="min/km"),
    Desc(key="speed_relative_threshold", translation_key="speed_relative_threshold", kind="live", metric="speed_relative_threshold", unit="%"),
    Desc(key="live_average_heart_rate", translation_key="live_average_heart_rate", kind="live", metric="live_average_hr", unit="bpm"),
    Desc(key="live_maximum_heart_rate", translation_key="live_maximum_heart_rate", kind="live", metric="live_maximum_hr", unit="bpm"),
    Desc(key="live_average_power", translation_key="live_average_power", kind="live", metric="live_average_power", unit="W"),
    Desc(key="live_maximum_power", translation_key="live_maximum_power", kind="live", metric="live_maximum_power", unit="W"),
    Desc(key="live_average_cadence", translation_key="live_average_cadence", kind="live", metric="live_average_cadence", unit="1/min"),
    Desc(key="live_average_speed", translation_key="live_average_speed", kind="live", metric="live_average_speed", unit="km/h"),
    Desc(key="live_banister_trimp", translation_key="live_banister_trimp", kind="live", metric="live_banister_trimp"),
    Desc(key="live_mechanical_work", translation_key="live_mechanical_work", kind="live", metric="live_mechanical_work", unit="kJ"),
    Desc(key="live_aerobic_efficiency", translation_key="live_aerobic_efficiency", kind="live", metric="live_aerobic_efficiency"),
    Desc(key="live_aerobic_decoupling", translation_key="live_aerobic_decoupling", kind="live", metric="live_aerobic_decoupling", unit="%"),
    Desc(key="live_time_moderate", translation_key="live_time_moderate", kind="live", metric="live_time_moderate", unit="s"),
    Desc(key="live_time_vigorous", translation_key="live_time_vigorous", kind="live", metric="live_time_vigorous", unit="s"),
    Desc(key="live_time_near_maximal", translation_key="live_time_near_maximal", kind="live", metric="live_time_near_maximal", unit="s"),

    # Workout device
    Desc(key="last_workout", translation_key="last_workout", kind="workout", metric="workout_name"),
    Desc(key="last_workout_source", translation_key="last_workout_source", kind="workout", metric="workout_source"),
    Desc(key="last_workout_duration", translation_key="last_workout_duration", kind="workout", metric="workout_duration", unit="min"),
    Desc(key="last_workout_distance", translation_key="last_workout_distance", kind="workout", metric="workout_distance", unit="km"),
    Desc(key="last_workout_avg_hr", translation_key="last_workout_avg_hr", kind="workout", metric="workout_avg_hr", unit="bpm"),
    Desc(key="last_workout_max_hr", translation_key="last_workout_max_hr", kind="workout", metric="workout_max_hr", unit="bpm"),
    Desc(key="last_workout_avg_power", translation_key="last_workout_avg_power", kind="workout", metric="workout_avg_power", unit="W"),
    Desc(key="last_workout_max_power", translation_key="last_workout_max_power", kind="workout", metric="workout_max_power", unit="W"),
    Desc(key="last_workout_avg_cadence", translation_key="last_workout_avg_cadence", kind="workout", metric="workout_avg_cadence", unit="spm"),
    Desc(key="last_workout_elevation_gain", translation_key="last_workout_elevation_gain", kind="workout", metric="workout_elevation", unit="m"),
    Desc(key="last_workout_calories", translation_key="last_workout_calories", kind="workout", metric="workout_calories", unit="kcal"),
    Desc(key="last_workout_moving_time", translation_key="last_workout_moving_time", kind="workout", metric="workout_moving_time", unit="min"),
    Desc(key="last_workout_elapsed_time", translation_key="last_workout_elapsed_time", kind="workout", metric="workout_elapsed_time", unit="min"),
    Desc(key="last_workout_average_speed", translation_key="last_workout_average_speed", kind="workout", metric="workout_average_speed", unit="km/h"),
    Desc(key="last_workout_max_speed", translation_key="last_workout_max_speed", kind="workout", metric="workout_max_speed", unit="km/h"),
    Desc(key="last_workout_weighted_power", translation_key="last_workout_weighted_power", kind="workout", metric="workout_weighted_power", unit="W"),
    Desc(key="last_workout_max_cadence", translation_key="last_workout_max_cadence", kind="workout", metric="workout_max_cadence", unit="1/min"),
    Desc(key="last_workout_elevation_loss", translation_key="last_workout_elevation_loss", kind="workout", metric="workout_elevation_loss", unit="m"),
    Desc(key="last_workout_training_load", translation_key="last_workout_training_load", kind="workout", metric="workout_training_load"),
    Desc(key="last_workout_aerobic_effect", translation_key="last_workout_aerobic_effect", kind="workout", metric="workout_aerobic_effect"),
    Desc(key="last_workout_anaerobic_effect", translation_key="last_workout_anaerobic_effect", kind="workout", metric="workout_anaerobic_effect"),
    Desc(key="last_workout_training_effect", translation_key="last_workout_training_effect", kind="workout", metric="workout_training_effect"),
    Desc(key="last_workout_vo2max", translation_key="last_workout_vo2max", kind="workout", metric="workout_vo2max", unit="mL/kg/min"),
    Desc(key="last_workout_relative_effort", translation_key="last_workout_relative_effort", kind="workout", metric="workout_relative_effort"),
    Desc(key="last_workout_kilojoules", translation_key="last_workout_kilojoules", kind="workout", metric="workout_kilojoules", unit="kJ"),
    Desc(key="last_workout_total_reps", translation_key="last_workout_total_reps", kind="workout", metric="workout_total_reps"),
    Desc(key="last_workout_exercise_count", translation_key="last_workout_exercise_count", kind="workout", metric="workout_exercise_count"),
    Desc(key="last_workout_volume", translation_key="last_workout_volume", kind="workout", metric="workout_volume", unit="kg"),
    Desc(key="last_workout_device", translation_key="last_workout_device", kind="workout", metric="workout_device"),
    Desc(key="last_workout_gear", translation_key="last_workout_gear", kind="workout", metric="workout_gear"),
    Desc(key="last_workout_sources", translation_key="last_workout_sources", kind="workout", metric="workout_sources"),
    Desc(key="last_workout_banister_trimp", translation_key="last_workout_banister_trimp", kind="workout", metric="workout_banister_trimp"),
    Desc(key="last_workout_trimp_per_hour", translation_key="last_workout_trimp_per_hour", kind="workout", metric="workout_trimp_per_hour"),
    Desc(key="last_workout_mechanical_work", translation_key="last_workout_mechanical_work", kind="workout", metric="workout_mechanical_work", unit="kJ"),
    Desc(key="last_workout_aerobic_efficiency", translation_key="last_workout_aerobic_efficiency", kind="workout", metric="workout_aerobic_efficiency"),
    Desc(key="last_workout_aerobic_decoupling", translation_key="last_workout_aerobic_decoupling", kind="workout", metric="workout_aerobic_decoupling", unit="%"),
    Desc(key="last_workout_hrr_10s", translation_key="last_workout_hrr_10s", kind="workout", metric="workout_hrr_10s", unit="bpm"),
    Desc(key="last_workout_hrr_30s", translation_key="last_workout_hrr_30s", kind="workout", metric="workout_hrr_30s", unit="bpm"),
    Desc(key="last_workout_hrr_60s", translation_key="last_workout_hrr_60s", kind="workout", metric="workout_hrr_60s", unit="bpm"),
    Desc(key="last_workout_hrr_120s", translation_key="last_workout_hrr_120s", kind="workout", metric="workout_hrr_120s", unit="bpm"),
    Desc(key="last_workout_time_moderate", translation_key="last_workout_time_moderate", kind="workout", metric="workout_time_moderate", unit="min"),
    Desc(key="last_workout_time_vigorous", translation_key="last_workout_time_vigorous", kind="workout", metric="workout_time_vigorous", unit="min"),
    Desc(key="last_workout_time_near_maximal", translation_key="last_workout_time_near_maximal", kind="workout", metric="workout_time_near_maximal", unit="min"),
    Desc(key="last_workout_comparable_count", translation_key="last_workout_comparable_count", kind="workout", metric="workout_comparable_count"),
    Desc(key="last_workout_efficiency_vs_baseline", translation_key="last_workout_efficiency_vs_baseline", kind="workout", metric="workout_efficiency_vs_baseline", unit="%"),
    Desc(key="last_workout_decoupling_vs_baseline", translation_key="last_workout_decoupling_vs_baseline", kind="workout", metric="workout_decoupling_vs_baseline", unit="%"),
    Desc(key="last_workout_hr_vs_baseline", translation_key="last_workout_hr_vs_baseline", kind="workout", metric="workout_hr_vs_baseline", unit="bpm"),
    Desc(key="last_workout_power_vs_baseline", translation_key="last_workout_power_vs_baseline", kind="workout", metric="workout_power_vs_baseline", unit="%"),
    Desc(key="last_workout_speed_vs_baseline", translation_key="last_workout_speed_vs_baseline", kind="workout", metric="workout_speed_vs_baseline", unit="%"),
    Desc(key="last_workout_trimp_vs_recent", translation_key="last_workout_trimp_vs_recent", kind="workout", metric="workout_trimp_vs_recent", unit="%"),
    Desc(key="last_workout_load_context", translation_key="last_workout_load_context", kind="workout", metric="workout_load_context"),
    Desc(key="last_workout_personal_context", translation_key="last_workout_personal_context", kind="workout", metric="workout_personal_context"),

    # Evaluation device
    Desc(key="age", translation_key="age", kind="evaluation", metric="age", unit="yr"),
    Desc(key="weight", translation_key="weight", kind="evaluation", metric="weight", unit="kg"),
    Desc(key="resting_hr", translation_key="resting_hr", kind="evaluation", metric="resting_hr", unit="bpm"),
    Desc(key="maximum_hr", translation_key="maximum_hr", kind="evaluation", metric="max_hr", unit="bpm"),
    Desc(key="heart_rate_reserve", translation_key="heart_rate_reserve", kind="evaluation", metric="heart_rate_reserve", unit="bpm"),
    Desc(key="vo2max", translation_key="vo2max", kind="evaluation", metric="vo2max", unit="mL/kg/min"),
    Desc(key="friend_predicted_vo2max", translation_key="friend_predicted_vo2max", kind="evaluation", metric="friend_predicted_vo2max", unit="mL/kg/min"),
    Desc(key="vo2max_percent_predicted", translation_key="vo2max_percent_predicted", kind="evaluation", metric="vo2max_percent_predicted", unit="%"),
    Desc(key="cardiorespiratory_status", translation_key="cardiorespiratory_status", kind="evaluation", metric="cardiorespiratory_status"),
    Desc(key="hrv_weekly", translation_key="hrv_weekly", kind="evaluation", metric="hrv_weekly", unit="ms"),
    Desc(key="hrv_last_night", translation_key="hrv_last_night", kind="evaluation", metric="hrv_last_night", unit="ms"),
    Desc(key="hrv_status", translation_key="hrv_status", kind="evaluation", metric="hrv_status"),
    Desc(key="threshold_hr", translation_key="threshold_hr", kind="evaluation", metric="threshold_hr", unit="bpm"),
    Desc(key="threshold_pace", translation_key="threshold_pace", kind="evaluation", metric="threshold_pace", unit="min/km"),
    Desc(key="threshold_power", translation_key="threshold_power", kind="evaluation", metric="threshold_power", unit="W"),
    Desc(key="threshold_power_to_weight", translation_key="threshold_power_to_weight", kind="evaluation", metric="power_to_weight", unit="W/kg"),
    Desc(key="fitness_age", translation_key="fitness_age", kind="evaluation", metric="fitness_age", unit="yr"),
    Desc(key="fitness_age_difference", translation_key="fitness_age_difference", kind="evaluation", metric="fitness_age_difference", unit="yr"),
    Desc(key="training_readiness_context", translation_key="training_readiness_context", kind="evaluation", metric="training_readiness", unit="%"),
    Desc(key="sleep_score_context", translation_key="sleep_score_context", kind="evaluation", metric="sleep_score"),
    Desc(key="acute_training_load", translation_key="acute_training_load", kind="evaluation", metric="acute_load"),
    Desc(key="chronic_training_load", translation_key="chronic_training_load", kind="evaluation", metric="chronic_load"),
    Desc(key="acute_chronic_ratio", translation_key="acute_chronic_ratio", kind="evaluation", metric="acute_chronic_ratio"),
    Desc(key="provider_training_status", translation_key="provider_training_status", kind="evaluation", metric="provider_training_status"),
    Desc(key="training_load_7d", translation_key="training_load_7d", kind="evaluation", metric="training_load_7d"),
    Desc(key="training_load_28d", translation_key="training_load_28d", kind="evaluation", metric="training_load_28d"),
    Desc(key="training_load_42d", translation_key="training_load_42d", kind="evaluation", metric="training_load_42d"),
    Desc(key="training_days_28d", translation_key="training_days_28d", kind="evaluation", metric="training_days_28d", unit="d"),
    Desc(key="hrr_60s_long_term", translation_key="hrr_60s_long_term", kind="evaluation", metric="hrr_60s_long_term", unit="bpm"),
    Desc(key="aerobic_decoupling_long_term", translation_key="aerobic_decoupling_long_term", kind="evaluation", metric="aerobic_decoupling_long_term", unit="%"),
    Desc(key="aerobic_efficiency_long_term", translation_key="aerobic_efficiency_long_term", kind="evaluation", metric="aerobic_efficiency_long_term"),
    Desc(key="ai_general_evaluation", translation_key="ai_general_evaluation", kind="evaluation", metric="ai_general"),
    Desc(key="ai_workout_evaluation", translation_key="ai_workout_evaluation", kind="evaluation", metric="ai_workout"),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Create optional Fitness sensors only after a valid value exists.

    Once created, an entity is permanent. A later missing prerequisite makes
    its state unavailable; it is never removed and its history/entity ID remain.
    """
    manager = hass.data[DOMAIN][entry.entry_id]
    registry = er.async_get(hass)

    descriptions = {
        desc.key: desc
        for desc in DESCRIPTIONS
        if not (
            desc.metric.startswith("ai_")
            and not manager.config.get("ai_enabled")
        )
    }

    # Preserve entities already created by older Fitness versions. This also
    # makes an alpha.31 -> alpha.32 upgrade non-destructive.
    registry_keys: set[str] = set()
    prefix = f"{entry.entry_id}_"

    for registry_entry in registry.entities.values():
        if registry_entry.platform != DOMAIN:
            continue

        unique_id = registry_entry.unique_id or ""
        if not unique_id.startswith(prefix):
            continue

        key = unique_id[len(prefix):]
        if key in descriptions:
            registry_keys.add(key)

    manager.remember_materialized_sensors(
        registry_keys,
        persist=True,
    )

    # Session status is the control/status anchor and always has a meaningful
    # value: idle / waiting_for_live_data / active / recovery.
    manager.remember_materialized_sensor(
        "session_status",
        persist=True,
    )

    created_keys: set[str] = set()

    def description_has_valid_value(desc) -> bool:
        """Calculate without registering an entity."""
        probe = FitnessSensor(manager, entry, desc)
        try:
            return probe.native_value is not None
        except Exception:
            # Optional data must never prevent the whole integration from loading.
            return False

    def collect_new_entities() -> list[FitnessSensor]:
        result: list[FitnessSensor] = []

        for key, desc in descriptions.items():
            if key in created_keys:
                continue

            previously_created = manager.sensor_was_materialized(key)
            valid_now = (
                False
                if previously_created
                else description_has_valid_value(desc)
            )

            if not previously_created and not valid_now:
                continue

            if valid_now:
                manager.remember_materialized_sensor(
                    key,
                    persist=True,
                )

            created_keys.add(key)
            result.append(
                FitnessSensor(
                    manager,
                    entry,
                    desc,
                )
            )

        return result

    initial = collect_new_entities()
    if initial:
        async_add_entities(initial)

    @callback
    def materialize_new_valid_sensors() -> None:
        new_entities = collect_new_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(
        manager.add_listener(
            materialize_new_valid_sensors
        )
    )


class FitnessSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, manager, entry, desc):
        self.manager = manager
        self.entry = entry
        self.entity_description = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_device_info = device_info(entry, desc.kind)

    async def async_added_to_hass(self):
        # Every Fitness sensor receives low-frequency/general manager updates.
        self.async_on_remove(
            self.manager.add_listener(self._update)
        )

        # Live sensors additionally receive the high-frequency live-only path.
        if self.entity_description.kind == "live":
            self.async_on_remove(
                self.manager.add_live_listener(self._update)
            )

    def _update(self):
        self.async_write_ha_state()

    @property
    def state_class(self):
        textual = {
            "session_status",
            "heart_rate_intensity",
            "workout_name",
            "workout_source",
            "workout_training_effect",
            "workout_device",
            "workout_gear",
            "workout_sources",
            "workout_load_context",
            "workout_personal_context",
            "ai_general",
            "ai_workout",
            "cardiorespiratory_status",
            "hrv_status",
            "provider_training_status",
        }
        if self.entity_description.metric in textual:
            return None
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        return self.entity_description.unit

    @property
    def native_value(self):
        m = self.entity_description.metric

        if self.entity_description.kind == "live":
            if m == "session_status":
                return self.manager.session_status()

            if not self.manager.session_active:
                return None

            if m == "session_duration":
                return round(self.manager.session_duration())

            live = self.manager.live_values()
            derived = self.manager.live_derived_values()
            session_stats = self.manager.live_session_statistics()

            if m in (
                METRIC_HEART_RATE,
                METRIC_POWER,
                METRIC_CADENCE,
                METRIC_SPEED,
                METRIC_DISTANCE,
                METRIC_ALTITUDE,
            ):
                value = live.get(m)
                return round(value, 2) if value is not None else None

            if m == "heart_rate_percent_max":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            if m == "heart_rate_reserve_percent":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            if m == "heart_rate_intensity":
                return derived.get(m)

            if m == "heart_rate_relative_threshold":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            if m == "current_power_to_weight":
                value = derived.get(m)
                return round(value, 2) if value is not None else None

            if m == "power_relative_threshold":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            if m == "current_pace":
                value = derived.get(m)
                return round(value, 2) if value is not None else None

            if m == "speed_relative_threshold":
                value = derived.get(m)
                return round(value, 1) if value is not None else None

            live_stats_map = {
                "live_average_hr": session_stats.get("average_hr"),
                "live_maximum_hr": session_stats.get("maximum_hr"),
                "live_average_power": session_stats.get("average_power"),
                "live_maximum_power": session_stats.get("maximum_power"),
                "live_average_cadence": session_stats.get("average_cadence"),
                "live_average_speed": session_stats.get("average_speed"),
                "live_banister_trimp": session_stats.get("banister_trimp"),
                "live_mechanical_work": session_stats.get("mechanical_work_kj"),
                "live_aerobic_efficiency": session_stats.get("aerobic_efficiency"),
                "live_aerobic_decoupling": session_stats.get("aerobic_decoupling_percent"),
                "live_time_moderate": session_stats.get("time_moderate_s"),
                "live_time_vigorous": session_stats.get("time_vigorous_s"),
                "live_time_near_maximal": session_stats.get("time_near_maximal_s"),
            }
            value = live_stats_map.get(m)
            return round(value, 2) if value is not None else None

        if self.entity_description.kind == "workout":
            w = self.manager.latest_workout()
            if w is None:
                return None
            return {
                "workout_name": w.name or w.sport or "Workout",
                "workout_source": w.source,
                "workout_duration": round(w.duration_s / 60, 1) if w.duration_s is not None else None,
                "workout_distance": round(w.distance_m / 1000, 2) if w.distance_m is not None else None,
                "workout_avg_hr": round(w.avg_hr) if w.avg_hr is not None else None,
                "workout_max_hr": round(w.max_hr) if w.max_hr is not None else None,
                "workout_avg_power": round(w.avg_power) if w.avg_power is not None else None,
                "workout_max_power": round(w.max_power) if w.max_power is not None else None,
                "workout_avg_cadence": round(w.avg_cadence, 1) if w.avg_cadence is not None else None,
                "workout_elevation": round(w.elevation_gain_m, 1) if w.elevation_gain_m is not None else None,
                "workout_calories": round(w.calories) if w.calories is not None else None,
                "workout_moving_time": round(w.moving_time_s / 60, 1) if w.moving_time_s is not None else None,
                "workout_elapsed_time": round(w.elapsed_time_s / 60, 1) if w.elapsed_time_s is not None else None,
                "workout_average_speed": round(w.average_speed_m_s * 3.6, 2) if w.average_speed_m_s is not None else None,
                "workout_max_speed": round(w.max_speed_m_s * 3.6, 2) if w.max_speed_m_s is not None else None,
                "workout_weighted_power": round(w.weighted_power) if w.weighted_power is not None else None,
                "workout_max_cadence": round(w.max_cadence, 1) if w.max_cadence is not None else None,
                "workout_elevation_loss": round(w.elevation_loss_m, 1) if w.elevation_loss_m is not None else None,
                "workout_training_load": round(w.training_load, 1) if w.training_load is not None else None,
                "workout_aerobic_effect": round(w.aerobic_training_effect, 1) if w.aerobic_training_effect is not None else None,
                "workout_anaerobic_effect": round(w.anaerobic_training_effect, 1) if w.anaerobic_training_effect is not None else None,
                "workout_training_effect": w.training_effect_label,
                "workout_vo2max": round(w.vo2max, 1) if w.vo2max is not None else None,
                "workout_relative_effort": round(w.relative_effort, 1) if w.relative_effort is not None else None,
                "workout_kilojoules": round(w.kilojoules, 1) if w.kilojoules is not None else None,
                "workout_total_reps": round(w.total_reps) if w.total_reps is not None else None,
                "workout_exercise_count": round(w.exercise_count) if w.exercise_count is not None else None,
                "workout_volume": round(w.volume_kg, 1) if w.volume_kg is not None else None,
                "workout_device": w.device_name,
                "workout_gear": w.gear_name,
                "workout_sources": ", ".join(w.provider_domains or w.sources) if (w.provider_domains or w.sources) else w.source,
                "workout_banister_trimp": round(w.banister_trimp, 1) if w.banister_trimp is not None else None,
                "workout_trimp_per_hour": round(w.trimp_per_hour, 1) if w.trimp_per_hour is not None else None,
                "workout_mechanical_work": round(w.mechanical_work_kj, 1) if w.mechanical_work_kj is not None else None,
                "workout_aerobic_efficiency": round(w.aerobic_efficiency, 5) if w.aerobic_efficiency is not None else None,
                "workout_aerobic_decoupling": round(w.aerobic_decoupling_percent, 2) if w.aerobic_decoupling_percent is not None else None,
                "workout_hrr_10s": round(w.hrr_10s, 1) if w.hrr_10s is not None else None,
                "workout_hrr_30s": round(w.hrr_30s, 1) if w.hrr_30s is not None else None,
                "workout_hrr_60s": round(w.hrr_60s, 1) if w.hrr_60s is not None else None,
                "workout_hrr_120s": round(w.hrr_120s, 1) if w.hrr_120s is not None else None,
                "workout_time_moderate": round(w.time_moderate_s / 60, 1) if w.time_moderate_s is not None else None,
                "workout_time_vigorous": round(w.time_vigorous_s / 60, 1) if w.time_vigorous_s is not None else None,
                "workout_time_near_maximal": round(w.time_near_maximal_s / 60, 1) if w.time_near_maximal_s is not None else None,
                "workout_comparable_count": w.comparable_workout_count,
                "workout_efficiency_vs_baseline": round(w.efficiency_vs_baseline_percent, 1) if w.efficiency_vs_baseline_percent is not None else None,
                "workout_decoupling_vs_baseline": round(w.decoupling_vs_baseline_percent, 1) if w.decoupling_vs_baseline_percent is not None else None,
                "workout_hr_vs_baseline": round(w.avg_hr_vs_baseline_bpm, 1) if w.avg_hr_vs_baseline_bpm is not None else None,
                "workout_power_vs_baseline": round(w.avg_power_vs_baseline_percent, 1) if w.avg_power_vs_baseline_percent is not None else None,
                "workout_speed_vs_baseline": round(w.avg_speed_vs_baseline_percent, 1) if w.avg_speed_vs_baseline_percent is not None else None,
                "workout_trimp_vs_recent": round(w.trimp_vs_recent_mean_percent, 1) if w.trimp_vs_recent_mean_percent is not None else None,
                "workout_load_context": w.load_context,
                "workout_personal_context": w.personal_context_summary,
            }.get(m)

        e = self.manager.evaluation()
        if m == "ai_general":
            return self.manager.ai_general_verdict or (
                "Updated" if self.manager.ai_general else None
            )
        if m == "ai_workout":
            return self.manager.ai_workout_verdict or (
                "Updated" if self.manager.ai_workout else None
            )

        workout_long_term = e.get("workout_long_term") or {}
        long_term_map = {
            "training_load_7d": workout_long_term.get("banister_trimp_7d"),
            "training_load_28d": workout_long_term.get("banister_trimp_28d"),
            "training_load_42d": workout_long_term.get("banister_trimp_42d"),
            "training_days_28d": workout_long_term.get("active_training_days_28d"),
            "hrr_60s_long_term": workout_long_term.get("hrr_60s_mean_90d"),
            "aerobic_decoupling_long_term": workout_long_term.get("aerobic_decoupling_mean_90d"),
            "aerobic_efficiency_long_term": workout_long_term.get("aerobic_efficiency_mean_90d"),
        }
        if m in long_term_map:
            return long_term_map[m]

        value = e.get(m)
        if isinstance(value, float):
            return round(value, 2)
        return value

    @property
    def extra_state_attributes(self):
        m = self.entity_description.metric

        if self.entity_description.kind == "live":
            attrs = {
                "capture_control": self.manager.capture_control,
                "samples_collected": len(self.manager.samples),
            }

            source_metric = {
                "heart_rate_percent_max": METRIC_HEART_RATE,
                "heart_rate_reserve_percent": METRIC_HEART_RATE,
                "heart_rate_intensity": METRIC_HEART_RATE,
                "heart_rate_relative_threshold": METRIC_HEART_RATE,
                "current_power_to_weight": METRIC_POWER,
                "power_relative_threshold": METRIC_POWER,
                "current_pace": METRIC_SPEED,
                "speed_relative_threshold": METRIC_SPEED,
            }.get(m, m)

            attrs.update(
                self.manager.live_source_info(source_metric)
            )
            attrs.update(
                sensor_explanation(
                    self.manager._ai_language(),
                    "live",
                    m,
                )
            )

            evaluation = self.manager.evaluation()

            if m == "heart_rate_percent_max":
                attrs.update(
                    {
                        "reference_hr": evaluation.get("max_hr"),
                        "method": "percent_max_heart_rate",
                        "note": (
                            "Descriptive %HRmax only. Individual physiological "
                            "thresholds can differ substantially at the same %HRmax."
                        ),
                    }
                )

            elif m in ("heart_rate_reserve_percent", "heart_rate_intensity"):
                attrs.update(
                    {
                        "resting_hr": evaluation.get("resting_hr"),
                        "max_hr": evaluation.get("max_hr"),
                        "method": METHOD_ACSM_HRR_INTENSITY,
                        "ranges_percent_hrr": {
                            "very_light": "<30",
                            "light": "30-39",
                            "moderate": "40-59",
                            "vigorous": "60-89",
                            "near_maximal": ">=90",
                        },
                        "note": (
                            "HRR-based population intensity classification. "
                            "Measured ventilatory/metabolic thresholds are more "
                            "individualized when available."
                        ),
                    }
                )

                if m == "heart_rate_intensity":
                    attrs.update(
                        self.manager.live_feedback_diagnostics()
                    )

            elif m == "heart_rate_relative_threshold":
                attrs.update(
                    {
                        "threshold_hr": evaluation.get("threshold_hr"),
                        "method": METHOD_THRESHOLD_RELATIVE,
                    }
                )

            elif m == "current_power_to_weight":
                attrs.update(
                    {
                        "weight_kg": evaluation.get("weight"),
                        "method": "instantaneous_power_per_body_mass",
                    }
                )

            elif m == "power_relative_threshold":
                attrs.update(
                    {
                        "threshold_power_w": evaluation.get("threshold_power"),
                        "method": METHOD_THRESHOLD_RELATIVE,
                        "note": (
                            "Relative to the configured/provider threshold power. "
                            "FTP, critical power and lactate-threshold power are not "
                            "assumed to be physiologically identical."
                        ),
                    }
                )

            elif m == "current_pace":
                attrs.update(
                    {
                        "normalized_speed_unit": "km/h",
                        "method": "pace_from_speed",
                    }
                )

            elif m == "speed_relative_threshold":
                attrs.update(
                    {
                        "threshold_pace_min_km": evaluation.get("threshold_pace"),
                        "method": METHOD_THRESHOLD_RELATIVE,
                    }
                )

            return attrs

        if self.entity_description.kind == "workout":
            w = self.manager.latest_workout()
            attrs = w.as_dict() if w else {}
            attrs.update(
                sensor_explanation(
                    self.manager._ai_language(),
                    "workout",
                    m,
                )
            )
            return attrs

        e = self.manager.evaluation()
        base_explanation = sensor_explanation(
            self.manager._ai_language(),
            "evaluation",
            m,
        )
        provenance = self.manager.localized_evaluation_provenance(m)
        base_explanation.update(provenance)

        if m in ("friend_predicted_vo2max", "vo2max_percent_predicted", "cardiorespiratory_status"):
            return {
                **base_explanation,
                "method": METHOD_FRIEND_2017,
                "scientific_output": (
                    "percent_predicted"
                    if m in ("vo2max_percent_predicted", "cardiorespiratory_status")
                    else "reference_vo2max"
                ),
                "note": (
                    "Status bands are display conventions; percent-predicted is the "
                    "underlying scientific comparison."
                ),
            }

        if m == "hrv_status":
            return {
                **base_explanation,
                "method": METHOD_PERSONAL_HRV_BASELINE,
                "baseline_low": e.get("hrv_baseline_low"),
                "baseline_high": e.get("hrv_baseline_high"),
                "note": "Individual baseline comparison, not a population diagnostic cutoff.",
            }

        if m == "vo2max":
            return {**base_explanation, "method": e.get("vo2max_method")}

        if m == "max_hr":
            return {**base_explanation, "method": e.get("max_hr_method")}

        if m in ("training_readiness", "sleep_score", "provider_training_status", "fitness_age"):
            return {
                **base_explanation,
                "source_type": "provider_context",
                "note": (
                    "The value is supplied by the provider. Fitness exposes the "
                    "concrete source entity in input_sources and does not claim "
                    "the provider's proprietary algorithm as a Fitness formula."
                ),
            }

        if m == "acute_chronic_ratio":
            return {
                **base_explanation,
                "note": (
                    "Training-load context only. This integration does not interpret "
                    "the ratio as an injury-risk prediction."
                )
            }

        if m in ("ai_general", "ai_workout"):
            full_text = (
                self.manager.ai_general
                if m == "ai_general"
                else self.manager.ai_workout
            )
            return {
                **base_explanation,
                "text": full_text,
                "generated_at": self.manager.ai_last_generated,
                "ai_entity": self.manager.config.get("ai_entity") or "preferred_default",
                "role": "interpretation_only",
                "note": (
                    "The full AI assessment is stored in the text attribute "
                    "because Home Assistant entity states are limited to 255 characters. "
                    "AI does not perform the deterministic scientific calculations."
                ),
            }

        configured_quantity = {
            "weight": ("weight", "weight"),
            "resting_hr": ("resting_hr", "heart_rate"),
            "max_hr": ("max_hr", "heart_rate"),
            "vo2max": ("vo2max", "vo2max"),
            "threshold_hr": ("threshold_hr", "heart_rate"),
            "threshold_pace": ("threshold_pace", "pace"),
            "threshold_power": ("threshold_power", "power"),
        }
        if m in configured_quantity:
            key, quantity = configured_quantity[m]
            resolved = resolve_number_or_entity(
                self.manager.hass,
                self.manager.config.get(key),
                quantity=quantity,
            )
            if resolved.entity_id:
                return {
                    **base_explanation,
                    "source": resolved.source,
                    "source_entity": resolved.entity_id,
                    "source_value": resolved.original_value,
                    "source_unit": resolved.original_unit,
                    "normalized_unit": resolved.canonical_unit,
                    "value_used": resolved.value,
                }

        return base_explanation
