"""Runtime Fitness room selection."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import device_info


async def async_setup_entry(hass, entry, async_add_entities):
    from .live import get_live_runtime
    runtime = get_live_runtime(hass)
    if not runtime.live_surface_available:
        return
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FitnessWorkoutRoomSelect(
                manager,
                entry,
            )
        ]
    )


class FitnessWorkoutRoomSelect(SelectEntity):
    """Select the room used for live Fitness feedback."""

    _attr_has_entity_name = True
    _attr_translation_key = "workout_room"
    _attr_icon = "mdi:home-map-marker"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, entry):
        self.manager = manager
        self.entry = entry
        self._attr_unique_id = (
            f"{entry.entry_id}_workout_room"
        )
        self._attr_device_info = device_info(
            entry,
            "live",
        )

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.manager.add_listener(
                self._update
            )
        )

    def _update(self):
        self.async_write_ha_state()

    def _area_map(self) -> dict[str, str | None]:
        """Map display option to persistent area ID, including no-room."""
        result: dict[str, str | None] = {
            "No room": None,
        }

        for area_id, name in self.manager.available_feedback_areas():
            # Area names are the human-facing options. If an installation ever
            # contains duplicate names, append the ID to keep options unique.
            option = name
            if option in result:
                option = f"{name} ({area_id})"
            result[option] = area_id

        return result

    @property
    def options(self) -> list[str]:
        return list(self._area_map())

    @property
    def current_option(self) -> str | None:
        selected = self.manager.selected_feedback_area_id

        if selected is None:
            return "No room"

        for option, area_id in self._area_map().items():
            if area_id == selected:
                return option

        return "No room"

    async def async_select_option(
        self,
        option: str,
    ) -> None:
        mapping = self._area_map()

        if option not in mapping:
            return

        await self.manager.async_select_feedback_area(
            mapping[option]
        )
