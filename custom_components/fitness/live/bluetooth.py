"""Bluetooth SIG fitness-sensor transport for Fitness."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher

from ..const import (
    METRIC_CADENCE,
    METRIC_DISTANCE,
    METRIC_HEART_RATE,
    METRIC_POWER,
    METRIC_SPEED,
)
from .runtime import LiveSensor

_LOGGER = logging.getLogger(__name__)

BASE = "0000{}-0000-1000-8000-00805f9b34fb"
SERVICE_HR = BASE.format("180d")
SERVICE_CYCLING_POWER = BASE.format("1818")
SERVICE_CSC = BASE.format("1816")
SERVICE_RSC = BASE.format("1814")
SERVICE_FTMS = BASE.format("1826")

CHAR_HR = BASE.format("2a37")
CHAR_CYCLING_POWER = BASE.format("2a63")
CHAR_CSC = BASE.format("2a5b")
CHAR_RSC = BASE.format("2a53")
CHAR_FTMS_TREADMILL = BASE.format("2acd")
CHAR_FTMS_CROSS_TRAINER = BASE.format("2ace")
CHAR_FTMS_ROWER = BASE.format("2ad1")
CHAR_FTMS_INDOOR_BIKE = BASE.format("2ad2")

SERVICE_CAPABILITIES = {
    SERVICE_HR: {METRIC_HEART_RATE},
    SERVICE_CYCLING_POWER: {METRIC_POWER, METRIC_CADENCE},
    SERVICE_CSC: {METRIC_CADENCE},
    SERVICE_RSC: {METRIC_SPEED, METRIC_CADENCE, METRIC_DISTANCE},
    SERVICE_FTMS: {
        METRIC_SPEED,
        METRIC_CADENCE,
        METRIC_POWER,
        METRIC_DISTANCE,
        METRIC_HEART_RATE,
    },
}

BATTERY_SERVICE = BASE.format("180f")
STRYD_MANUFACTURER_ID = 43690


def _passive_advertisement_values(info) -> tuple[dict[str, float], dict[str, dict]]:
    """Decode connectionless values with known semantics.

    BLE manufacturer data has no universal schema, so vendor-specific fields are
    exposed only when Fitness has a verified decoder. Standard Battery Service
    service data and Stryd's passive battery frame are currently supported.
    """
    values: dict[str, float] = {}
    metadata: dict[str, dict] = {}

    service_data = getattr(info, "service_data", {}) or {}
    for key, payload in service_data.items():
        if str(key).lower() == BATTERY_SERVICE and payload:
            battery = int(bytes(payload)[0])
            if 0 <= battery <= 100:
                values["battery"] = float(battery)
                metadata["battery"] = {
                    "name": "Battery", "unit": "%", "device_class": "battery",
                    "state_class": "measurement", "icon": "mdi:battery",
                    "passive": True,
                }

    manufacturer_data = getattr(info, "manufacturer_data", {}) or {}
    stryd = manufacturer_data.get(STRYD_MANUFACTURER_ID)
    if stryd and len(stryd) >= 2:
        # Home Assistant strips the two-byte company identifier. This is the
        # passive Stryd battery byte already verified by HA-Stryd-BLE.
        battery = int(bytes(stryd)[1])
        if 0 <= battery <= 100:
            values["battery"] = float(battery)
            metadata["battery"] = {
                "name": "Battery", "unit": "%", "device_class": "battery",
                "state_class": "measurement", "icon": "mdi:battery",
                "passive": True, "manufacturer_id": STRYD_MANUFACTURER_ID,
            }
    return values, metadata


@dataclass
class _RevolutionState:
    crank_revs: int | None = None
    crank_time: int | None = None


class BluetoothFitnessProvider:
    """Discover via HA Bluetooth and actively connect through HA/proxy routes."""

    transport = "bluetooth"

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self.hass = runtime.hass
        self.capture_active = False
        self.available = False
        self.last_error: str | None = None
        self._unsub = None
        self._clients: dict[str, BleakClient] = {}
        self._profile_clients: dict[str, set[str]] = {}
        self._sensor_users: dict[str, set[str]] = {}
        self._revolution_state: dict[str, _RevolutionState] = {}

    async def async_setup(self) -> None:
        """Register one HA Bluetooth discovery callback; no private scanner."""
        from homeassistant.setup import async_setup_component

        if not await async_setup_component(self.hass, "bluetooth", {}):
            self.available = False
            self.last_error = "Home Assistant Bluetooth could not be initialized"
            return

        self._unsub = bluetooth.async_register_callback(
            self.hass,
            self._async_discovered,
            BluetoothCallbackMatcher(connectable=False),
            BluetoothScanningMode.PASSIVE,
        )
        self._refresh_available()
        self.runtime.set_adapter_presence("bluetooth", self.available)

        # Include already-cached advertisements, including ESPHome proxy paths.
        for info in bluetooth.async_discovered_service_info(self.hass, False):
            self._async_discovered(info, None)

    def _refresh_available(self) -> None:
        scanner_count = getattr(bluetooth, "async_scanner_count", None)
        if scanner_count is None:
            self.available = True
            return
        try:
            self.available = bool(scanner_count(self.hass, connectable=True))
        except TypeError:
            try:
                self.available = bool(scanner_count(self.hass))
            except Exception:
                self.available = True
        except Exception:
            self.available = False

    def _async_discovered(self, info, _change) -> None:
        uuids = {str(x).lower() for x in (info.service_uuids or [])}
        capabilities: set[str] = set()
        for service, caps in SERVICE_CAPABILITIES.items():
            if service in uuids:
                capabilities.update(caps)
        if not capabilities:
            return

        endpoint_id = f"bluetooth:{info.address.upper()}"
        sensor = self.runtime.register_transport_sensor(
            transport=self.transport,
            endpoint_id=endpoint_id,
            name=info.name or info.address,
            capabilities=capabilities,
            address=info.address,
            source=getattr(info, "source", None),
            last_seen=datetime.now(timezone.utc),
            rssi=getattr(info, "rssi", None),
            available=True,
            metadata={
                "advertised_name": info.name,
                "service_uuids": sorted(uuids),
            },
        )
        passive, passive_meta = _passive_advertisement_values(info)
        if passive:
            self.runtime.publish_passive(
                sensor.sensor_id, passive, transport=self.transport, metadata=passive_meta
            )
        self._refresh_available()
        self.runtime.set_adapter_presence("bluetooth", self.available)

    async def async_start_capture(self) -> None:
        # BLE advertisements remain passive. Active GATT is opened only for
        # assigned sensors by async_connect_profile().
        self.capture_active = True
        self.last_error = None
        self._refresh_available()

    async def async_stop_capture(self) -> None:
        for profile_id in tuple(self._profile_clients):
            await self.async_disconnect_profile(profile_id, keep_heart_rate=False)
        self.capture_active = False

    async def async_connect_profile(
        self, profile_id: str, sensors: list[LiveSensor]
    ) -> None:
        if not self.capture_active:
            return

        for sensor in sensors:
            endpoint = sensor.endpoints.get(self.transport)
            if endpoint is None or not endpoint.address:
                continue

            existing = self._clients.get(sensor.sensor_id)
            if existing is not None and existing.is_connected:
                self._profile_clients.setdefault(profile_id, set()).add(sensor.sensor_id)
                self._sensor_users.setdefault(sensor.sensor_id, set()).add(profile_id)
                continue

            # HA resolves the best connectable path. The BLEDevice can therefore
            # point at local Bluetooth or a compatible remote Bluetooth proxy.
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, endpoint.address, connectable=True
            )
            if ble_device is None:
                continue

            try:
                client = await establish_connection(
                    BleakClient,
                    device=ble_device,
                    name=sensor.name or endpoint.address,
                    max_attempts=4,
                )
                self._clients[sensor.sensor_id] = client
                self._profile_clients.setdefault(profile_id, set()).add(sensor.sensor_id)
                self._sensor_users.setdefault(sensor.sensor_id, set()).add(profile_id)
                sensor = await self._async_enrich_identity(sensor, endpoint, client)
                await self._subscribe(sensor, client)
            except Exception as err:
                self.last_error = f"{sensor.name}: {err}"
                _LOGGER.debug(
                    "Bluetooth fitness connect failed for %s: %s",
                    sensor.sensor_id,
                    err,
                )

    async def _async_enrich_identity(self, sensor: LiveSensor, endpoint, client: BleakClient) -> LiveSensor:
        """Read standard Device Information when available and refine identity."""
        metadata = dict(endpoint.metadata)
        for uuid, key in (
            (BASE.format("2a29"), "manufacturer"),
            (BASE.format("2a24"), "model"),
            (BASE.format("2a25"), "serial_number"),
        ):
            try:
                raw = await client.read_gatt_char(uuid)
                value = bytes(raw).decode("utf-8", errors="ignore").strip("\x00 ")
            except Exception:
                continue
            if value:
                metadata[key] = value
        refined_name = metadata.get("model") or sensor.name
        merged = self.runtime.register_transport_sensor(
            transport=self.transport,
            endpoint_id=endpoint.endpoint_id,
            name=str(refined_name),
            capabilities=set(endpoint.capabilities),
            address=endpoint.address,
            source=endpoint.source,
            last_seen=datetime.now(timezone.utc),
            rssi=endpoint.rssi,
            available=True,
            metadata=metadata,
        )
        # Strong identity information may merge this endpoint into an already
        # known ANT+ physical device. Continue using the canonical object.
        if merged.sensor_id != sensor.sensor_id:
            old_id = sensor.sensor_id
            new_id = merged.sensor_id
            self._clients[new_id] = self._clients.pop(old_id, client)
            for profile_id, ids in self._profile_clients.items():
                if old_id in ids:
                    ids.discard(old_id)
                    ids.add(new_id)
            users = self._sensor_users.pop(old_id, set())
            if users:
                self._sensor_users.setdefault(new_id, set()).update(users)
            state = self._revolution_state.pop(old_id, None)
            if state is not None:
                self._revolution_state[new_id] = state
        return merged

    async def _subscribe(self, sensor: LiveSensor, client: BleakClient) -> None:
        def notify(parser):
            def _callback(_char, data):
                try:
                    values = parser(bytes(data))
                except Exception:
                    _LOGGER.debug(
                        "Bluetooth fitness parser failed for %s",
                        sensor.sensor_id,
                        exc_info=True,
                    )
                    return
                if values:
                    self.runtime.publish(sensor.sensor_id, values, transport=self.transport)
            return _callback

        async def start(uuid: str, parser) -> None:
            try:
                await client.start_notify(uuid, notify(parser))
            except Exception:
                # A service may advertise a family while omitting a particular
                # optional characteristic. That is normal, not an adapter fault.
                return

        state = self._revolution_state.setdefault(sensor.sensor_id, _RevolutionState())
        await start(CHAR_HR, _parse_hr)
        await start(
            CHAR_CYCLING_POWER,
            lambda data: _parse_cycling_power(data, state),
        )
        await start(CHAR_RSC, _parse_rsc)
        await start(CHAR_CSC, lambda data: _parse_csc(data, state))
        await start(CHAR_FTMS_INDOOR_BIKE, _parse_ftms_indoor_bike)
        # These parsers intentionally consume only the common instantaneous
        # fields whose byte layout is unambiguous across the FTMS profile.
        await start(CHAR_FTMS_TREADMILL, _parse_ftms_treadmill)

    async def async_disconnect_profile(
        self, profile_id: str, *, keep_heart_rate: bool = False
    ) -> None:
        ids = self._profile_clients.get(profile_id, set()).copy()
        for sensor_id in ids:
            sensor = self.runtime.sensors.get(sensor_id)
            if keep_heart_rate and sensor and METRIC_HEART_RATE in sensor.capabilities:
                continue

            self._profile_clients.get(profile_id, set()).discard(sensor_id)
            users = self._sensor_users.setdefault(sensor_id, set())
            users.discard(profile_id)
            if users:
                continue

            self._sensor_users.pop(sensor_id, None)
            self._revolution_state.pop(sensor_id, None)
            client = self._clients.pop(sensor_id, None)
            if client is not None:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        if not self._profile_clients.get(profile_id):
            self._profile_clients.pop(profile_id, None)

    @property
    def receiver_count(self) -> int:
        scanner_count = getattr(bluetooth, "async_scanner_count", None)
        if scanner_count is None:
            return 1 if self.available else 0
        try:
            return int(scanner_count(self.hass, connectable=True))
        except TypeError:
            try:
                return int(scanner_count(self.hass))
            except Exception:
                return 0
        except Exception:
            return 0

    @property
    def connected_sensor_count(self) -> int:
        return sum(1 for client in self._clients.values() if client.is_connected)

    @property
    def receiver_details(self) -> list[dict]:
        return [
            {
                "type": "Home Assistant Bluetooth",
                "scanner_count": self.receiver_count,
                "proxy_capable": True,
            }
        ]

    async def async_shutdown(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        await self.async_stop_capture()
        self.available = False
        self.hass.async_create_task(self.runtime.async_refresh_adapter_presence())
        self.runtime.notify_changed()


def _parse_hr(data: bytes) -> dict[str, float]:
    if len(data) < 2:
        return {}
    flags = data[0]
    if flags & 0x01 and len(data) >= 3:
        hr = int.from_bytes(data[1:3], "little")
    else:
        hr = data[1]
    return {METRIC_HEART_RATE: float(hr)} if 20 <= hr <= 260 else {}


def _counter_delta(current: int, previous: int, modulus: int) -> int:
    return (current - previous) % modulus


def _parse_cycling_power(
    data: bytes, state: _RevolutionState | None = None
) -> dict[str, float]:
    if len(data) < 4:
        return {}
    flags = int.from_bytes(data[0:2], "little")
    power = int.from_bytes(data[2:4], "little", signed=True)
    result: dict[str, float] = {}
    if -2000 <= power <= 5000:
        result[METRIC_POWER] = float(power)

    # Cycling Power Measurement optional fields are consumed in flag order.
    idx = 4
    if flags & (1 << 0):  # pedal power balance
        idx += 1
    if flags & (1 << 2):  # accumulated torque
        idx += 2
    if flags & (1 << 4):  # wheel revolution data
        idx += 6
    if flags & (1 << 5) and len(data) >= idx + 4 and state is not None:
        crank_revs = int.from_bytes(data[idx:idx + 2], "little")
        crank_time = int.from_bytes(data[idx + 2:idx + 4], "little")
        if state.crank_revs is not None and state.crank_time is not None:
            rev_delta = _counter_delta(crank_revs, state.crank_revs, 1 << 16)
            time_delta = _counter_delta(crank_time, state.crank_time, 1 << 16)
            if rev_delta > 0 and time_delta > 0:
                cadence = rev_delta * 60.0 * 1024.0 / time_delta
                if 0.0 <= cadence <= 300.0:
                    result[METRIC_CADENCE] = round(cadence, 2)
        state.crank_revs = crank_revs
        state.crank_time = crank_time
    return result


def _parse_rsc(data: bytes) -> dict[str, float]:
    if len(data) < 4:
        return {}
    speed_ms = int.from_bytes(data[1:3], "little") / 256.0
    cadence = data[3]
    result: dict[str, float] = {
        METRIC_SPEED: speed_ms * 3.6,
        METRIC_CADENCE: float(cadence),
    }
    idx = 4
    if data[0] & 0x01:  # stride length
        idx += 2
    if data[0] & 0x02 and len(data) >= idx + 4:  # total distance, 1/10 m
        result[METRIC_DISTANCE] = int.from_bytes(data[idx:idx + 4], "little") / 10000.0
    return result


def _parse_csc(
    data: bytes, state: _RevolutionState | None = None
) -> dict[str, float]:
    """Decode standard CSC crank cadence; wheel speed needs circumference."""
    if len(data) < 1 or state is None:
        return {}
    flags = data[0]
    idx = 1
    if flags & 0x01:  # cumulative wheel revs + last wheel event time
        if len(data) < idx + 6:
            return {}
        idx += 6
    if not (flags & 0x02) or len(data) < idx + 4:
        return {}

    crank_revs = int.from_bytes(data[idx:idx + 2], "little")
    crank_time = int.from_bytes(data[idx + 2:idx + 4], "little")
    result: dict[str, float] = {}
    if state.crank_revs is not None and state.crank_time is not None:
        rev_delta = _counter_delta(crank_revs, state.crank_revs, 1 << 16)
        time_delta = _counter_delta(crank_time, state.crank_time, 1 << 16)
        if rev_delta > 0 and time_delta > 0:
            cadence = rev_delta * 60.0 * 1024.0 / time_delta
            if 0.0 <= cadence <= 300.0:
                result[METRIC_CADENCE] = round(cadence, 2)
    state.crank_revs = crank_revs
    state.crank_time = crank_time
    return result


def _parse_ftms_indoor_bike(data: bytes) -> dict[str, float]:
    """Decode the common FTMS Indoor Bike Data fields in flag order."""
    if len(data) < 2:
        return {}
    flags = int.from_bytes(data[0:2], "little")
    idx = 2
    result: dict[str, float] = {}

    # Bit 0 is "More Data": instantaneous speed is present when it is clear.
    if not (flags & (1 << 0)):
        if len(data) < idx + 2:
            return result
        result[METRIC_SPEED] = int.from_bytes(data[idx:idx + 2], "little") / 100.0
        idx += 2
    if flags & (1 << 1):  # average speed
        idx += 2
    if flags & (1 << 2) and len(data) >= idx + 2:
        result[METRIC_CADENCE] = int.from_bytes(data[idx:idx + 2], "little") / 2.0
        idx += 2
    if flags & (1 << 3):  # average cadence
        idx += 2
    if flags & (1 << 4) and len(data) >= idx + 3:
        result[METRIC_DISTANCE] = int.from_bytes(data[idx:idx + 3], "little") / 1000.0
        idx += 3
    if flags & (1 << 5):  # resistance level
        idx += 2
    if flags & (1 << 6) and len(data) >= idx + 2:
        result[METRIC_POWER] = float(int.from_bytes(data[idx:idx + 2], "little", signed=True))
        idx += 2
    if flags & (1 << 7):  # average power
        idx += 2
    if flags & (1 << 8):  # expended energy block
        idx += 5
    if flags & (1 << 9) and len(data) > idx:
        hr = data[idx]
        if 20 <= hr <= 260:
            result[METRIC_HEART_RATE] = float(hr)
    return result


def _parse_ftms_treadmill(data: bytes) -> dict[str, float]:
    """Decode safe common FTMS Treadmill Data fields."""
    if len(data) < 4:
        return {}
    flags = int.from_bytes(data[0:2], "little")
    idx = 2
    result: dict[str, float] = {}
    if not (flags & 0x01) and len(data) >= idx + 2:
        result[METRIC_SPEED] = int.from_bytes(data[idx:idx + 2], "little") / 100.0
        idx += 2
    # Treadmill's remaining optional fields differ from Indoor Bike. We avoid
    # guessing their offsets here; speed is still a useful canonical live input.
    return result
