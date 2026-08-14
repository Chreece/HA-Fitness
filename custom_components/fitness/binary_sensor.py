"""Fitness Local Sensors diagnostics."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from .live import get_live_runtime
from .live.runtime import HUB_ENTRY_TYPE


def _sensor_control_capabilities(sensor) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for endpoint in sensor.endpoints.values():
        mapping = endpoint.metadata.get("protocol_controls") or {}
        values = mapping.get(endpoint.transport, []) if isinstance(mapping, dict) else mapping
        for value in values or []:
            result.setdefault(str(value), set()).add(endpoint.transport)
    return result


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = get_live_runtime(hass)
    if entry.data.get("entry_type") != HUB_ENTRY_TYPE:
        return
    for transport in sorted(runtime.adapter_entity_transports):
        adapter_entities = [AdapterAvailable(runtime, transport), AdapterProblem(runtime, transport)]
        async_add_entities(
            adapter_entities,
            config_subentry_id=runtime.adapter_subentry_id(transport),
        )

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
            async_add_entities(added, config_subentry_id=runtime.adapter_subentry_id("antplus"))
    _add_ant_receiver_diagnostics()
    entry.async_on_unload(runtime.add_listener(_add_ant_receiver_diagnostics))

    materialized_sensor_ids: set[str] = set()
    materialized_controls: set[tuple[str, str]] = set()

    def _add_live_sensor_availability() -> None:
        accepted_ids = {
            sensor.sensor_id
            for sensor in runtime.sensors.values()
            if runtime.sensor_is_accepted(sensor.sensor_id)
        }
        materialized_sensor_ids.intersection_update(accepted_ids)
        new_ids = sorted(accepted_ids - materialized_sensor_ids)
        added = [LiveSensorAvailable(runtime, sensor_id) for sensor_id in new_ids]
        materialized_sensor_ids.update(new_ids)

        for sensor_id in sorted(accepted_ids):
            sensor = runtime.sensors.get(sensor_id)
            if sensor is None:
                continue
            for transport in sorted(sensor.endpoints):
                capture_token = (sensor_id, f"__capture_{transport}__")
                if capture_token not in materialized_controls:
                    materialized_controls.add(capture_token)
                    added.append(SensorTransportCaptureActive(runtime, sensor_id, transport))
            gatt_token = (sensor_id, "__gatt_connected__")
            if "bluetooth" in sensor.endpoints and gatt_token not in materialized_controls:
                materialized_controls.add(gatt_token)
                added.append(BluetoothGattConnected(runtime, sensor_id))
            for capability, transports in sorted(_sensor_control_capabilities(sensor).items()):
                token = (sensor_id, capability)
                if token in materialized_controls:
                    continue
                materialized_controls.add(token)
                added.append(PhysicalControlSupported(runtime, sensor_id, capability, transports))

        if not added:
            return
        subentry = runtime.ensure_sensors_subentry()
        async_add_entities(
            added,
            config_subentry_id=subentry.subentry_id if subentry is not None else None,
        )

    _add_live_sensor_availability()
    entry.async_on_unload(runtime.add_structure_listener(_add_live_sensor_availability))


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


class SensorTransportCaptureActive(BinarySensorEntity):
    """Per-physical-sensor logical capture gate state."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, sensor_id: str, transport: str):
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self.transport = str(transport)
        label = "ANT+" if self.transport == "antplus" else "Bluetooth"
        self._attr_name = f"{label} capture active"
        self._attr_icon = "mdi:record-rec"
        self._attr_unique_id = (
            f"fitness_{self.sensor_id}_{self.transport}_capture_active"
        )
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "capture", self.transport, self._update
            )
        )
        self.async_on_remove(self.runtime.add_listener(self._update))

    def _update(self):
        self.async_write_ha_state()

    @property
    def is_on(self):
        return bool(
            self.runtime.adapter_enabled(self.transport)
            and self.runtime.sensor_transport_capture_enabled(
                self.sensor_id, self.transport
            )
        )

    @property
    def available(self):
        sensor = self.runtime.sensors.get(
            self.runtime.resolve_sensor_id(self.sensor_id)
        )
        return bool(
            sensor is not None
            and self.transport in sensor.endpoints
            and self.runtime.adapter_enabled(self.transport)
        )


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

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "availability", None, self._update
            )
        )

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
            "known_transports": sorted(sensor.transports),
            "available_transports": sorted(
                transport
                for transport, endpoint in sensor.endpoints.items()
                if endpoint.available
            ),
        }


class BluetoothGattConnected(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Bluetooth GATT connected"
    _attr_icon = "mdi:bluetooth-connect"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, sensor_id: str):
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self._attr_unique_id = f"fitness_{self.sensor_id}_gatt_connected"
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.runtime.add_sensor_value_listener(
                self.sensor_id, "gatt_connection", None, self._update
            )
        )

    def _update(self):
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self.runtime.bluetooth_gatt_connected(self.sensor_id)

    @property
    def extra_state_attributes(self):
        provider = self.runtime.providers.get("bluetooth")
        users = getattr(provider, "sensor_users", None) if provider else None
        return {
            "owners": sorted(users(self.sensor_id)) if users is not None else [],
            "ant_data_fresh": bool(
                (sensor := self.runtime.sensors.get(self.sensor_id))
                and self.runtime.ant_data_fresh(sensor)
            ),
        }


class PhysicalControlSupported(BinarySensorEntity):
    """A positively detected protocol control capability.

    This is intentionally diagnostic until Fitness has a verified encoder/range
    contract for the capability. It creates no radio polling or state churn.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:gamepad-variant-outline"

    def __init__(self, runtime, sensor_id: str, capability: str, transports: set[str]):
        self.runtime = runtime
        self.sensor_id = runtime.resolve_sensor_id(sensor_id)
        self.capability = str(capability)
        self.transports = set(transports)
        self._attr_name = f"Supports {self.capability.replace('_', ' ')}"
        self._attr_unique_id = f"fitness_{self.sensor_id}_control_{self.capability}"
        self._attr_device_info = runtime.sensor_device_info(self.sensor_id)

    @property
    def is_on(self):
        return True

    @property
    def extra_state_attributes(self):
        evidence = {}
        sensor = self.runtime.sensors.get(self.sensor_id)
        if sensor is not None:
            for endpoint in sensor.endpoints.values():
                item = endpoint.metadata.get("capability_evidence") or {}
                if self.capability in item:
                    evidence[endpoint.transport] = item[self.capability]
        return {
            "capability": self.capability,
            "transports": sorted(self.transports),
            "evidence": evidence,
            "actionable": False,
            "reason": "A verified protocol encoder/range/acknowledgement contract is required before writes are enabled.",
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
