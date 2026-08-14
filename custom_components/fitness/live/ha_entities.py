"""Home Assistant entities for global Local Sensors infrastructure."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, PERCENTAGE

from ..const import (
    METRIC_ALTITUDE,
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
)

METRIC_META = {
    METRIC_HEART_RATE: ("Heart rate", "bpm", "mdi:heart-pulse"),
    METRIC_POWER: ("Power", "W", "mdi:flash"),
    METRIC_CADENCE: ("Cadence", "1/min", "mdi:rotate-right"),
    METRIC_SPEED: ("Speed", "km/h", "mdi:speedometer"),
    METRIC_DISTANCE: ("Distance", "km", "mdi:map-marker-distance"),
    METRIC_ALTITUDE: ("Altitude", "m", "mdi:elevation-rise"),
}


class _PhysicalSensorEntity(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, runtime, sensor_id: str) -> None:
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    @property
    def _value_listener_token(self) -> tuple[str, str | None]:
        raise NotImplementedError

    async def async_added_to_hass(self):
        kind, key = self._value_listener_token
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, kind, key, self._update
            )
        )

    def _update(self):
        self.async_write_ha_state()


class PhysicalMetricSensor(_PhysicalSensorEntity):
    def __init__(self, runtime, sensor_id: str, metric: str) -> None:
        super().__init__(runtime, sensor_id)
        self.metric = metric
        name, unit, icon = METRIC_META[metric]
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"fitness_{sensor_id}_{metric}"

    @property
    def _value_listener_token(self) -> tuple[str, str | None]:
        return ("metric", self.metric)

    @property
    def native_value(self):
        return self.runtime.sensor_values.get(self.sensor_id, {}).get(self.metric)

    @property
    def extra_state_attributes(self):
        return {
            "transport": self.runtime.sensor_value_transport.get(self.sensor_id, {}).get(self.metric),
        }


class PhysicalPassiveSensor(_PhysicalSensorEntity):
    """Connectionless BLE value such as battery."""

    def __init__(self, runtime, sensor_id: str, key: str) -> None:
        super().__init__(runtime, sensor_id)
        self.key = key
        meta = runtime.sensor_passive_meta.get(sensor_id, {}).get(key, {})
        self._attr_name = str(meta.get("name") or key.replace("_", " ").title())
        self._attr_unique_id = f"fitness_{sensor_id}_passive_{key}"
        unit = meta.get("unit")
        if unit:
            self._attr_native_unit_of_measurement = unit
        if meta.get("icon"):
            self._attr_icon = meta["icon"]
        if meta.get("device_class") == "battery":
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_native_unit_of_measurement = PERCENTAGE
        if meta.get("state_class") == "measurement":
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def _value_listener_token(self) -> tuple[str, str | None]:
        return ("passive", self.key)

    @property
    def native_value(self):
        return self.runtime.sensor_passive_values.get(self.sensor_id, {}).get(self.key)

    @property
    def extra_state_attributes(self):
        return {"transport": "bluetooth", "passive": True}


class PhysicalActiveTransportSensor(_PhysicalSensorEntity):
    _attr_name = "Active transport"
    _attr_icon = "mdi:transit-connection-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, sensor_id: str) -> None:
        super().__init__(runtime, sensor_id)
        self._attr_unique_id = f"fitness_{sensor_id}_active_transport"

    @property
    def _value_listener_token(self) -> tuple[str, str | None]:
        return ("active_transport", None)

    @property
    def native_value(self):
        sensor = self.runtime.sensors.get(self.sensor_id)
        return sensor.active_transport if sensor and sensor.active_transport else "idle"

    @property
    def extra_state_attributes(self):
        sensor = self.runtime.sensors.get(self.sensor_id)
        if sensor is None:
            return {}
        details = self.runtime.sensor_transport_details(self.sensor_id)
        # Keep recorder-facing attributes structural. RSSI/last_seen are volatile and
        # can change several times per second while a sensor is broadcasting.
        for item in details.values():
            item.pop("rssi", None)
            item.pop("last_seen", None)
        return {
            "preferred_transport": sensor.preferred_transport,
            "available_transports": [
                t for t in ("antplus", "bluetooth") if t in sensor.transports
            ],
            "transport_details": details,
        }


class PhysicalLastSeenSensor(_PhysicalSensorEntity):
    _attr_name = "Last seen"
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, runtime, sensor_id: str) -> None:
        super().__init__(runtime, sensor_id)
        self._attr_unique_id = f"fitness_{sensor_id}_last_seen"
        self._last_bucket: datetime | None = None

    @property
    def _value_listener_token(self) -> tuple[str, str | None]:
        return ("last_seen", None)

    @property
    def native_value(self) -> datetime | None:
        sensor = self.runtime.sensors.get(self.sensor_id)
        seen = sensor.last_seen if sensor else None
        if seen is None:
            return None
        # Five-minute precision is plenty for diagnostics and prevents a manually
        # enabled Last seen entity from generating Recorder rows per radio packet.
        return seen.replace(minute=(seen.minute // 5) * 5, second=0, microsecond=0)

    def _update(self):
        bucket = self.native_value
        if bucket == self._last_bucket:
            return
        self._last_bucket = bucket
        self.async_write_ha_state()


async def async_setup_sensor_entities(runtime, async_add_entities) -> None:
    """Materialize accepted physical-sensor entities without reloading the hub."""
    materialized: set[tuple[str, str, str]] = set()

    def _collect() -> None:
        accepted_ids = {
            sensor.sensor_id
            for sensor in runtime.sensors.values()
            if runtime.sensor_is_accepted(sensor.sensor_id)
        }
        # Device deletion can later re-use the same canonical physical ID. Forget
        # local materialization markers once a sensor is no longer accepted/present.
        materialized.intersection_update(
            item for item in materialized if item[0] in accepted_ids
        )

        entities = []
        for sensor_id in sorted(accepted_ids):
            sensor = runtime.sensors.get(sensor_id)
            if sensor is None:
                continue
            runtime.ensure_sensor_device(sensor_id)

            key = (sensor_id, "diagnostic", "active_transport")
            if key not in materialized:
                materialized.add(key)
                entities.append(PhysicalActiveTransportSensor(runtime, sensor_id))

            key = (sensor_id, "diagnostic", "last_seen")
            if key not in materialized:
                materialized.add(key)
                entities.append(PhysicalLastSeenSensor(runtime, sensor_id))

            for metric in METRIC_META:
                if metric not in sensor.capabilities:
                    continue
                key = (sensor_id, "metric", metric)
                if key in materialized:
                    continue
                materialized.add(key)
                entities.append(PhysicalMetricSensor(runtime, sensor_id, metric))

            for passive_key in sorted(runtime.sensor_passive_values.get(sensor_id, {})):
                key = (sensor_id, "passive", passive_key)
                if key in materialized:
                    continue
                materialized.add(key)
                entities.append(PhysicalPassiveSensor(runtime, sensor_id, passive_key))

        if entities:
            subentry = runtime.ensure_sensors_subentry()
            async_add_entities(
                entities,
                config_subentry_id=subentry.subentry_id if subentry is not None else None,
            )

    _collect()
    runtime.hub_entry.async_on_unload(runtime.add_structure_listener(_collect))
