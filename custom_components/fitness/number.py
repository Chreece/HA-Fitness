"""Runtime Fitness numeric inputs."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode

from .const import DOMAIN
from .entity import device_info


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FitnessSessionRpeNumber(manager, entry)])


class FitnessSessionRpeNumber(NumberEntity):
    """Integer 1-10 session rating of perceived exertion."""

    _attr_has_entity_name = True
    _attr_translation_key = "session_rpe"
    _attr_icon = "mdi:gauge"
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, manager, entry):
        self.manager = manager
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_session_rpe"
        self._attr_device_info = device_info(entry, "workout")

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()

    @property
    def native_value(self):
        return self.manager.session_rpe_value()

    @property
    def available(self):
        return bool(
            self.manager.session_active
            or self.manager.session_armed
            or self.manager.latest_workout() is not None
        )

    async def async_set_native_value(self, value: float) -> None:
        await self.manager.async_set_session_rpe(int(round(value)))
