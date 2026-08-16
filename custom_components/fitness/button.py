"""Fitness control buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .entity import device_info
from .live import get_live_runtime


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    from .live.runtime import HUB_ENTRY_TYPE

    if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
        # Native sensor transport is automatic. The adapter Activate switches
        # own module lifecycle and Bluetooth GATT connects/disconnects only when
        # workout routing requires it, so the hub exposes no transport buttons.
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
