"""Fitness control buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CAPABILITY_WORKOUT_HISTORY, DOMAIN
from .entity import device_info
from .live import get_live_runtime


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    from .live.runtime import HUB_ENTRY_TYPE

    if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
        # Normal live transport is automatic. Archive-capable devices expose one
        # explicit retry action in addition to their automatic reconnect policy.
        materialized: set[str] = set()
        from homeassistant.helpers import entity_registry as er

        entity_registry = er.async_get(hass)

        def _collect_archive_buttons() -> None:
            added = []
            accepted_ids = {
                runtime.resolve_sensor_id(sensor.sensor_id)
                for sensor in runtime.sensors.values()
                if runtime.sensor_is_accepted(sensor.sensor_id)
            }
            materialized.intersection_update(accepted_ids)
            for sensor in runtime.sensors.values():
                sensor_id = runtime.resolve_sensor_id(sensor.sensor_id)
                unique_id = f"fitness_{sensor_id}_cycplus_sync_workouts"
                if sensor_id in materialized:
                    if entity_registry.async_get_entity_id(
                        "button", DOMAIN, unique_id
                    ) is not None:
                        continue
                    materialized.discard(sensor_id)
                if (
                    CAPABILITY_WORKOUT_HISTORY not in sensor.capabilities
                    or not runtime.sensor_is_accepted(sensor_id)
                ):
                    continue
                materialized.add(sensor_id)
                added.append(CycplusSyncWorkoutsButton(runtime, sensor_id))
            if added:
                subentry = runtime.ensure_sensors_subentry()
                async_add_entities(
                    added,
                    config_subentry_id=(
                        subentry.subentry_id if subentry is not None else None
                    ),
                )

        _collect_archive_buttons()
        entry.async_on_unload(runtime.add_structure_listener(_collect_archive_buttons))
        return

    manager = hass.data[DOMAIN][entry.entry_id]
    # Live controls are stable profile infrastructure. Sensor assignment only
    # changes availability/routing; it must never require a profile reload just
    # to create or remove controls.
    entities = [
        StartWorkoutButton(manager, entry),
        PauseWorkoutButton(manager, entry),
        ResumeWorkoutButton(manager, entry),
        StopWorkoutButton(manager, entry),
    ]
    if manager.config.get("ai_enabled"):
        entities.append(RegenerateEvaluationButton(manager, entry))
    async_add_entities(entities)



class BaseFitnessButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, manager, entry):
        self.manager = manager
        self.entry = entry
        self.runtime = get_live_runtime(manager.hass)

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()


class CycplusSyncWorkoutsButton(ButtonEntity):
    """Request an immediate M1 archive retry without blocking the service call."""

    _attr_has_entity_name = True
    _attr_translation_key = "cycplus_sync_workouts"
    _attr_icon = "mdi:calendar-sync"

    def __init__(self, runtime, sensor_id: str):
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self._attr_unique_id = f"fitness_{self.sensor_id}_cycplus_sync_workouts"
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "availability", None, self._update
            )
        )
        self.async_on_remove(self.runtime.add_structure_listener(self._update))

    def _update(self):
        self.async_write_ha_state()

    @property
    def available(self):
        self.sensor_id = self.runtime.resolve_sensor_id(self.sensor_id)
        sensor = self.runtime.sensors.get(self.sensor_id)
        provider = self.runtime.providers.get("bluetooth")
        return bool(
            sensor
            and sensor.available
            and provider is not None
            and self.runtime.sensor_assigned_profile_ids(self.sensor_id)
        )

    async def async_press(self):
        self.sensor_id = self.runtime.resolve_sensor_id(self.sensor_id)
        provider = self.runtime.providers.get("bluetooth")
        coordinator = getattr(provider, "cycplus_m1", None) if provider else None
        if coordinator is not None:
            coordinator.schedule(self.sensor_id, delay=0.0, force=True)


class BaseLiveFitnessButton(BaseFitnessButton):
    """Profile Live control updated only by the bounded live notification path."""

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.add_live_listener(self._update))


class StartWorkoutButton(BaseLiveFitnessButton):
    _attr_translation_key = "start_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_start_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return bool(
            self.runtime.profile_has_assigned_live_sensor(self.entry)
            and not self.manager.session_active
            and not self.manager.session_armed
        )

    async def async_press(self):
        await self.manager.async_start_session()


class PauseWorkoutButton(BaseLiveFitnessButton):
    _attr_translation_key = "pause_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_pause_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return bool((self.manager.session_active or self.manager.session_armed) and not self.manager.session_paused)

    async def async_press(self):
        await self.manager.async_pause_session()


class ResumeWorkoutButton(BaseLiveFitnessButton):
    _attr_translation_key = "resume_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_resume_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return bool((self.manager.session_active or self.manager.session_armed) and self.manager.session_paused)

    async def async_press(self):
        await self.manager.async_resume_session()


class StopWorkoutButton(BaseLiveFitnessButton):
    _attr_translation_key = "stop_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_stop_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return self.manager.session_active or self.manager.session_armed

    async def async_press(self):
        await self.manager.async_stop_session()


class RegenerateEvaluationButton(BaseFitnessButton):
    _attr_translation_key = "regenerate_ai_evaluation"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_regenerate_ai"
        self._attr_device_info = device_info(entry, "evaluation")

    async def async_press(self):
        await self.manager.async_generate_ai(
            general=True, workout=True, raise_on_failure=True
        )
