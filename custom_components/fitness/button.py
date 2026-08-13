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
        entities = []
        for transport in sorted(runtime.configured_transports):
            entities.extend([
                AdapterStartCaptureButton(runtime, transport),
                AdapterStopCaptureButton(runtime, transport),
            ])
        async_add_entities(entities, config_subentry_id=runtime.adapters_subentry_id)
        return

    manager = hass.data[DOMAIN][entry.entry_id]
    entities = []
    if runtime.live_enabled:
        entities.extend([
            StartWorkoutButton(manager, entry),
            PauseWorkoutButton(manager, entry),
            ResumeWorkoutButton(manager, entry),
            StopWorkoutButton(manager, entry),
        ])
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


class _AdapterButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, runtime, transport):
        self.runtime = runtime
        self.transport = transport
        self._attr_device_info = runtime.adapter_device_info(transport)

    @property
    def provider(self):
        return self.runtime.providers.get(self.transport)

    @property
    def available(self):
        return self.runtime.adapter_enabled(self.transport) and self.provider is not None


class AdapterStartCaptureButton(_AdapterButton):
    _attr_name = "Start capture"
    _attr_icon = "mdi:play"

    def __init__(self, runtime, transport):
        super().__init__(runtime, transport)
        self._attr_unique_id = f"fitness_{transport}_start_capture"

    async def async_press(self):
        provider = self.provider
        if provider is not None:
            await provider.async_start_capture()
            self.async_write_ha_state()


class AdapterStopCaptureButton(_AdapterButton):
    _attr_name = "Stop capture"
    _attr_icon = "mdi:stop"

    def __init__(self, runtime, transport):
        super().__init__(runtime, transport)
        self._attr_unique_id = f"fitness_{transport}_stop_capture"

    @property
    def available(self):
        return super().available and not self.runtime.transport_in_use(self.transport)

    async def async_press(self):
        if self.runtime.transport_in_use(self.transport):
            return
        provider = self.provider
        if provider is not None:
            await provider.async_stop_capture()
            self.async_write_ha_state()
