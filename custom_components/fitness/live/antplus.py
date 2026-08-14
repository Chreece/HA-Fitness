"""Native ANT+ provider using the vendored HA-ANT+ runtime core."""
from __future__ import annotations

import logging
import threading
import time
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
from .antplus_core.const import (
    DEVICE_TYPE_POWER,
    DEVICE_TYPE_FITNESS_EQUIPMENT,
    DEVICE_TYPE_HEART_RATE,
    DEVICE_TYPE_BIKE_SPEED_CADENCE,
    DEVICE_TYPE_BIKE_CADENCE,
    DEVICE_TYPE_BIKE_SPEED,
    DEVICE_TYPE_STRIDE_SPEED,
)
from .antplus_core.remote import async_register_remote_listener
from .antplus_core.capabilities import capability_snapshot

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


def _profile_capabilities(profiles: list[int]) -> set[str]:
    """Return standard potential live metrics from ANT profile identity alone."""
    caps: set[str] = set()
    profile_set = {int(profile) for profile in profiles}
    if DEVICE_TYPE_HEART_RATE in profile_set:
        caps.add(METRIC_HEART_RATE)
    if DEVICE_TYPE_POWER in profile_set:
        caps.add(METRIC_POWER)
    if DEVICE_TYPE_BIKE_CADENCE in profile_set:
        caps.add(METRIC_CADENCE)
    if DEVICE_TYPE_BIKE_SPEED in profile_set:
        caps.add(METRIC_SPEED)
    if DEVICE_TYPE_BIKE_SPEED_CADENCE in profile_set:
        caps.update({METRIC_SPEED, METRIC_CADENCE})
    if DEVICE_TYPE_STRIDE_SPEED in profile_set:
        caps.update({METRIC_SPEED, METRIC_DISTANCE, METRIC_CADENCE})
    if DEVICE_TYPE_FITNESS_EQUIPMENT in profile_set:
        caps.update(
            {METRIC_SPEED, METRIC_DISTANCE, METRIC_CADENCE, METRIC_POWER}
        )
    return caps


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
        self.available = False
        self.last_error: str | None = None
        self.receiver: AntPlusReceiver | None = None
        self.adapter_manager: AntAdapterManager | None = None
        self._remote_unsub = None
        self._adapter_unsub = None
        self._device_unsub = None
        self._metric_unsub = None
        self._packet_unsub = None
        self._event_metric_cache: dict[tuple[int, str], Any] = {}
        self._raw_event_cache: dict[tuple[str, str], tuple[bytes, float]] = {}
        self._extra_metric_cache: dict[tuple[int, str], Any] = {}
        self._extra_telemetry_last_publish: dict[int, float] = {}
        self._host_entry = None
        self._publish_lock = threading.Lock()
        self._pending_publish: dict[int, Any] = {}
        self._publish_scheduled: set[int] = set()
        self._pending_structural: set[int] = set()
        self._device_sensor_ids: dict[int, str] = {}
        self._device_accepted: dict[int, bool] = {}
        self._device_structure_signature: dict[int, tuple[object, ...]] = {}

    async def async_setup(self) -> None:
        """Start ANT+ adapter/gateway discovery even without local hardware."""
        if self.receiver is not None:
            return

        try:
            self.receiver = AntPlusReceiver()
            self.receiver.diagnostics.start_watchdog()
            self._device_unsub = self.receiver.add_device_callback(
                lambda device: self._schedule_publish_device(device, structural=True)
            )
            self._metric_unsub = self.receiver.add_metric_callback(
                lambda device, _key: self._schedule_publish_device(device, structural=False)
            )
            self._packet_unsub = self.receiver.add_packet_callback(self._schedule_protocol_event)
            await self._async_create_adapter_manager(self.runtime.hub_entry)
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
        self.runtime.set_adapter_presence("antplus", self.available)
        self.runtime.notify_changed()

        for device in tuple(self.receiver.devices.values()):
            self._publish_device(device)

        # Respect each adapter's persisted Capture preference. Provider/module
        # startup must never force Capture ON.
        await self._async_restore_receiver_states()

    async def async_bind_hub(self, entry) -> None:
        """Attach global adapter devices/storage to the Local Sensors entry."""
        if self._host_entry is not None or self.receiver is None:
            return

        if self._remote_unsub:
            self._remote_unsub()
            self._remote_unsub = None
        if self._adapter_unsub:
            self._adapter_unsub()
            self._adapter_unsub = None
        if self.adapter_manager is not None:
            await self.adapter_manager.async_stop()
        self.adapter_manager = None

        await self._async_create_adapter_manager(entry)

    def _schedule_publish_device(self, device, *, structural: bool) -> None:
        """Bridge ANT worker callbacks into one bounded per-device HA mailbox.

        The ANT worker may emit several metric callbacks for one packet and several
        profiles for one physical device. Only the newest device snapshot is kept.
        Accepted sensors are drained at most 2 times/s; known unaccepted sensors do
        not schedule metric work on Home Assistant's event loop at all.
        """
        try:
            device_id = int(getattr(device, "device_id"))
        except (TypeError, ValueError, AttributeError):
            return

        with self._publish_lock:
            if not structural:
                sensor_id = self._device_sensor_ids.get(device_id)
                if sensor_id is not None and not self._device_accepted.get(device_id, False):
                    return
            else:
                self._pending_structural.add(device_id)

            self._pending_publish[device_id] = device
            if device_id in self._publish_scheduled:
                return
            self._publish_scheduled.add(device_id)

        self.hass.loop.call_soon_threadsafe(self._flush_publish_device, device_id)

    def _flush_publish_device(self, device_id: int) -> None:
        """Drain one device mailbox and keep the gate closed for 500 ms."""
        with self._publish_lock:
            device = self._pending_publish.pop(device_id, None)
            structural = device_id in self._pending_structural
            self._pending_structural.discard(device_id)

        if device is not None:
            sensor_id = self._device_sensor_ids.get(device_id)
            if structural or sensor_id is None:
                self._publish_device(device)
            elif self._device_accepted.get(device_id, False):
                self._publish_metric_values(device, sensor_id)

        # Keep `_publish_scheduled` set during the cooldown. Worker callbacks only
        # replace `_pending_publish`; they do not create more thread-safe HA jobs.
        self.hass.loop.call_later(0.5, self._finish_publish_window, device_id)

    def _finish_publish_window(self, device_id: int) -> None:
        with self._publish_lock:
            if device_id in self._pending_publish:
                # New data arrived during the cooldown; keep the gate closed and
                # drain the newest snapshot now.
                pass
            else:
                self._publish_scheduled.discard(device_id)
                return
        self._flush_publish_device(device_id)

    def _schedule_protocol_event(self, device, device_type: int, transmission_type: int, payload: bytes, source: str) -> None:
        """Bridge discrete/raw ANT event-capable packets to HA Event entities.

        High-rate telemetry profiles never enter this path. For event-oriented
        profiles without a semantic decoder, raw payload changes are retained so
        Home Assistant still exposes the advertised event surface without guessing
        the vendor/profile meaning of individual bits.
        """
        # Most ANT packets are high-rate telemetry and can never generate raw HA
        # events. Reject them before resolving the capability model.
        device_type = int(device_type)
        if device_type not in (16, 115):
            return
        snapshot = capability_snapshot(device)
        event_keys: list[str] = []
        if device_type == 16:
            for key in ("generic_control_event", "controls_availability_event"):
                if key in snapshot.events:
                    event_keys.append(key)
        elif device_type == 115 and "dropper_event" in snapshot.events:
            event_keys.append("dropper_event")
        if not event_keys:
            return
        device_id = int(getattr(device, "device_id"))
        with self._publish_lock:
            sensor_id = self._device_sensor_ids.get(device_id)
            accepted = bool(sensor_id and self._device_accepted.get(device_id, False))
        if not accepted or sensor_id is None:
            return
        raw = bytes(payload)
        page = raw[0] & 0x7F if raw else None
        self.hass.loop.call_soon_threadsafe(
            self._emit_raw_protocol_events, sensor_id, tuple(event_keys),
            int(device_type), int(transmission_type), raw, str(source), page,
        )

    def _emit_raw_protocol_events(
        self, sensor_id: str, event_keys: tuple[str, ...], device_type: int,
        transmission_type: int, payload: bytes, source: str, page: int | None,
    ) -> None:
        now = time.monotonic()
        for event_key in event_keys:
            cache_key = (sensor_id, event_key)
            previous = self._raw_event_cache.get(cache_key)
            # Identical retransmissions are part of ANT reliability, not new HA
            # events. Allow the same payload again after 500 ms so a real repeated
            # button/control action is not suppressed forever.
            if previous is not None and previous[0] == payload and now - previous[1] < 0.5:
                continue
            self._raw_event_cache[cache_key] = (payload, now)
            self.runtime.emit_sensor_event(
                sensor_id, event_key, "event",
                {
                    "transport": "antplus", "device_type": device_type,
                    "transmission_type": transmission_type, "page": page,
                    "payload": payload.hex(), "source": source,
                },
            )

    def refresh_telemetry_gates(self) -> None:
        """Enable ANT metric decoding only for sensors needed by live sessions."""
        if self.receiver is None:
            return
        with self._publish_lock:
            mappings = tuple(self._device_sensor_ids.items())
        for device_id, sensor_id in mappings:
            canonical_id = self.runtime.resolve_sensor_id(sensor_id)
            if canonical_id != sensor_id:
                with self._publish_lock:
                    self._device_sensor_ids[device_id] = canonical_id
                sensor_id = canonical_id
            enabled = self.runtime.sensor_live_telemetry_needed(sensor_id)
            self.receiver.set_device_telemetry_enabled(device_id, enabled)

    def sensor_acceptance_changed(self, sensor_id: str, accepted: bool) -> None:
        """Update publish and decode gates after assignment/deletion."""
        affected: list[int] = []
        target_sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        with self._publish_lock:
            for device_id, mapped_sensor_id in tuple(self._device_sensor_ids.items()):
                canonical_id = self.runtime.resolve_sensor_id(mapped_sensor_id)
                if canonical_id == target_sensor_id:
                    self._device_sensor_ids[device_id] = canonical_id
                    self._device_accepted[device_id] = bool(accepted)
                    affected.append(device_id)
        if self.receiver is not None:
            for device_id in affected:
                mapped = self._device_sensor_ids.get(device_id)
                canonical = self.runtime.resolve_sensor_id(mapped) if mapped else None
                if mapped and canonical != mapped:
                    with self._publish_lock:
                        self._device_sensor_ids[device_id] = canonical
                    mapped = canonical
                self.receiver.set_device_accepted(device_id, bool(accepted and mapped))
                self.receiver.set_device_telemetry_enabled(
                    device_id,
                    bool(mapped and self.runtime.sensor_live_telemetry_needed(mapped)),
                )

    def forget_device(self, device_id: int) -> None:
        """Forget receiver-side ANT identity so the next RF packets rediscover it."""
        device_id = int(device_id)
        if self.receiver is not None:
            self.receiver.forget_device(device_id)
        with self._publish_lock:
            self._pending_publish.pop(device_id, None)
            self._publish_scheduled.discard(device_id)
            self._pending_structural.discard(device_id)
            self._device_sensor_ids.pop(device_id, None)
            self._device_accepted.pop(device_id, None)
            self._device_structure_signature.pop(device_id, None)

    def _metric_values(self, device) -> tuple[set[str], dict[str, float]]:
        """Return canonical Fitness capabilities and current values."""
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
        return caps, values

    def _publish_extra_metrics(self, device, sensor_id: str) -> None:
        """Publish decoded ANT+ information not consumed by the live core.

        Static/device information is retained immediately. Non-core telemetry is
        sampled at at most 1 Hz and disabled by default, so exposing the full
        decoder surface cannot recreate the radio-load problem. Event counters
        are still inspected on every bounded ANT mailbox flush.
        """
        details: dict[str, Any] = {}
        meta: dict[str, dict[str, Any]] = {}
        supported_events = set(capability_snapshot(device).events)
        device_id = int(getattr(device, "device_id"))
        now_mono = time.monotonic()
        allow_telemetry = (
            now_mono - self._extra_telemetry_last_publish.get(device_id, 0.0) >= 1.0
        )
        published_telemetry = False

        for key, metric in getattr(device, "metrics", {}).items():
            key = str(key)
            if METRIC_MAP.get(key.lower()) is not None:
                continue
            value = getattr(metric, "value", None)
            if value is None:
                continue

            event_key = None
            if key == "shift_event_count" and "shift_event" in supported_events:
                event_key = "shift_event"
            elif key.startswith("calibration_"):
                if "fe_calibration_event" in supported_events:
                    event_key = "fe_calibration_event"
                elif "power_calibration_event" in supported_events:
                    event_key = "power_calibration_event"
            elif key == "command_status" and "fe_command_status_event" in supported_events:
                event_key = "fe_command_status_event"

            if event_key:
                cache_key = (device_id, key)
                previous = self._event_metric_cache.get(cache_key)
                self._event_metric_cache[cache_key] = value
                if previous is not None and previous != value:
                    self.runtime.emit_sensor_event(
                        sensor_id, event_key, "event",
                        {"metric": key, "value": value, "previous": previous, "transport": "antplus"},
                    )

            availability_mode = str(getattr(metric, "availability_mode", "metric") or "metric")
            is_device_info = availability_mode == "device"
            if not is_device_info and not event_key and not allow_telemetry:
                continue

            value_cache_key = (device_id, key)
            if self._extra_metric_cache.get(value_cache_key) == value:
                continue
            self._extra_metric_cache[value_cache_key] = value
            details[key] = value
            if not is_device_info:
                published_telemetry = True

            category = getattr(metric, "entity_category", None)
            category_value = getattr(category, "value", category)
            meta[key] = {
                "name": getattr(metric, "name", None) or key.replace("_", " ").title(),
                "unit": getattr(metric, "unit", None),
                "device_class": getattr(metric, "device_class", None),
                "state_class": getattr(metric, "state_class", None),
                "icon": getattr(metric, "icon", None),
                "entity_category": category_value,
                # Every non-core ANT metric is opt-in. Core HR/power/cadence/etc.
                # remain normal entities; full protocol telemetry stays available
                # without generating Recorder/state churn by default.
                "enabled_default": False,
                "availability_mode": availability_mode,
            }

        if published_telemetry:
            self._extra_telemetry_last_publish[device_id] = now_mono

        # Battery is one canonical entity across ANT+ and BLE.
        if "battery_level" in details:
            self.runtime.publish_passive(
                sensor_id, {"battery": details.pop("battery_level")}, transport="antplus",
                metadata={"battery": {"name": "Battery", "unit": "%", "device_class": "battery", "state_class": "measurement", "icon": "mdi:battery"}},
            )
            meta.pop("battery_level", None)
        if details:
            self.runtime.publish_details(
                sensor_id, details, transport="antplus", metadata=meta, priority=65
            )

    def _publish_metric_values(self, device, sensor_id: str) -> None:
        """Fast metric-only path for an already registered accepted sensor."""
        _caps, values = self._metric_values(device)
        if values:
            self.runtime.publish(sensor_id, values, transport=self.transport)
        self._publish_extra_metrics(device, sensor_id)

    def _publish_device(self, device) -> None:
        metric_caps, values = self._metric_values(device)
        device_id = int(getattr(device, "device_id"))
        manufacturer = getattr(device, "manufacturer_name", None)
        model = getattr(device, "model_no", None)
        profiles = sorted(getattr(device, "profiles", set()))
        caps = _profile_capabilities(profiles) | metric_caps
        if not caps:
            return
        # Never promote the ANT numeric model number to the HA device name/model.
        # A semantic identity resolver/catalog will enrich this once enough
        # common-page or BLE Device Information data exists.
        name = "Fitness sensor"
        endpoint_id = f"antplus:{device_id}"
        snapshot = capability_snapshot(device)
        evidence = dict(snapshot.evidence)
        metadata = {
            "device_number": device_id,
            "profiles": profiles,
            "transmission_types": sorted(getattr(device, "transmission_types", set())),
            "manufacturer": manufacturer,
            "manufacturer_id": getattr(device, "manufacturer_id", None),
            "model_no": model,
            "serial_no": getattr(device, "serial_no", None),
            "hardware_rev": getattr(device, "hardware_rev", None),
            "software_ver": getattr(device, "software_ver", None),
            "protocol_controls": {"antplus": sorted(snapshot.controls)},
            "protocol_events": {"antplus": sorted(snapshot.events)},
            "capability_evidence": evidence,
        }
        structure_signature = (
            tuple(profiles),
            tuple(metadata["transmission_types"]),
            manufacturer,
            metadata["manufacturer_id"],
            model,
            metadata["serial_no"],
            metadata["hardware_rev"],
            metadata["software_ver"],
            tuple(sorted(snapshot.controls)),
            tuple(sorted(snapshot.events)),
        )
        previous_structure = self._device_structure_signature.get(device_id)
        mapped_sensor_id = self._device_sensor_ids.get(device_id)
        if previous_structure == structure_signature and mapped_sensor_id:
            canonical_id = self.runtime.resolve_sensor_id(mapped_sensor_id)
            if canonical_id != mapped_sensor_id:
                mapped_sensor_id = canonical_id
                with self._publish_lock:
                    self._device_sensor_ids[device_id] = canonical_id
            accepted = self.runtime.sensor_is_accepted(mapped_sensor_id)
            with self._publish_lock:
                self._device_accepted[device_id] = accepted
            if self.receiver is not None:
                self.receiver.set_device_accepted(device_id, accepted)
                self.receiver.set_device_telemetry_enabled(
                    device_id,
                    self.runtime.sensor_live_telemetry_needed(mapped_sensor_id),
                )
            return

        sensor = self.runtime.register_transport_sensor(
            transport=self.transport, endpoint_id=endpoint_id, name=name,
            capabilities=caps, address=str(device_id),
            last_seen=getattr(device, "last_seen", None) or datetime.now(timezone.utc),
            available=True, metadata=metadata,
        )
        accepted = self.runtime.sensor_is_accepted(sensor.sensor_id)
        self._device_structure_signature[device_id] = structure_signature
        with self._publish_lock:
            self._device_sensor_ids[device_id] = sensor.sensor_id
            self._device_accepted[device_id] = accepted
        if self.receiver is not None:
            self.receiver.set_device_accepted(device_id, accepted)
            self.receiver.set_device_telemetry_enabled(
                device_id,
                self.runtime.sensor_live_telemetry_needed(sensor.sensor_id),
            )

        # Keep raw protocol identity/capabilities as disabled diagnostics.
        diagnostic_values = {
            "ant_device_number": device_id,
            "ant_profiles": ", ".join(str(x) for x in profiles),
            "ant_transmission_types": ", ".join(str(x) for x in sorted(getattr(device, "transmission_types", set()))),
            "ant_manufacturer_id": getattr(device, "manufacturer_id", None),
            "ant_model_number": model,
            "ant_supported_controls": ", ".join(sorted(snapshot.controls)),
            "ant_supported_events": ", ".join(sorted(snapshot.events)),
        }
        diagnostic_values = {k: v for k, v in diagnostic_values.items() if v not in (None, "")}
        diagnostic_meta = {key: {"name": key.replace("_", " ").title(), "entity_category": "diagnostic", "enabled_default": False, "icon": "mdi:information-outline"} for key in diagnostic_values}
        if diagnostic_values:
            self.runtime.publish_details(sensor.sensor_id, diagnostic_values, transport="antplus", metadata=diagnostic_meta, priority=20)
        # A generic ANT profile remains provisional until runtime has stable
        # common-page/catalog identity. Device Registry work is owned by the
        # post-Add/control-plane path; never perform registry lookup here.
        if accepted:
            if values:
                self.runtime.publish(sensor.sensor_id, values, transport=self.transport)
            self._publish_extra_metrics(device, sensor.sensor_id)

    def _has_available_receiver(self) -> bool:
        if self.adapter_manager is None:
            return False
        return any(
            record.available for record in self.adapter_manager.records.values()
        )

    def _adapter_changed(self, stable_key: str) -> None:
        del stable_key
        self.available = self._has_available_receiver()
        self.runtime.set_adapter_presence("antplus", self.available)
        self.runtime.notify_changed()

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
                }
            )
        return result

    async def _async_restore_receiver_states(self) -> None:
        """Apply persisted Capture preferences without changing them."""
        if self.adapter_manager is None:
            return
        for key, record in tuple(self.adapter_manager.records.items()):
            try:
                # Startup only applies the preference already loaded; it does not
                # mutate the user's Capture setting.
                self.adapter_manager._sync_local_capture(key)
                for gateway_id in sorted(record.remote_gateways or {}):
                    self.adapter_manager._send_remote_capture(
                        key, gateway_id, bool(record.desired_capture)
                    )
            except Exception as err:
                self.last_error = str(err)
                _LOGGER.debug(
                    "ANT+ receiver state restore failed for %s: %s", key, err
                )

    async def _async_enable_receivers(self) -> None:
        """Enable ANT receiver paths while the adapter module is active."""
        self.last_error = None
        if self.receiver is not None:
            # The vendored ANT receiver performs synchronous USB control work.
            # Never execute that on Home Assistant's event loop.
            await self.hass.async_add_executor_job(self.receiver.enable_capture)
        if self.adapter_manager is not None:
            for key in tuple(self.adapter_manager.records):
                try:
                    await self.adapter_manager.async_set_capture(key, True)
                except Exception as err:
                    self.last_error = str(err)
                    _LOGGER.debug("ANT+ receiver enable failed for %s: %s", key, err)
        self.available = self._has_available_receiver()

    async def _async_disable_receivers(self) -> None:
        """Disable ANT receiver paths only when the adapter module unloads."""
        if self.adapter_manager is not None:
            for key in tuple(self.adapter_manager.records):
                try:
                    await self.adapter_manager.async_set_capture(key, False)
                except Exception as err:
                    self.last_error = str(err)
                    _LOGGER.debug("ANT+ receiver disable failed for %s: %s", key, err)
        if self.receiver is not None:
            # Receiver shutdown may issue synchronous USB control transfers too.
            await self.hass.async_add_executor_job(self.receiver.disable_capture)
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
        await self._async_disable_receivers()
        for attr in (
            "_metric_unsub",
            "_packet_unsub",
            "_device_unsub",
            "_adapter_unsub",
            "_remote_unsub",
        ):
            unsub = getattr(self, attr)
            if unsub:
                unsub()
                setattr(self, attr, None)
        if self.adapter_manager is not None:
            await self.adapter_manager.async_stop()
        self.adapter_manager = None
        if self.receiver is not None:
            await self.hass.async_add_executor_job(self.receiver.diagnostics.stop)
        self.receiver = None
        self._host_entry = None
        self.available = False
        # Keep lightweight presence detector authoritative after unloading.
        self.hass.async_create_task(self.runtime.async_refresh_adapter_presence())
        self.runtime.notify_changed()
