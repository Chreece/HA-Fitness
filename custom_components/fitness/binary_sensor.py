"""Fitness Local Sensors diagnostics."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from .live import get_live_runtime
from .live.runtime import HUB_ENTRY_TYPE


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    if entry.data.get("entry_type") != HUB_ENTRY_TYPE:
        return
    adapter_entities = []
    for transport in sorted(runtime.adapter_entity_transports):
        adapter_entities.extend([AdapterAvailable(runtime, transport), AdapterProblem(runtime, transport)])
        if transport == "bluetooth":
            adapter_entities.append(AdapterCapture(runtime, transport))
    async_add_entities(adapter_entities, config_subentry_id=runtime.adapters_subentry_id)

    materialized_receivers: set[str] = set()
    def _add_ant_receiver_diagnostics():
        added = []
        for stable_key in runtime.ant_receiver_records():
            if stable_key in materialized_receivers:
                continue
            materialized_receivers.add(stable_key)
            added.extend([
                AntReceiverAvailable(runtime, stable_key),
                AntReceiverCapture(runtime, stable_key),
                AntReceiverProblem(runtime, stable_key),
            ])
        if added:
            async_add_entities(added, config_subentry_id=runtime.adapters_subentry_id)
    _add_ant_receiver_diagnostics()
    entry.async_on_unload(runtime.add_listener(_add_ant_receiver_diagnostics))

    sensor_entities = [
        LiveSensorAvailable(runtime, sensor.sensor_id)
        for sensor in runtime.sensors.values()
        if runtime.sensor_is_accepted(sensor.sensor_id)
    ]
    async_add_entities(
        sensor_entities,
        config_subentry_id=runtime.sensors_subentry_id,
    )


class _RuntimeEntity(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_added_to_hass(self):
        self.async_on_remove(self.runtime.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()


class _AdapterBase(_RuntimeEntity):
    def __init__(self, runtime, transport):
        self.runtime = runtime
        self.transport = transport
        self._attr_device_info = runtime.adapter_device_info(transport)

    @property
    def provider(self):
        return self.runtime.providers.get(self.transport)

    @property
    def extra_state_attributes(self):
        provider = self.provider
        return {
            "configured": self.runtime.adapter_configured(self.transport),
            "enabled": self.runtime.adapter_enabled(self.transport),
            "receiver_count": getattr(provider, "receiver_count", 0) if provider else 0,
            "connected_sensor_count": getattr(provider, "connected_sensor_count", 0) if provider else 0,
            "known_physical_sensors": sum(
                1 for sensor in self.runtime.sensors.values() if self.transport in sensor.transports
            ),
            "receivers": getattr(provider, "receiver_details", []) if provider else [],
            "last_error": getattr(provider, "last_error", None) if provider else None,
        }


class AdapterAvailable(_AdapterBase):
    _attr_name = "Receiver available"
    _attr_icon = "mdi:access-point"

    def __init__(self, *args):
        super().__init__(*args)
        self._attr_unique_id = f"fitness_{self.transport}_receiver_available"

    @property
    def is_on(self):
        return self.runtime.adapter_available(self.transport)


class AdapterCapture(_AdapterBase):
    _attr_name = "Capture active"
    _attr_icon = "mdi:record-rec"

    def __init__(self, *args):
        super().__init__(*args)
        self._attr_unique_id = f"fitness_{self.transport}_capture_active"

    @property
    def is_on(self):
        provider = self.provider
        return bool(provider and provider.capture_active)


class AdapterProblem(_AdapterBase):
    _attr_name = "Problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, *args):
        super().__init__(*args)
        self._attr_unique_id = f"fitness_{self.transport}_problem"

    @property
    def is_on(self):
        provider = self.provider
        # Waiting for local/remote receiver hardware is not a fault.
        return bool(provider and provider.last_error)


class LiveSensorAvailable(_RuntimeEntity):
    _attr_name = "Available"
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, runtime, sensor_id: str):
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self._attr_unique_id = f"fitness_{self.sensor_id}_available"
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    @property
    def is_on(self):
        sensor = self.runtime.sensors.get(self.sensor_id)
        return bool(sensor and sensor.available)

    @property
    def extra_state_attributes(self):
        sensor = self.runtime.sensors.get(self.sensor_id)
        if sensor is None:
            return {"sensor_id": self.sensor_id}
        return {
            "sensor_id": sensor.sensor_id,
            "name": sensor.name,
            "capabilities": sorted(sensor.capabilities),
            "preferred_transport": sensor.preferred_transport,
            "active_transport": sensor.active_transport,
            "available_transports": sorted(sensor.transports),
            "transport_details": self.runtime.sensor_transport_details(self.sensor_id),
        }


class _AntReceiverDiagnostic(_RuntimeEntity):
    def __init__(self, runtime, stable_key: str):
        self.runtime = runtime
        self.stable_key = stable_key
        self._attr_device_info = runtime.ant_receiver_device_info(stable_key)

    @property
    def record(self):
        return self.runtime.ant_receiver_records().get(self.stable_key)

    @property
    def extra_state_attributes(self):
        record = self.record
        if record is None:
            return {}
        return {
            "connection": record.connection,
            "sources": record.sources,
            "error": record.capture_error,
        }


class AntReceiverAvailable(_AntReceiverDiagnostic):
    _attr_name = "Available"
    _attr_icon = "mdi:usb"
    def __init__(self, runtime, stable_key: str):
        super().__init__(runtime, stable_key)
        self._attr_unique_id = f"fitness_ant_receiver_{stable_key}_available"
    @property
    def is_on(self):
        return bool(self.record and self.record.available)


class AntReceiverCapture(_AntReceiverDiagnostic):
    _attr_name = "Capture active"
    _attr_icon = "mdi:record-rec"
    def __init__(self, runtime, stable_key: str):
        super().__init__(runtime, stable_key)
        self._attr_unique_id = f"fitness_ant_receiver_{stable_key}_capture_active"
    @property
    def is_on(self):
        return bool(self.record and self.record.displayed_capture)


class AntReceiverProblem(_AntReceiverDiagnostic):
    _attr_name = "Problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    def __init__(self, runtime, stable_key: str):
        super().__init__(runtime, stable_key)
        self._attr_unique_id = f"fitness_ant_receiver_{stable_key}_problem"
    @property
    def is_on(self):
        return bool(self.record and self.record.capture_error)
