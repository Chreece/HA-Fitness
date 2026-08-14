"""Runtime Fitness room selection."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN
from .entity import device_info


async def async_setup_entry(hass, entry, async_add_entities):
    from .live import get_live_runtime
    from .live.runtime import HUB_ENTRY_TYPE
    runtime = get_live_runtime(hass)
    if entry.data.get("entry_type") == HUB_ENTRY_TYPE:
        entities = [
            FitnessSensorWorkoutOwnerSelect(runtime, sensor.sensor_id)
            for sensor in runtime.sensors.values()
            if runtime.sensor_is_accepted(sensor.sensor_id)
        ]
        async_add_entities(entities)
        return
    if not (
        runtime.live_surface_available
        and runtime.profile_has_assigned_live_sensor(entry)
    ):
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


class FitnessSensorWorkoutOwnerSelect(SelectEntity):
    """Explicitly transfer one physical sensor between overlapping workouts."""

    _attr_has_entity_name = True
    _attr_translation_key = "sensor_workout_owner"
    _attr_icon = "mdi:account-switch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime, sensor_id: str):
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self._attr_unique_id = f"fitness_{self.sensor_id}_workout_owner_select"
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "workout_owner", None, self._update
            )
        )

    def _update(self):
        self.async_write_ha_state()

    def _profile_map(self) -> dict[str, str]:
        result = {}
        sensor_id = self.runtime.resolve_sensor_id(self.sensor_id)
        for entry in self.runtime.profile_entries.values():
            if sensor_id not in self.runtime.selected_sensor_ids(entry):
                continue
            name = str(
                entry.options.get("profile_name", entry.data.get("profile_name", entry.title))
                or entry.title
            )
            option = name
            if option in result:
                option = f"{name} ({entry.entry_id[:6]})"
            result[option] = entry.entry_id
        return result

    @property
    def options(self) -> list[str]:
        return list(self._profile_map())

    @property
    def current_option(self) -> str | None:
        owner = self.runtime.sensor_workout_owner(self.sensor_id)
        if owner is None:
            return None
        for option, entry_id in self._profile_map().items():
            if entry_id == owner:
                return option
        return None

    @property
    def available(self) -> bool:
        return self.runtime.sensor_workout_owner(self.sensor_id) is not None

    async def async_select_option(self, option: str) -> None:
        mapping = self._profile_map()
        target = mapping.get(option)
        if target is None:
            return
        await self.runtime.async_transfer_workout_sensor_owner(self.sensor_id, target)


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
