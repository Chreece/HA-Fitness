"""Native ANT+ provider using the vendored HA-ANT+ runtime core."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from ..const import (
    METRIC_ALTITUDE,
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
)
from .runtime import LiveSensor
from .antplus_core.adapter import AntAdapterManager
from .antplus_core.receiver import AntPlusReceiver
from .antplus_core.remote import async_register_remote_listener

_LOGGER = logging.getLogger(__name__)

METRIC_MAP = {
    "heart_rate": METRIC_HEART_RATE,
    "hr": METRIC_HEART_RATE,
    "power": METRIC_POWER,
    "instantaneous_power": METRIC_POWER,
    "cycling_power": METRIC_POWER,
    "running_power": METRIC_POWER,
    "cadence": METRIC_CADENCE,
    "instantaneous_cadence": METRIC_CADENCE,
    "running_cadence": METRIC_CADENCE,
    "speed": METRIC_SPEED,
    "instantaneous_speed": METRIC_SPEED,
    "distance": METRIC_DISTANCE,
    "total_distance": METRIC_DISTANCE,
    "altitude": METRIC_ALTITUDE,
    "elevation": METRIC_ALTITUDE,
}


class _DiscoveryAdapterManager(AntAdapterManager):
    """ANT manager usable before the first Fitness ConfigEntry exists.

    HA-ANT+'s radio/gateway runtime is retained exactly. Only registry/config-entry
    persistence is deferred until a real Fitness profile entry can own the
    global adapter device.
    """

    def __init__(self, hass, receiver) -> None:
        self._pending_host = True
        super().__init__(
            hass,
            SimpleNamespace(data={}, entry_id="fitness_live_pending"),
            receiver,
        )

    def _known_adapters(self):
        return {}

    def _persist_record(self, record) -> None:
        del record

    def _merge_or_register_device(self, adapter) -> None:
        del adapter


class AntPlusFitnessProvider:
    """Expose HA-ANT+'s adapter/decoder/gateway runtime to Fitness."""

    transport = "antplus"

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self.hass = runtime.hass
        self.capture_active = False
        self.available = False
        self.last_error: str | None = None
        self.receiver: AntPlusReceiver | None = None
        self.adapter_manager: AntAdapterManager | None = None
        self._remote_unsub = None
        self._adapter_unsub = None
        self._device_unsub = None
        self._metric_unsub = None
        self._host_entry = None
        self._capture_requested = False

    async def async_setup(self) -> None:
        """Start ANT+ adapter/gateway discovery even without local hardware."""
        if self.receiver is not None:
            return

        try:
            self.receiver = AntPlusReceiver()
            self.receiver.diagnostics.start_watchdog()
            self._device_unsub = self.receiver.add_device_callback(
                self._schedule_publish_device
            )
            self._metric_unsub = self.receiver.add_metric_callback(
                lambda device, _key: self._schedule_publish_device(device)
            )
            await self._async_create_adapter_manager(
                next(iter(self.runtime.profile_entries.values()), None)
            )
            self.last_error = None
        except Exception as err:
            self.last_error = f"ANT+ initialization failed: {err}"
            _LOGGER.exception("Fitness ANT+ initialization failed")

    async def _async_create_adapter_manager(self, entry) -> None:
        if self.receiver is None:
            return

        if entry is None:
            manager: AntAdapterManager = _DiscoveryAdapterManager(
                self.hass, self.receiver
            )
            listener_entry = manager.entry
            self._host_entry = None
        else:
            manager = AntAdapterManager(self.hass, entry, self.receiver)
            listener_entry = entry
            self._host_entry = entry

        self.adapter_manager = manager
        self.receiver.adapter_manager = manager
        self._adapter_unsub = manager.add_callback(self._adapter_changed)
        await manager.async_start()
        self._remote_unsub = async_register_remote_listener(
            self.hass,
            listener_entry,
            self.receiver,
            manager,
        )
        self.available = self._has_available_receiver()

        for device in tuple(self.receiver.devices.values()):
            self._publish_device(device)

        if self._capture_requested:
            await self.async_start_capture()

    async def async_bind_profile(self, entry) -> None:
        """Attach global adapter devices/storage to the first real profile."""
        if self._host_entry is not None or self.receiver is None:
            return

        capture_requested = self._capture_requested
        if self._remote_unsub:
            self._remote_unsub()
            self._remote_unsub = None
        if self._adapter_unsub:
            self._adapter_unsub()
            self._adapter_unsub = None
        if self.adapter_manager is not None:
            self.adapter_manager.stop()
        self.adapter_manager = None

        self._capture_requested = capture_requested
        await self._async_create_adapter_manager(entry)

    def _schedule_publish_device(self, device) -> None:
        """Receiver callbacks may originate on OpenANT/remote worker threads."""
        self.hass.loop.call_soon_threadsafe(self._publish_device, device)

    def _publish_device(self, device) -> None:
        caps: set[str] = set()
        values: dict[str, float] = {}
        for key, metric in getattr(device, "metrics", {}).items():
            canonical = METRIC_MAP.get(str(key).lower())
            if canonical is None:
                continue
            caps.add(canonical)
            try:
                value = float(metric.value)
            except (TypeError, ValueError, AttributeError):
                continue
            unit = str(getattr(metric, "unit", "") or "").strip().lower()
            if canonical == METRIC_SPEED and unit in {"m/s", "mps"}:
                value *= 3.6
            elif canonical == METRIC_DISTANCE and unit in {"m", "meter", "meters"}:
                value /= 1000.0
            elif canonical == METRIC_DISTANCE and unit in {"mi", "mile", "miles"}:
                value *= 1.609344
            elif canonical == METRIC_ALTITUDE and unit in {"ft", "feet", "foot"}:
                value *= 0.3048
            values[canonical] = value

        if not caps:
            return

        device_id = int(getattr(device, "device_id"))
        manufacturer = getattr(device, "manufacturer_name", None)
        model = getattr(device, "model_no", None)
        name_parts = [
            x for x in (manufacturer, f"{model}" if model else None) if x
        ]
        name = " ".join(name_parts) if name_parts else f"ANT+ {device_id}"
        sensor_id = f"antplus:{device_id}"
        self.runtime.register_sensor(
            LiveSensor(
                sensor_id=sensor_id,
                transport=self.transport,
                name=name,
                capabilities=caps,
                address=str(device_id),
                last_seen=getattr(device, "last_seen", None)
                or datetime.now(timezone.utc),
                available=True,
                metadata={
                    "profiles": sorted(getattr(device, "profiles", set())),
                    "manufacturer": manufacturer,
                    "manufacturer_id": getattr(device, "manufacturer_id", None),
                    "model": f"{model}" if model is not None else None,
                    "model_no": model,
                    "serial_no": getattr(device, "serial_no", None),
                },
            )
        )
        if values:
            self.runtime.publish(sensor_id, values)

    def _has_available_receiver(self) -> bool:
        if self.adapter_manager is None:
            return False
        return any(
            record.available for record in self.adapter_manager.records.values()
        )

    def _adapter_changed(self, stable_key: str) -> None:
        self.available = self._has_available_receiver()
        if not self._capture_requested or self.adapter_manager is None:
            return
        record = self.adapter_manager.get(stable_key)
        if record is None or record.desired_capture:
            return
        self.hass.async_create_task(
            self.adapter_manager.async_set_capture(stable_key, True)
        )

    @property
    def receiver_count(self) -> int:
        if self.adapter_manager is None:
            return 0
        return sum(
            1 for record in self.adapter_manager.records.values() if record.available
        )

    @property
    def connected_sensor_count(self) -> int:
        return len(getattr(self.receiver, "devices", {}) or {})

    @property
    def receiver_details(self) -> list[dict[str, Any]]:
        if self.adapter_manager is None:
            return []
        result: list[dict[str, Any]] = []
        for key, record in self.adapter_manager.records.items():
            result.append(
                {
                    "id": key,
                    "available": record.available,
                    "connection": record.connection,
                    "sources": record.sources,
                    "capture": record.displayed_capture,
                    "error": record.capture_error,
                }
            )
        return result

    async def async_start_capture(self) -> None:
        """Capture on every present/future local adapter or remote gateway."""
        self._capture_requested = True
        self.capture_active = True
        self.last_error = None
        if self.receiver is not None:
            self.receiver.enable_capture()
        if self.adapter_manager is None:
            return
        for key in tuple(self.adapter_manager.records):
            try:
                await self.adapter_manager.async_set_capture(key, True)
            except Exception as err:
                self.last_error = str(err)
                _LOGGER.debug("ANT+ capture start failed for %s: %s", key, err)
        self.available = self._has_available_receiver()

    async def async_stop_capture(self) -> None:
        self._capture_requested = False
        if self.adapter_manager is not None:
            for key in tuple(self.adapter_manager.records):
                try:
                    await self.adapter_manager.async_set_capture(key, False)
                except Exception as err:
                    self.last_error = str(err)
                    _LOGGER.debug("ANT+ capture stop failed for %s: %s", key, err)
        if self.receiver is not None:
            self.receiver.disable_capture()
        self.capture_active = False
        self.available = self._has_available_receiver()

    async def async_connect_profile(
        self, profile_id: str, sensors: list[LiveSensor]
    ) -> None:
        del profile_id, sensors
        # ANT+ is broadcast; assignment/filtering happens in LiveRuntime.publish.

    async def async_disconnect_profile(
        self, profile_id: str, *, keep_heart_rate: bool = False
    ) -> None:
        del profile_id, keep_heart_rate

    async def async_shutdown(self) -> None:
        await self.async_stop_capture()
        for attr in (
            "_metric_unsub",
            "_device_unsub",
            "_adapter_unsub",
            "_remote_unsub",
        ):
            unsub = getattr(self, attr)
            if unsub:
                unsub()
                setattr(self, attr, None)
        if self.adapter_manager is not None:
            self.adapter_manager.stop()
        self.adapter_manager = None
        if self.receiver is not None:
            self.receiver.diagnostics.stop()
        self.receiver = None
        self._host_entry = None
        self.available = False
