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
        # Physical sensors expose only genuinely sensor-specific actions such as
        # an optional Bluetooth GATT connect/disconnect operation. ANT receiver
        # scan capture remains receiver-scoped hardware control.
        receiver_materialized: set[str] = set()

        def _add_ant_receivers():
            added = []
            for stable_key in runtime.ant_receiver_records():
                if stable_key in receiver_materialized:
                    continue
                receiver_materialized.add(stable_key)
                added.extend([
                    AntReceiverStartCaptureButton(runtime, stable_key),
                    AntReceiverStopCaptureButton(runtime, stable_key),
                ])
            if added:
                async_add_entities(
                    added,
                    config_subentry_id=runtime.adapter_subentry_id("antplus"),
                )

        _add_ant_receivers()
        entry.async_on_unload(runtime.add_listener(_add_ant_receivers))

        sensor_button_materialized: set[tuple[str, str]] = set()

        def _add_sensor_buttons():
            added = []
            for sensor in runtime.sensors.values():
                sensor_id = runtime.resolve_sensor_id(sensor.sensor_id)
                if not runtime.sensor_is_accepted(sensor_id):
                    continue
                if "bluetooth" in sensor.endpoints and runtime.bluetooth_gatt_supported(sensor):
                    key = (sensor_id, "gatt")
                    if key not in sensor_button_materialized:
                        sensor_button_materialized.add(key)
                        added.extend([
                            SensorGattConnectButton(runtime, sensor_id),
                            SensorGattDisconnectButton(runtime, sensor_id),
                        ])
            if added:
                subentry = runtime.ensure_sensors_subentry()
                async_add_entities(
                    added,
                    config_subentry_id=subentry.subentry_id if subentry else None,
                )

        _add_sensor_buttons()
        entry.async_on_unload(runtime.add_structure_listener(_add_sensor_buttons))
        return

    manager = hass.data[DOMAIN][entry.entry_id]
    entities = []
    if runtime.live_surface_available and runtime.profile_has_assigned_live_sensor(entry):
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


class _SensorGattButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, runtime, sensor_id: str):
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "gatt_connection", None, self._update
            )
        )
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "active_transport", None, self._update
            )
        )

    def _update(self):
        self.async_write_ha_state()

    @property
    def sensor(self):
        return self.runtime.sensors.get(self.runtime.resolve_sensor_id(self.sensor_id))

    @property
    def provider(self):
        return self.runtime.providers.get("bluetooth")


class SensorGattConnectButton(_SensorGattButton):
    _attr_name = "Connect Bluetooth GATT"
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(self, runtime, sensor_id: str):
        super().__init__(runtime, sensor_id)
        self._attr_unique_id = f"fitness_{self.sensor_id}_gatt_connect"

    @property
    def available(self):
        sensor = self.sensor
        return bool(
            sensor is not None
            and self.runtime.bluetooth_gatt_capable(sensor)
            and not self.runtime.bluetooth_gatt_connected(self.sensor_id)
            and not self.runtime.ant_data_fresh(sensor)
        )

    async def async_press(self):
        await self.runtime.async_manual_gatt_connect(self.sensor_id)


class SensorGattDisconnectButton(_SensorGattButton):
    _attr_name = "Disconnect Bluetooth GATT"
    _attr_icon = "mdi:bluetooth-off"

    def __init__(self, runtime, sensor_id: str):
        super().__init__(runtime, sensor_id)
        self._attr_unique_id = f"fitness_{self.sensor_id}_gatt_disconnect"

    @property
    def available(self):
        provider = self.provider
        if provider is None or not self.runtime.bluetooth_gatt_connected(self.sensor_id):
            return False
        # Never let a manual button disconnect a connection currently owned by
        # one or more active Fitness profiles. Shared ownership is authoritative.
        checker = getattr(provider, "sensor_has_automatic_users", None)
        return not bool(checker(self.sensor_id)) if checker is not None else True

    async def async_press(self):
        await self.runtime.async_manual_gatt_disconnect(self.sensor_id)
