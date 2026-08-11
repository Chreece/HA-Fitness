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

    # Sleep device
    Desc(key="last_sleep_source", translation_key="last_sleep_source", kind="sleep", metric="sleep_source"),
    Desc(key="last_sleep_duration", translation_key="last_sleep_duration", kind="sleep", metric="sleep_duration", unit="min"),
    Desc(key="last_sleep_score", translation_key="last_sleep_score", kind="sleep", metric="sleep_score"),
    Desc(key="last_sleep_efficiency", translation_key="last_sleep_efficiency", kind="sleep", metric="sleep_efficiency", unit="%"),
    Desc(key="last_sleep_time_in_bed", translation_key="last_sleep_time_in_bed", kind="sleep", metric="sleep_time_in_bed", unit="min"),
    Desc(key="last_sleep_awake", translation_key="last_sleep_awake", kind="sleep", metric="sleep_awake", unit="min"),
    Desc(key="last_sleep_light", translation_key="last_sleep_light", kind="sleep", metric="sleep_light", unit="min"),
    Desc(key="last_sleep_deep", translation_key="last_sleep_deep", kind="sleep", metric="sleep_deep", unit="min"),
    Desc(key="last_sleep_rem", translation_key="last_sleep_rem", kind="sleep", metric="sleep_rem", unit="min"),
    Desc(key="last_sleep_hrv", translation_key="last_sleep_hrv", kind="sleep", metric="sleep_hrv", unit="ms"),
    Desc(key="last_sleep_average_hr", translation_key="last_sleep_average_hr", kind="sleep", metric="sleep_average_hr", unit="bpm"),
    Desc(key="last_sleep_respiratory_rate", translation_key="last_sleep_respiratory_rate", kind="sleep", metric="sleep_respiratory_rate", unit="1/min"),
    Desc(key="last_sleep_spo2", translation_key="last_sleep_spo2", kind="sleep", metric="sleep_spo2", unit="%"),
    Desc(key="last_sleep_recovery_score", translation_key="last_sleep_recovery_score", kind="sleep", metric="sleep_recovery_score"),
    Desc(key="last_sleep_readiness_score", translation_key="last_sleep_readiness_score", kind="sleep", metric="sleep_readiness_score"),

    # Evaluation device — evidence-based and non-duplicative.
    # Provider facts stay on their source/Sleep/Workout devices. Fitness adds
    # only reference comparisons and longitudinal context requiring real data.
    Desc(key="vo2max_percent_predicted", translation_key="vo2max_percent_predicted", kind="evaluation", metric="vo2max_percent_predicted", unit="%"),
    Desc(key="training_load_7d", translation_key="training_load_7d", kind="evaluation", metric="training_load_7d"),
    Desc(key="training_load_28d", translation_key="training_load_28d", kind="evaluation", metric="training_load_28d"),
    Desc(key="training_load_change_7_vs_28", translation_key="training_load_change_7_vs_28", kind="evaluation", metric="training_load_change_7_vs_28", unit="%"),
    Desc(key="training_days_28d", translation_key="training_days_28d", kind="evaluation", metric="training_days_28d", unit="d"),
    Desc(key="hrr_60s_long_term", translation_key="hrr_60s_long_term", kind="evaluation", metric="hrr_60s_long_term", unit="bpm"),
    Desc(key="hrr_60s_vs_90d", translation_key="hrr_60s_vs_90d", kind="evaluation", metric="hrr_60s_vs_90d", unit="bpm"),
    Desc(key="sleep_duration_7d_mean", translation_key="sleep_duration_7d_mean", kind="evaluation", metric="sleep_duration_7d_mean", unit="min"),
    Desc(key="sleep_duration_28d_mean", translation_key="sleep_duration_28d_mean", kind="evaluation", metric="sleep_duration_28d_mean", unit="min"),
    Desc(key="sleep_duration_vs_28d", translation_key="sleep_duration_vs_28d", kind="evaluation", metric="sleep_duration_vs_28d", unit="min"),
    Desc(key="sleep_duration_shortfall", translation_key="sleep_duration_shortfall", kind="evaluation", metric="sleep_duration_shortfall", unit="min"),
    Desc(key="sleep_midpoint_variability_14d", translation_key="sleep_midpoint_variability_14d", kind="evaluation", metric="sleep_midpoint_variability_14d", unit="min"),
    Desc(key="sleep_hrv_7d_mean", translation_key="sleep_hrv_7d_mean", kind="evaluation", metric="sleep_hrv_7d_mean", unit="ms"),
    Desc(key="sleep_hrv_28d_mean", translation_key="sleep_hrv_28d_mean", kind="evaluation", metric="sleep_hrv_28d_mean", unit="ms"),
    Desc(key="sleep_hrv_vs_28d", translation_key="sleep_hrv_vs_28d", kind="evaluation", metric="sleep_hrv_vs_28d", unit="%"),
    Desc(key="resting_hr_7d_mean", translation_key="resting_hr_7d_mean", kind="evaluation", metric="resting_hr_7d_mean", unit="bpm"),
    Desc(key="resting_hr_28d_mean", translation_key="resting_hr_28d_mean", kind="evaluation", metric="resting_hr_28d_mean", unit="bpm"),
    Desc(key="resting_hr_vs_28d", translation_key="resting_hr_vs_28d", kind="evaluation", metric="resting_hr_vs_28d", unit="bpm"),
    Desc(key="vo2max_28d_mean", translation_key="vo2max_28d_mean", kind="evaluation", metric="vo2max_28d_mean", unit="mL/kg/min"),
    Desc(key="vo2max_trend_14_vs_previous_14", translation_key="vo2max_trend_14_vs_previous_14", kind="evaluation", metric="vo2max_trend_14_vs_previous_14", unit="%"),
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

    # Remove obsolete Evaluation mirrors from older betas instead of leaving
    # permanent unavailable ghost entities in the device registry.
    deprecated_evaluation_keys = {
        "age", "weight", "resting_hr", "maximum_hr", "heart_rate_reserve",
        "vo2max", "friend_predicted_vo2max", "cardiorespiratory_status",
        "hrv_weekly", "hrv_last_night", "hrv_status", "threshold_hr",
        "threshold_pace", "threshold_power", "threshold_power_to_weight",
        "fitness_age", "fitness_age_difference", "training_readiness_context",
        "sleep_score_context", "acute_training_load", "chronic_training_load",
        "acute_chronic_ratio", "provider_training_status", "training_load_42d",
        "aerobic_decoupling_long_term", "aerobic_efficiency_long_term",
    }
    prefix = f"{entry.entry_id}_"
    for registry_entry in list(registry.entities.values()):
        if registry_entry.platform != DOMAIN:
            continue
        unique_id = registry_entry.unique_id or ""
        if not unique_id.startswith(prefix):
            continue
        key = unique_id[len(prefix):]
        if key in deprecated_evaluation_keys:
            registry.async_remove(registry_entry.entity_id)
            manager.materialized_sensor_keys.discard(key)
            continue

        # beta.28 could materialize Garmin's broad daytime "Awake duration"
        # as last-sleep awake time. Revalidate that one key during migration.
        if key == "last_sleep_awake":
            sleep = manager.latest_sleep()
            if sleep is None or sleep.awake_s is None:
                registry.async_remove(registry_entry.entity_id)
                manager.materialized_sensor_keys.discard(key)

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
        elif self.entity_description.kind == "sleep":
            self.async_on_remove(
                self.manager.add_sleep_listener(self._update)
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
            "sleep_source",
        }
        if self.entity_description.metric in textual:
            return None
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        return self.entity_description.unit

    @staticmethod
    def _sleep_source_name(record):
        names = {
            "garmin_connect": "Garmin Connect",
            "sleep_as_android": "Sleep as Android",
            "oura": "Oura",
            "fitbit": "Fitbit",
            "withings": "Withings",
            "whoop": "WHOOP",
            "suunto": "Suunto",
            "sleepiq": "SleepIQ",
            "eight_sleep": "Eight Sleep",
            "eightsleep": "Eight Sleep",
        }
        domains = list(record.provider_domains or [])
        if not domains and record.provider_domain and record.provider_domain != "merged":
            domains = [record.provider_domain]
        if not domains:
            return None
        return " + ".join(names.get(domain, domain.replace("_", " ").title()) for domain in domains)

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

        if self.entity_description.kind == "sleep":
            r = self.manager.latest_sleep()
            if r is None:
                return None
            values = {
                "sleep_source": self._sleep_source_name(r),
                "sleep_duration": r.duration_s / 60 if r.duration_s is not None else None,
                "sleep_score": r.score,
                "sleep_efficiency": r.efficiency_percent,
                "sleep_time_in_bed": r.time_in_bed_s / 60 if r.time_in_bed_s is not None else None,
                "sleep_awake": r.awake_s / 60 if r.awake_s is not None else None,
                "sleep_light": r.light_sleep_s / 60 if r.light_sleep_s is not None else None,
                "sleep_deep": r.deep_sleep_s / 60 if r.deep_sleep_s is not None else None,
                "sleep_rem": r.rem_sleep_s / 60 if r.rem_sleep_s is not None else None,
                "sleep_hrv": r.hrv_ms,
                "sleep_average_hr": r.average_hr,
                "sleep_respiratory_rate": r.respiratory_rate,
                "sleep_spo2": r.spo2_percent,
                "sleep_recovery_score": r.recovery_score,
                "sleep_readiness_score": r.readiness_score,
            }
            value = values.get(m)
            return round(value, 2) if isinstance(value, (int, float)) else value

        if self.entity_description.kind == "sleep":
            record = self.manager.latest_sleep()
            if record is None:
                return {}
            return {
                **record.as_dict(),
                "merged_sources": list(record.provider_domains),
                "source_count": len(record.provider_domains),
            }

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
        sleep_long_term = e.get("sleep_long_term") or {}
        recorder_long_term = e.get("recorder_long_term") or {}
        long_term_map = {
            "training_load_7d": workout_long_term.get("banister_trimp_7d"),
            "training_load_28d": workout_long_term.get("banister_trimp_28d"),
            "training_load_change_7_vs_28": workout_long_term.get("training_load_change_7_vs_28_percent"),
            "training_days_28d": workout_long_term.get("active_training_days_28d"),
            "hrr_60s_long_term": workout_long_term.get("hrr_60s_mean_90d"),
            "hrr_60s_vs_90d": workout_long_term.get("hrr_60s_latest_vs_90d_bpm"),
            "sleep_duration_7d_mean": sleep_long_term.get("sleep_duration_7d_mean_min"),
            "sleep_duration_28d_mean": sleep_long_term.get("sleep_duration_28d_mean_min"),
            "sleep_duration_vs_28d": sleep_long_term.get("sleep_duration_vs_28d_min"),
            "sleep_duration_shortfall": sleep_long_term.get("sleep_duration_shortfall_min"),
            "sleep_midpoint_variability_14d": sleep_long_term.get("sleep_midpoint_variability_14d_min"),
            "sleep_hrv_7d_mean": sleep_long_term.get("sleep_hrv_7d_mean_ms"),
            "sleep_hrv_28d_mean": sleep_long_term.get("sleep_hrv_28d_mean_ms"),
            "sleep_hrv_vs_28d": sleep_long_term.get("sleep_hrv_vs_28d_percent"),
            "resting_hr_7d_mean": recorder_long_term.get("resting_hr_7d_mean"),
            "resting_hr_28d_mean": recorder_long_term.get("resting_hr_28d_mean"),
            "resting_hr_vs_28d": recorder_long_term.get("resting_hr_vs_28d"),
            "vo2max_28d_mean": recorder_long_term.get("vo2max_28d_mean"),
            "vo2max_trend_14_vs_previous_14": recorder_long_term.get("vo2max_trend_14_vs_previous_14_percent"),
        }
        if m in long_term_map:
            return long_term_map[m]

        value = e.get(m)
        if isinstance(value, float):
            return round(value, 2)
        return value

    @property
    def extra_state_attributes(self):
        """Return intentionally small attributes.

        Raw Live/Workout/Sleep entities expose provenance only. Methodology,
        explanations and scientific references are reserved for Fitness-owned
        Evaluation outputs, keeping high-frequency state rows small and avoiding
        duplicated provider diagnostics in Recorder.
        """
        m = self.entity_description.metric
        kind = self.entity_description.kind

        if kind == "live":
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
            info = self.manager.live_source_info(source_metric)
            return {
                key: info.get(key)
                for key in (
                    "source_entity",
                    "source_device_name",
                    "source_integration",
                )
                if info.get(key) is not None
            }

        if kind == "workout":
            workout = self.manager.latest_workout()
            if workout is None:
                return {}
            attrs = {}
            sources = workout.provider_domains or workout.sources
            if sources:
                attrs["sources"] = list(dict.fromkeys(sources))
            if workout.start:
                attrs["workout_start"] = workout.start
            field_source = (workout.field_sources or {}).get(m.removeprefix("workout_"))
            if field_source:
                attrs["field_source"] = field_source
            return attrs

        if kind == "sleep":
            sleep = self.manager.latest_sleep()
            if sleep is None:
                return {}
            attrs = {}
            sources = sleep.provider_domains or sleep.sources
            if sources:
                attrs["sources"] = list(dict.fromkeys(sources))
            if sleep.start:
                attrs["sleep_start"] = sleep.start
            if sleep.end:
                attrs["sleep_end"] = sleep.end
            field_name = {
                "sleep_duration": "duration_s",
                "sleep_time_in_bed": "time_in_bed_s",
                "sleep_awake": "awake_s",
                "sleep_light": "light_sleep_s",
                "sleep_deep": "deep_sleep_s",
                "sleep_rem": "rem_sleep_s",
                "sleep_hrv": "hrv_ms",
                "sleep_average_hr": "average_hr",
                "sleep_respiratory_rate": "respiratory_rate",
                "sleep_spo2": "spo2_percent",
                "sleep_score": "score",
                "sleep_efficiency": "efficiency_percent",
            }.get(m)
            field_source = (sleep.field_sources or {}).get(field_name) if field_name else None
            if field_source:
                attrs["field_source"] = field_source
            return attrs

        # Evaluation attributes are deliberately transparent: these are Fitness
        # calculations/interpretations rather than measurements from another device.
        base_explanation = sensor_explanation(
            self.manager._ai_language(),
            "evaluation",
            m,
        )
        provenance = self.manager.localized_evaluation_provenance(m)
        base_explanation.update(provenance)
        attrs = base_explanation

        evidence = {
            "vo2max_percent_predicted": ("friend_2017", "reference_equation"),
            "training_load_7d": ("training_load_consensus_2017", "supported"),
            "training_load_28d": ("training_load_consensus_2017", "supported"),
            "training_load_change_7_vs_28": ("training_load_consensus_2017", "descriptive"),
            "training_days_28d": ("training_load_consensus_2017", "descriptive"),
            "hrr_60s_long_term": ("heart_rate_recovery_1999", "established"),
            "hrr_60s_vs_90d": ("heart_rate_recovery_1999", "longitudinal_context"),
            "sleep_duration_7d_mean": ("adult_sleep_duration_consensus_2015", "descriptive"),
            "sleep_duration_28d_mean": ("adult_sleep_duration_consensus_2015", "descriptive"),
            "sleep_duration_vs_28d": ("adult_sleep_duration_consensus_2015", "personal_context"),
            "sleep_duration_shortfall": ("adult_sleep_duration_consensus_2015", "consensus_threshold"),
            "sleep_midpoint_variability_14d": ("sleep_regularity_metrics_2021", "descriptive"),
            "sleep_hrv_7d_mean": ("hrv_training_status_meta_2016", "longitudinal_context"),
            "sleep_hrv_28d_mean": ("hrv_training_status_meta_2016", "longitudinal_context"),
            "sleep_hrv_vs_28d": ("hrv_training_status_meta_2016", "longitudinal_context"),
            "resting_hr_7d_mean": ("hr_monitoring_training_status_2014", "longitudinal_context"),
            "resting_hr_28d_mean": ("hr_monitoring_training_status_2014", "longitudinal_context"),
            "resting_hr_vs_28d": ("hr_monitoring_training_status_2014", "longitudinal_context"),
            "vo2max_28d_mean": ("friend_2017", "descriptive"),
            "vo2max_trend_14_vs_previous_14": ("friend_2017", "descriptive"),
        }.get(m)
        if evidence:
            attrs["research_reference"] = evidence[0]
            attrs["evidence_level"] = evidence[1]

        if m in ("ai_general", "ai_workout"):
            full_text = self.manager.ai_general if m == "ai_general" else self.manager.ai_workout
            attrs.update({
                "text": full_text,
                "generated_at": self.manager.ai_last_generated,
                "ai_entity": self.manager.config.get("ai_entity") or "preferred_default",
                "role": "interpretation_only",
            })
        return attrs

