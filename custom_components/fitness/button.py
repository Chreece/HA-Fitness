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
        # Bluetooth capture is a transport-level GATT/session control. ANT+
        # capture belongs to each physical receiver independently.
        entities = []
        if "bluetooth" in runtime.adapter_entity_transports:
            entities.extend([
                AdapterStartCaptureButton(runtime, "bluetooth"),
                AdapterStopCaptureButton(runtime, "bluetooth"),
            ])
        async_add_entities(entities, config_subentry_id=runtime.adapters_subentry_id)

        materialized: set[str] = set()
        def _add_ant_receivers():
            added = []
            for stable_key in runtime.ant_receiver_records():
                if stable_key in materialized:
                    continue
                materialized.add(stable_key)
                added.extend([
                    AntReceiverStartCaptureButton(runtime, stable_key),
                    AntReceiverStopCaptureButton(runtime, stable_key),
                ])
            if added:
                async_add_entities(added, config_subentry_id=runtime.adapters_subentry_id)
        _add_ant_receivers()
        entry.async_on_unload(runtime.add_listener(_add_ant_receivers))
        return

    manager = hass.data[DOMAIN][entry.entry_id]
    entities = []
    if runtime.live_surface_available:
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

    async def async_added_to_hass(self):
        self.async_on_remove(self.runtime.add_listener(self._runtime_update))

    def _runtime_update(self):
        self.async_write_ha_state()

    @property
    def available(self):
        return self.runtime.adapter_enabled(self.transport) and self.provider is not None


class AdapterStartCaptureButton(_AdapterButton):
    _attr_name = "Start capture"
    _attr_icon = "mdi:play"

    def __init__(self, runtime, transport):
        super().__init__(runtime, transport)
        self._attr_unique_id = f"fitness_{transport}_start_capture"

    @property
    def available(self):
        provider = self.provider
        return super().available and provider is not None and not provider.capture_active

    async def async_press(self):
        provider = self.provider
        if provider is not None:
            await provider.async_start_capture()
            self.runtime.notify_changed()


class AdapterStopCaptureButton(_AdapterButton):
    _attr_name = "Stop capture"
    _attr_icon = "mdi:stop"

    def __init__(self, runtime, transport):
        super().__init__(runtime, transport)
        self._attr_unique_id = f"fitness_{transport}_stop_capture"

    @property
    def available(self):
        provider = self.provider
        return (
            super().available
            and provider is not None
            and provider.capture_active
            and not self.runtime.transport_in_use(self.transport)
        )

    async def async_press(self):
        if self.runtime.transport_in_use(self.transport):
            return
        provider = self.provider
        if provider is not None:
            await provider.async_stop_capture()
            self.runtime.notify_changed()


class _AntReceiverButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, runtime, stable_key: str):
        self.runtime = runtime
        self.stable_key = stable_key
        self._attr_device_info = runtime.ant_receiver_device_info(stable_key)

    @property
    def provider(self):
        return self.runtime.providers.get("antplus")

    @property
    def record(self):
        return self.runtime.ant_receiver_records().get(self.stable_key)

    async def async_added_to_hass(self):
        self.async_on_remove(self.runtime.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()


class AntReceiverStartCaptureButton(_AntReceiverButton):
    _attr_name = "Start capture"
    _attr_icon = "mdi:play"

    def __init__(self, runtime, stable_key: str):
        super().__init__(runtime, stable_key)
        self._attr_unique_id = f"fitness_ant_receiver_{stable_key}_start_capture"

    @property
    def available(self):
        record = self.record
        return bool(
            self.runtime.adapter_enabled("antplus")
            and record is not None
            and record.available
            and not record.displayed_capture
        )

    async def async_press(self):
        provider = self.provider
        if provider and provider.adapter_manager and self.record is not None:
            await provider.adapter_manager.async_set_capture(self.stable_key, True)
            self.runtime.notify_changed()


class AntReceiverStopCaptureButton(_AntReceiverButton):
    _attr_name = "Stop capture"
    _attr_icon = "mdi:stop"

    def __init__(self, runtime, stable_key: str):
        super().__init__(runtime, stable_key)
        self._attr_unique_id = f"fitness_ant_receiver_{stable_key}_stop_capture"

    @property
    def available(self):
        record = self.record
        return bool(
            self.runtime.adapter_enabled("antplus")
            and record is not None
            and record.available
            and record.displayed_capture
            and not self.runtime.transport_in_use("antplus")
        )

    async def async_press(self):
        if self.runtime.transport_in_use("antplus"):
            return
        provider = self.provider
        if provider and provider.adapter_manager and self.record is not None:
            await provider.adapter_manager.async_set_capture(self.stable_key, False)
            self.runtime.notify_changed()
