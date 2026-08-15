"""Home Assistant entities for global Local Sensors infrastructure."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, PERCENTAGE

from ..const import (
    DOMAIN,
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

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "availability", None, self._update
            )
        )

    @property
    def available(self) -> bool:
        sensor = self.runtime.sensors.get(self.sensor_id)
        return bool(
            sensor is not None
            and sensor.available
            and self.native_value is not None
        )

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
        sources = dict(self.runtime.sensor_passive_sources.get(self.sensor_id, {}).get(self.key, {}))
        return {
            "transport": next(iter(sources), None) if len(sources) == 1 else "merged",
            "passive": True,
            "source_values": sources,
        }


class PhysicalDetailSensor(_PhysicalSensorEntity):
    """Merged protocol/device information retained as diagnostic entities."""

    def __init__(self, runtime, sensor_id: str, key: str) -> None:
        super().__init__(runtime, sensor_id)
        self.key = key
        meta = runtime.sensor_detail_meta.get(sensor_id, {}).get(key, {})
        self._attr_name = str(meta.get("name") or key.replace("_", " ").title())
        self._attr_unique_id = f"fitness_{sensor_id}_detail_{key}"
        unit = meta.get("unit")
        if unit:
            self._attr_native_unit_of_measurement = str(unit)
        if meta.get("icon"):
            self._attr_icon = str(meta["icon"])
        if meta.get("device_class"):
            self._attr_device_class = str(meta["device_class"])
        if meta.get("state_class") in {"measurement", "total", "total_increasing"}:
            self._attr_state_class = str(meta["state_class"])
        if str(meta.get("entity_category") or "").lower() == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = bool(meta.get("enabled_default", False))

    @property
    def _value_listener_token(self) -> tuple[str, str | None]:
        return ("detail", self.key)

    def _raw_value(self):
        return self.runtime.sensor_detail_values.get(self.sensor_id, {}).get(self.key)

    @property
    def native_value(self):
        value = self._raw_value()
        rendered = str(value) if isinstance(value, (dict, list, tuple, set)) else value
        # Home Assistant's state string is capped at 255 characters. Large raw
        # GATT/service/manufacturer diagnostics belong in attributes, not state.
        if isinstance(rendered, str) and len(rendered) > 255:
            return f"{len(rendered)} characters"
        return rendered

    @property
    def extra_state_attributes(self):
        value = self._raw_value()
        rendered = str(value) if isinstance(value, (dict, list, tuple, set)) else value
        attributes = {
            "source": self.runtime.sensor_detail_source.get(self.sensor_id, {}).get(self.key),
            "source_values": dict(self.runtime.sensor_detail_sources.get(self.sensor_id, {}).get(self.key, {})),
        }
        if isinstance(rendered, str) and len(rendered) > 255:
            attributes["full_value"] = rendered
        return attributes


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
        # Keep this enabled diagnostic entity tiny. Full ANT/GATT metadata already
        # has dedicated opt-in diagnostic entities and should not be duplicated in
        # Recorder attributes every time transport ownership changes.
        details = {
            transport: {
                "address": endpoint.address,
                "endpoint_id": endpoint.endpoint_id,
                "capabilities": sorted(endpoint.capabilities),
            }
            for transport, endpoint in sensor.endpoints.items()
        }
        return {
            "preferred_transport": sensor.preferred_transport,
            "known_transports": [
                t for t in ("antplus", "bluetooth") if t in sensor.transports
            ],
            "available_transports": [
                t for t in ("antplus", "bluetooth")
                if t in sensor.endpoints and sensor.endpoints[t].available
            ],
            "transport_details": details,
        }


class PhysicalWorkoutOwnerSensor(_PhysicalSensorEntity):
    """Diagnostic view of the exclusive workout lock for this physical sensor."""

    _attr_name = "Workout owner"
    _attr_icon = "mdi:account-lock-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, runtime, sensor_id: str) -> None:
        super().__init__(runtime, sensor_id)
        self._attr_unique_id = f"fitness_{sensor_id}_workout_owner"

    @property
    def _value_listener_token(self) -> tuple[str, str | None]:
        return ("workout_owner", None)

    @property
    def native_value(self):
        owner = self.runtime.sensor_workout_owner(self.sensor_id)
        if owner is None:
            return "free"
        entry = self.runtime.profile_entries.get(owner)
        return entry.title if entry is not None else owner

    @property
    def extra_state_attributes(self):
        owner = self.runtime.sensor_workout_owner(self.sensor_id)
        assigned = []
        for entry in self.runtime.profile_entries.values():
            if self.sensor_id in self.runtime.selected_sensor_ids(entry):
                assigned.append({"entry_id": entry.entry_id, "name": entry.title})
        return {
            "owner_entry_id": owner,
            "assigned_profiles": assigned,
            "release_policy": "when_all_overlapping_fitness_sessions_are_idle",
        }


class PhysicalSignalStrengthSensor(_PhysicalSensorEntity):
    """Merged radio signal diagnostic sampled on the low-rate Last-seen clock."""

    _attr_name = "Signal strength"
    _attr_icon = "mdi:signal"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = "dBm"
    _attr_entity_registry_enabled_default = False

    def __init__(self, runtime, sensor_id: str) -> None:
        super().__init__(runtime, sensor_id)
        self._attr_unique_id = f"fitness_{sensor_id}_signal_strength"

    @property
    def _value_listener_token(self) -> tuple[str, str | None]:
        # RSSI can change on every BLE advertisement. Sampling it on the same
        # five-minute diagnostic clock as Last seen prevents Recorder churn.
        return ("last_seen", None)

    @property
    def native_value(self):
        sensor = self.runtime.sensors.get(self.sensor_id)
        if sensor is None:
            return None
        values = [ep.rssi for ep in sensor.endpoints.values() if ep.rssi is not None]
        return max(values) if values else None

    @property
    def extra_state_attributes(self):
        sensor = self.runtime.sensors.get(self.sensor_id)
        if sensor is None:
            return {}
        return {
            "source_values": {
                transport: endpoint.rssi
                for transport, endpoint in sensor.endpoints.items()
                if endpoint.rssi is not None
            },
            "sampling": "5_minute_diagnostic_bucket",
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
        # Runtime already rate-limits Last seen dirty notifications to one minute.
        # Expose the same one-minute precision here so a continuously broadcasting
        # sensor visibly advances every minute without packet-rate Recorder churn.
        return seen.replace(second=0, microsecond=0)

    def _update(self):
        bucket = self.native_value
        if bucket == self._last_bucket:
            return
        self._last_bucket = bucket
        self.async_write_ha_state()


async def async_setup_sensor_entities(runtime, async_add_entities) -> None:
    """Materialize accepted physical-sensor entities without reloading the hub."""
    from homeassistant.helpers import entity_registry as er

    materialized: set[tuple[str, str, str]] = set()
    entity_registry = er.async_get(runtime.hass)

    def _claim(marker: tuple[str, str, str], unique_id: str) -> bool:
        """Return True when an entity must be (re)added to the platform.

        ``materialized`` is only an in-process optimization. A Home Assistant
        device/entity deletion can remove the Registry row while the sensor
        platform remains loaded, and the same physical ANT/BLE identity can then
        be rediscovered in the same process. Never let the stale in-memory marker
        suppress recreation of that entity. The registry lookup is O(1) by unique
        ID and happens only on structural refreshes, not on radio packets.
        """
        if marker in materialized:
            entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id is not None:
                return False
            materialized.discard(marker)
        materialized.add(marker)
        return True

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
            if _claim(key, f"fitness_{sensor_id}_active_transport"):
                entities.append(PhysicalActiveTransportSensor(runtime, sensor_id))

            key = (sensor_id, "diagnostic", "last_seen")
            if _claim(key, f"fitness_{sensor_id}_last_seen"):
                entities.append(PhysicalLastSeenSensor(runtime, sensor_id))

            key = (sensor_id, "diagnostic", "workout_owner")
            if _claim(key, f"fitness_{sensor_id}_workout_owner"):
                entities.append(PhysicalWorkoutOwnerSensor(runtime, sensor_id))

            if any(endpoint.rssi is not None for endpoint in sensor.endpoints.values()):
                key = (sensor_id, "diagnostic", "signal_strength")
                if _claim(key, f"fitness_{sensor_id}_signal_strength"):
                    entities.append(PhysicalSignalStrengthSensor(runtime, sensor_id))

            for metric in METRIC_META:
                if metric not in sensor.capabilities:
                    continue
                key = (sensor_id, "metric", metric)
                if not _claim(key, f"fitness_{sensor_id}_{metric}"):
                    continue
                entities.append(PhysicalMetricSensor(runtime, sensor_id, metric))

            for passive_key in sorted(runtime.sensor_passive_values.get(sensor_id, {})):
                key = (sensor_id, "passive", passive_key)
                if not _claim(key, f"fitness_{sensor_id}_passive_{passive_key}"):
                    continue
                entities.append(PhysicalPassiveSensor(runtime, sensor_id, passive_key))

            for detail_key in sorted(runtime.sensor_detail_values.get(sensor_id, {})):
                key = (sensor_id, "detail", detail_key)
                if not _claim(key, f"fitness_{sensor_id}_detail_{detail_key}"):
                    continue
                entities.append(PhysicalDetailSensor(runtime, sensor_id, detail_key))

        if entities:
            subentry = runtime.ensure_sensors_subentry()
            async_add_entities(
                entities,
                config_subentry_id=subentry.subentry_id if subentry is not None else None,
            )

    _collect()
    runtime.hub_entry.async_on_unload(runtime.add_structure_listener(_collect))
