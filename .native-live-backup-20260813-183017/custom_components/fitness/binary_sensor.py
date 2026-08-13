"""Fitness live-adapter and assigned-sensor diagnostics."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_LIVE_SENSOR_IDS, DOMAIN
from .live import get_live_runtime


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    entities = []

    # Global adapter diagnostics belong to one infrastructure owner only, and
    # remain present while a configured adapter is disabled/unloaded.
    if next(iter(runtime.profile_entries), None) == entry.entry_id:
        for transport in sorted(runtime.configured_transports):
            entities.extend(
                [
                    AdapterAvailable(runtime, transport),
                    AdapterCapture(runtime, transport),
                    AdapterProblem(runtime, transport),
                ]
            )

    selected = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
    for sensor_id in selected:
        entities.append(LiveSensorAvailable(runtime, entry, sensor_id))

    async_add_entities(entities)


class _AdapterBase(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, transport):
        self.runtime = runtime
        self.transport = transport
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"live_adapter:{transport}")},
            name=f"Fitness {transport.upper()} Adapter",
            manufacturer="Fitness",
            model=f"{transport.upper()} live transport",
        )

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
            "known_sensors": sum(
                1 for sensor in self.runtime.sensors.values() if sensor.transport == self.transport
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
        provider = self.provider
        return bool(provider and provider.available)


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
        # No receiver/hardware is intentionally NOT a fault.
        return bool(provider and provider.last_error)


class LiveSensorAvailable(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Available"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:heart-pulse"

    def __init__(self, runtime, entry, sensor_id: str):
        self.runtime = runtime
        self.entry = entry
        self.sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_{sensor_id}_available"
        sensor = runtime.sensors.get(sensor_id)
        name = sensor.name if sensor else sensor_id
        transport = sensor.transport if sensor else sensor_id.split(":", 1)[0]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"live_sensor:{sensor_id}")},
            name=name,
            manufacturer=("Bluetooth SIG" if transport == "bluetooth" else "ANT+"),
            model=f"{transport.upper()} fitness sensor",
        )

    @property
    def is_on(self):
        sensor = self.runtime.sensors.get(self.sensor_id)
        return bool(sensor and sensor.available)

    @property
    def extra_state_attributes(self):
        sensor = self.runtime.sensors.get(self.sensor_id)
        if sensor is None:
            return {"sensor_id": self.sensor_id, "profile": self.entry.title}
        return {
            "sensor_id": sensor.sensor_id,
            "transport": sensor.transport,
            "capabilities": sorted(sensor.capabilities),
            "address": sensor.address,
            "source": sensor.source,
            "rssi": sensor.rssi,
            "last_seen": sensor.last_seen.isoformat() if sensor.last_seen else None,
            "profile": self.entry.title,
        }
