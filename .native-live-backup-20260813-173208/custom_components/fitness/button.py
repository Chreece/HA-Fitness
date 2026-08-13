"""Fitness control buttons."""

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import device_info


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
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

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()


class StartWorkoutButton(BaseFitnessButton):
    _attr_translation_key = "start_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_start_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return not self.manager.session_active

    async def async_press(self):
        await self.manager.async_start_session()


class PauseWorkoutButton(BaseFitnessButton):
    _attr_translation_key = "pause_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_pause_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return self.manager.session_active and not self.manager.session_paused

    async def async_press(self):
        await self.manager.async_pause_session()


class ResumeWorkoutButton(BaseFitnessButton):
    _attr_translation_key = "resume_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_resume_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return self.manager.session_active and self.manager.session_paused

    async def async_press(self):
        await self.manager.async_resume_session()


class StopWorkoutButton(BaseFitnessButton):
    _attr_translation_key = "stop_workout"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_stop_workout"
        self._attr_device_info = device_info(entry, "live")

    @property
    def available(self):
        return self.manager.session_active

    async def async_press(self):
        await self.manager.async_stop_session()


class RegenerateEvaluationButton(BaseFitnessButton):
    _attr_translation_key = "regenerate_ai_evaluation"

    def __init__(self, manager, entry):
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_regenerate_ai"
        self._attr_device_info = device_info(entry, "evaluation")

    async def async_press(self):
        await self.manager.async_generate_ai(general=True, workout=True, raise_on_failure=True)
