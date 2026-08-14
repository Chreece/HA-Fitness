"""Protocol event entities for physical Fitness sensors."""
from __future__ import annotations

from homeassistant.components.event import EventEntity

from .live import get_live_runtime
from .live.runtime import HUB_ENTRY_TYPE


def _event_capabilities(sensor) -> set[str]:
    result: set[str] = set()
    for endpoint in sensor.endpoints.values():
        mapping = endpoint.metadata.get("protocol_events") or {}
        if isinstance(mapping, dict):
            values = mapping.get(endpoint.transport) or []
            result.update(str(value) for value in values)
        elif isinstance(mapping, (list, tuple, set)):
            result.update(str(value) for value in mapping)
    return result


class PhysicalProtocolEvent(EventEntity):
    """One semantic event capability exposed by an ANT+/BLE physical sensor."""

    _attr_has_entity_name = True
    _attr_event_types = ["event"]

    def __init__(self, runtime, sensor_id: str, event_key: str) -> None:
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self.event_key = str(event_key)
        self._attr_name = self.event_key.replace("_event", "").replace("_", " ").title()
        self._attr_unique_id = f"fitness_{self.sensor_id}_event_{self.event_key}"
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.runtime.add_sensor_event_listener(
                self.sensor_id, self.event_key, self._handle_event
            )
        )

    def _handle_event(self, event_type: str, data: dict) -> None:
        # The semantic capability is represented by the entity itself. Keep one
        # stable HA event type and retain protocol specifics in event attributes.
        payload = {"capability": self.event_key, **dict(data or {})}
        self._trigger_event("event", payload)
        self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data.get("entry_type") != HUB_ENTRY_TYPE:
        return
    runtime = get_live_runtime(hass)
    materialized: set[tuple[str, str]] = set()

    def _collect() -> None:
        entities = []
        for sensor in runtime.sensors.values():
            sensor_id = runtime.resolve_sensor_id(sensor.sensor_id)
            if not runtime.sensor_is_accepted(sensor_id):
                continue
            for event_key in sorted(_event_capabilities(sensor)):
                token = (sensor_id, event_key)
                if token in materialized:
                    continue
                materialized.add(token)
                entities.append(PhysicalProtocolEvent(runtime, sensor_id, event_key))
        if entities:
            subentry = runtime.ensure_sensors_subentry()
            async_add_entities(
                entities,
                config_subentry_id=subentry.subentry_id if subentry else None,
            )

    _collect()
    entry.async_on_unload(runtime.add_structure_listener(_collect))
