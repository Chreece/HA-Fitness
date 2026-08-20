"""Authenticated remote Fitness sensor gateway and browser-local Cast helpers.

The wire protocol is deliberately transport-neutral so browser Web Bluetooth/WebUSB
and future Android/iOS/Windows sender applications can publish the same raw BLE and
ANT+ frames without duplicating Fitness's decoding and profile-assignment logic.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from itertools import islice
import logging
import time
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .access_control import get_fitness_access_controller
from .const import CONF_LIVE_SENSOR_IDS, DOMAIN
from .live.antplus_core.adapter import AntUsbAdapter
from .live.antplus_core.const import (
    REMOTE_GATEWAY_HELLO_EVENT,
    REMOTE_GATEWAY_STATUS_EVENT,
    REMOTE_PACKET_EVENT,
)
from .live.bluetooth import (
    CHAR_BATTERY_LEVEL,
    CHAR_CSC,
    CHAR_CYCLING_POWER,
    CHAR_FTMS_INDOOR_BIKE,
    CHAR_FTMS_TREADMILL,
    CHAR_HR,
    CHAR_RSC,
    SERVICE_CAPABILITIES,
    _RevolutionState,
    _battery_metadata,
    _parse_battery,
    _parse_csc,
    _parse_cycling_power,
    _parse_ftms_indoor_bike,
    _parse_ftms_treadmill,
    _parse_hr,
    _parse_rsc,
)
from .device_adapters.registry import ARCHIVE_ADAPTERS
from .device_adapters.cycplus_m1 import (
    CYCPLUS_M1_SERVICE_UUID,
    cycplus_m1_name_identity,
    cycplus_m1_serial_identity,
)
from .live.runtime import get_live_runtime
from .resource_safety import bounded_payload, bounded_websocket_payload

_LOGGER = logging.getLogger(__name__)

REMOTE_GATEWAY_PROTOCOL = 1
REMOTE_GATEWAY_KEY = "_remote_gateway_runtime"
# Browser-local Cast must use the authenticated browser session credentials.
# This mirrors Home Assistant frontend's Web Sender flow instead of the
# server-side Cast integration's separate system user.
LEGACY_LOCAL_CAST_USER_NAMES = {"Fitness TV Cast", "Home Assistant Cast"}
LOCAL_CAST_APP_ID = "A078F6B0"
LOCAL_CAST_NAMESPACE = "urn:x-cast:com.nabucasa.hast"
REMOTE_BLE_DEVICE_LIMIT = 256
REMOTE_BLE_STALE_SECONDS = 300.0
REMOTE_ASSIGNMENT_GATEWAY_LIMIT = 16
REMOTE_ASSIGNMENT_DEVICE_LIMIT = 512
REMOTE_BLE_IDENTITY_FIELDS = {
    "manufacturer",
    "model",
    "serial_number",
    "firmware_version",
    "hw_version",
    "sw_version",
}

# Characteristic -> stable capability set / decoder name. The backend decodes raw
# standard Bluetooth SIG measurements so browser and native senders stay tiny.
BLE_CHARACTERISTICS: dict[str, tuple[set[str], str]] = {
    CHAR_BATTERY_LEVEL: (set(), "battery"),
    CHAR_HR: ({"heart_rate"}, "hr"),
    CHAR_CYCLING_POWER: ({"power", "cadence"}, "cycling_power"),
    CHAR_CSC: ({"cadence"}, "csc"),
    CHAR_RSC: ({"speed", "cadence", "distance"}, "rsc"),
    CHAR_FTMS_INDOOR_BIKE: ({"speed", "cadence", "distance", "power", "heart_rate"}, "ftms_indoor_bike"),
    CHAR_FTMS_TREADMILL: ({"speed"}, "ftms_treadmill"),
}


def _clean_gateway_id(value: Any) -> str:
    value = str(value or "").strip()
    if not value or len(value) > 128:
        raise ValueError("invalid gateway_id")
    return value


def _clean_device_id(value: Any) -> str:
    value = str(value or "").strip()
    if not value or len(value) > 256:
        raise ValueError("invalid device_id")
    return value


def _normalize_uuid(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if len(raw) == 4:
        return f"0000{raw}-0000-1000-8000-00805f9b34fb"
    return raw


def _byte_payload(value: Any, *, exact: int | None = None, maximum: int = 512) -> bytes:
    if isinstance(value, str):
        cleaned = value.replace(" ", "").replace(":", "").replace("-", "")
        if len(cleaned) % 2:
            raise ValueError("hex payload must contain complete bytes")
        data = bytes.fromhex(cleaned)
    elif isinstance(value, (list, tuple)):
        values = [int(item) for item in value]
        if any(item < 0 or item > 255 for item in values):
            raise ValueError("payload byte outside 0..255")
        data = bytes(values)
    else:
        raise ValueError("payload must be hex or a byte list")
    if exact is not None and len(data) != exact:
        raise ValueError(f"payload must contain exactly {exact} bytes")
    if len(data) > maximum:
        raise ValueError("payload too large")
    return data


def _profile_entry(hass: HomeAssistant, profile_entry_id: str):
    entry = hass.config_entries.async_get_entry(str(profile_entry_id))
    if entry is None or entry.domain != DOMAIN or entry.data.get("entry_type") in {"live_hub", "devices_hub"}:
        return None
    return entry


async def _require_profile_access(hass: HomeAssistant, connection, profile_entry_id: str) -> None:
    """Require active control rights for every remote-gateway data path."""
    await get_fitness_access_controller(hass).async_require_profile_control(
        connection, str(profile_entry_id)
    )


async def _async_assign_sensor_to_profile(hass: HomeAssistant, runtime, entry, sensor_id: str) -> None:
    """Accept a newly paired remote sensor and bind it to the active profile."""
    sensor_id = runtime.resolve_sensor_id(sensor_id)
    ids = list(({**entry.data, **entry.options}.get(CONF_LIVE_SENSOR_IDS) or []))
    if not any(runtime.resolve_sensor_id(str(item)) == sensor_id for item in ids):
        ids.append(sensor_id)
        options = dict(entry.options)
        options[CONF_LIVE_SENSOR_IDS] = ids
        if getattr(getattr(entry, "state", None), "value", None) == "loaded":
            runtime.suppress_entry_reload_once(entry.entry_id)
        hass.config_entries.async_update_entry(entry, options=options)
    if not runtime.sensor_is_accepted(sensor_id):
        runtime.mark_sensor_accepted(sensor_id)
        # Keep materialization off the WebSocket response's hot path.
        await asyncio.sleep(0)
        runtime.finalize_sensor_acceptance(sensor_id)
    runtime.schedule_profile_assignment_refresh([entry.entry_id])



class RemoteGattSession:
    """One authenticated browser GATT bridge used by archive adapters.

    The browser owns the physical Bluetooth connection; adapter protocols stay
    in Python and issue bounded read/write/notify operations through this queue.
    """

    def __init__(self, hass: HomeAssistant, key: tuple[str, str, str]) -> None:
        self.hass = hass
        self.key = key
        self.connected = True
        self.closed = False
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
        self._pending: dict[str, asyncio.Future] = {}
        self._notify: dict[str, list[Any]] = defaultdict(list)
        self._sequence = 0

    async def request(
        self,
        operation: str,
        *,
        characteristic_uuid: str | None = None,
        payload: bytes | None = None,
        response: bool | None = None,
        timeout: float = 30.0,
    ) -> bytes:
        if self.closed:
            raise RuntimeError("remote_gatt_closed")
        self._sequence += 1
        request_id = f"g{self._sequence:x}"
        future = self.hass.loop.create_future()
        self._pending[request_id] = future
        item: dict[str, Any] = {"request_id": request_id, "operation": operation}
        if characteristic_uuid:
            item["characteristic_uuid"] = _normalize_uuid(characteristic_uuid)
        if payload is not None:
            item["payload"] = list(payload)
        if response is not None:
            item["response"] = bool(response)
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull as err:
            self._pending.pop(request_id, None)
            raise RuntimeError("remote_gatt_queue_full") from err
        try:
            result = await asyncio.wait_for(future, timeout=max(1.0, timeout))
        finally:
            self._pending.pop(request_id, None)
        if not isinstance(result, dict) or not result.get("ok"):
            message = str((result or {}).get("error") or "remote_gatt_failed")
            raise RuntimeError(message)
        data = _byte_payload((result or {}).get("payload") or [], maximum=65536)
        if operation == "connect":
            self.connected = True
        elif operation == "disconnect":
            self.connected = False
        return data

    async def poll(self, timeout: float = 20.0) -> dict[str, Any] | None:
        if self.closed:
            return None
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=max(1.0, timeout))
        except TimeoutError:
            return None

    def resolve(self, request_id: str, *, ok: bool, payload: Any = None, error: str = "") -> bool:
        future = self._pending.get(str(request_id))
        if future is None or future.done():
            return False
        future.set_result({"ok": bool(ok), "payload": payload or [], "error": str(error or "")[:300]})
        return True

    def add_notify(self, characteristic_uuid: str, callback) -> None:
        uuid = _normalize_uuid(characteristic_uuid)
        if callback not in self._notify[uuid]:
            self._notify[uuid].append(callback)

    def remove_notify(self, characteristic_uuid: str, callback=None) -> None:
        uuid = _normalize_uuid(characteristic_uuid)
        if callback is None:
            self._notify.pop(uuid, None)
            return
        callbacks = self._notify.get(uuid, [])
        if callback in callbacks:
            callbacks.remove(callback)
        if not callbacks:
            self._notify.pop(uuid, None)

    def publish_notify(self, characteristic_uuid: str, payload: bytes) -> int:
        uuid = _normalize_uuid(characteristic_uuid)
        callbacks = tuple(self._notify.get(uuid, ()))
        for callback in callbacks:
            try:
                callback(uuid, bytes(payload))
            except Exception:
                _LOGGER.debug("Remote GATT notify callback failed", exc_info=True)
        return len(callbacks)

    def close(self, reason: str = "remote_gatt_closed") -> None:
        self.closed = True
        self.connected = False
        for future in tuple(self._pending.values()):
            if not future.done():
                future.set_result({"ok": False, "payload": [], "error": reason})
        self._pending.clear()
        self._notify.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break


class RemoteGattClient:
    """Bleak-like client facade backed by one browser GATT bridge."""

    def __init__(self, session: RemoteGattSession) -> None:
        self._session = session

    @property
    def is_connected(self) -> bool:
        return bool(self._session.connected and not self._session.closed)

    async def connect(self) -> bool:
        await self._session.request("connect", timeout=25.0)
        return True

    async def disconnect(self) -> bool:
        if self._session.closed:
            return True
        try:
            await self._session.request("disconnect", timeout=10.0)
        except Exception:
            self._session.connected = False
        return True

    async def read_gatt_char(self, characteristic_uuid: str) -> bytearray:
        data = await self._session.request(
            "read", characteristic_uuid=characteristic_uuid, timeout=20.0
        )
        return bytearray(data)

    async def write_gatt_char(
        self, characteristic_uuid: str, data, response: bool = False
    ) -> None:
        await self._session.request(
            "write",
            characteristic_uuid=characteristic_uuid,
            payload=bytes(data),
            response=bool(response),
            timeout=20.0,
        )

    async def start_notify(self, characteristic_uuid: str, callback) -> None:
        self._session.add_notify(characteristic_uuid, callback)
        try:
            await self._session.request(
                "start_notify", characteristic_uuid=characteristic_uuid, timeout=20.0
            )
        except Exception:
            self._session.remove_notify(characteristic_uuid, callback)
            raise

    async def stop_notify(self, characteristic_uuid: str) -> None:
        await self._session.request(
            "stop_notify", characteristic_uuid=characteristic_uuid, timeout=10.0
        )
        self._session.remove_notify(characteristic_uuid)


class RemoteGatewayRuntime:
    """Per-HA decoder state for authenticated remote gateways."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._ble_revolutions: dict[tuple[str, str, str, str], _RevolutionState] = defaultdict(_RevolutionState)
        self._ble_sensor_ids: dict[tuple[str, str, str], str] = {}
        self._last_seen: dict[tuple[str, str, str], float] = {}
        self._last_prune = 0.0
        self._ant_assignment_pending: dict[tuple[str, str], set[int]] = {}
        self._ant_assignment_tasks: dict[tuple[str, str], asyncio.Task] = {}
        self._gatt_sessions: dict[tuple[str, str, str], RemoteGattSession] = {}
        self._gatt_sensor_keys: dict[str, tuple[str, str, str]] = {}

    def _prune_ble_state(self, *, force: bool = False) -> None:
        """Bound state retained for vanished browser Bluetooth devices."""
        now = time.monotonic()
        if not force and now - self._last_prune < 30.0:
            return
        self._last_prune = now
        stale = {
            key
            for key, seen in self._last_seen.items()
            if now - seen > REMOTE_BLE_STALE_SECONDS
        }
        if len(self._last_seen) - len(stale) > REMOTE_BLE_DEVICE_LIMIT:
            remaining = sorted(
                (
                    (seen, key)
                    for key, seen in self._last_seen.items()
                    if key not in stale
                ),
                reverse=True,
            )
            stale.update(key for _seen, key in remaining[REMOTE_BLE_DEVICE_LIMIT:])
        for key in stale:
            self._last_seen.pop(key, None)
            sensor_id = self._ble_sensor_ids.pop(key, None)
            session = self._gatt_sessions.pop(key, None)
            if session is not None:
                session.close("remote_ble_stale")
            if sensor_id:
                canonical = get_live_runtime(self.hass).resolve_sensor_id(sensor_id)
                if self._gatt_sensor_keys.get(canonical) == key:
                    self._gatt_sensor_keys.pop(canonical, None)
        if stale:
            for state_key in tuple(self._ble_revolutions):
                if state_key[:3] in stale:
                    self._ble_revolutions.pop(state_key, None)

    def schedule_ant_assignments(
        self,
        profile_entry_id: str,
        gateway_id: str,
        device_ids: set[int],
    ) -> None:
        """Union packet-batch IDs into one assignment worker per gateway."""
        if not device_ids:
            return
        key = (str(profile_entry_id), str(gateway_id))
        pending = self._ant_assignment_pending.setdefault(key, set())
        for device_id in sorted(device_ids):
            if len(pending) >= REMOTE_ASSIGNMENT_DEVICE_LIMIT:
                break
            pending.add(int(device_id))
        task = self._ant_assignment_tasks.get(key)
        if task is not None and not task.done():
            return
        if len(self._ant_assignment_tasks) >= REMOTE_ASSIGNMENT_GATEWAY_LIMIT:
            self._ant_assignment_pending.pop(key, None)
            _LOGGER.warning("Ignoring excess remote ANT+ assignment gateway %s", gateway_id)
            return

        async def _runner() -> None:
            try:
                while pending := self._ant_assignment_pending.get(key):
                    batch = set(pending)
                    pending.clear()
                    await _async_assign_remote_ant_devices(
                        self.hass, profile_entry_id, batch
                    )
                    await asyncio.sleep(0)
            finally:
                self._ant_assignment_pending.pop(key, None)
                self._ant_assignment_tasks.pop(key, None)

        self._ant_assignment_tasks[key] = self.hass.async_create_background_task(
            _runner(),
            f"fitness remote ANT+ profile assignment {gateway_id}",
            eager_start=False,
        )

    async def async_ensure_transport(self, transport: str) -> None:
        runtime = get_live_runtime(self.hass)
        await runtime.async_initialize()
        # Pairing a browser/native gateway is itself an explicit user action. Turn
        # on that transport once so publish() and the existing ANT remote receiver
        # are immediately usable. This does not require local radio hardware.
        if not runtime.adapter_enabled(transport):
            await runtime.async_configure_transport(transport, enabled=True)

    async def async_shutdown(self) -> None:
        """Cancel remote assignment work before the live hub is torn down."""
        tasks = {
            task for task in self._ant_assignment_tasks.values() if not task.done()
        }
        for task in tasks:
            task.cancel()
        if tasks:
            try:
                async with asyncio.timeout(5.0):
                    await asyncio.gather(*tasks, return_exceptions=True)
            except TimeoutError:
                _LOGGER.warning("Timed out stopping remote Fitness gateway workers")
        self._ant_assignment_tasks.clear()
        self._ant_assignment_pending.clear()
        self._ble_revolutions.clear()
        self._ble_sensor_ids.clear()
        self._last_seen.clear()
        for session in tuple(self._gatt_sessions.values()):
            session.close("gateway_shutdown")
        self._gatt_sessions.clear()
        self._gatt_sensor_keys.clear()

    def remote_gatt_client_for_sensor(self, sensor_id: str) -> RemoteGattClient | None:
        runtime = get_live_runtime(self.hass)
        canonical = runtime.resolve_sensor_id(str(sensor_id))
        key = self._gatt_sensor_keys.get(canonical)
        if key is None:
            for stored_id, candidate_key in tuple(self._gatt_sensor_keys.items()):
                if runtime.resolve_sensor_id(stored_id) == canonical:
                    key = candidate_key
                    self._gatt_sensor_keys[canonical] = candidate_key
                    break
        session = self._gatt_sessions.get(key) if key is not None else None
        if session is None or session.closed:
            return None
        return RemoteGattClient(session)

    def _ensure_gatt_session(
        self, profile_entry_id: str, gateway_id: str, device_id: str
    ) -> RemoteGattSession:
        key = (str(profile_entry_id), str(gateway_id), str(device_id))
        session = self._gatt_sessions.get(key)
        if session is None or session.closed:
            session = self._gatt_sessions[key] = RemoteGattSession(self.hass, key)
        else:
            session.connected = True
        return session

    async def async_poll_gatt(
        self, profile_entry_id: str, gateway_id: str, device_id: str
    ) -> dict[str, Any] | None:
        session = self._gatt_sessions.get((profile_entry_id, gateway_id, device_id))
        if session is None:
            return None
        return await session.poll(20.0)

    def resolve_gatt_result(
        self,
        profile_entry_id: str,
        gateway_id: str,
        device_id: str,
        request_id: str,
        *,
        ok: bool,
        payload: Any = None,
        error: str = "",
    ) -> bool:
        session = self._gatt_sessions.get((profile_entry_id, gateway_id, device_id))
        return bool(session and session.resolve(request_id, ok=ok, payload=payload, error=error))

    def publish_gatt_notify(
        self,
        profile_entry_id: str,
        gateway_id: str,
        device_id: str,
        characteristic_uuid: str,
        payload: bytes,
    ) -> int:
        session = self._gatt_sessions.get((profile_entry_id, gateway_id, device_id))
        if session is None:
            return 0
        return session.publish_notify(characteristic_uuid, payload)

    async def async_register_ble_device(
        self,
        *,
        profile_entry_id: str,
        gateway_id: str,
        device_id: str,
        name: str,
        service_uuids: list[str],
        characteristic_uuids: list[str],
        identity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._prune_ble_state()
        entry = _profile_entry(self.hass, profile_entry_id)
        if entry is None:
            raise ValueError("profile_not_found")
        await self.async_ensure_transport("bluetooth")
        runtime = get_live_runtime(self.hass)
        runtime.set_adapter_presence("bluetooth", True)

        services = {
            _normalize_uuid(item)[:128] for item in islice(service_uuids, 64)
        }
        chars = {
            _normalize_uuid(item)[:128]
            for item in islice(characteristic_uuids, 64)
        }
        capabilities: set[str] = set()
        for service, caps in SERVICE_CAPABILITIES.items():
            if service in services:
                capabilities.update(caps)
        for char in chars:
            meta = BLE_CHARACTERISTICS.get(char)
            if meta:
                capabilities.update(meta[0])

        endpoint_id = f"bluetooth:web:{profile_entry_id}:{gateway_id}:{device_id}"
        device_name = str(name or "Remote Bluetooth fitness sensor")[:160]
        provider = runtime.providers.get("bluetooth")
        archives = getattr(provider, "device_archives", None) if provider is not None else None
        archive_advertisement = (
            archives.match_remote_gatt(device_name, services)
            if archives is not None
            else None
        )
        if archive_advertisement is not None:
            capabilities.update(archive_advertisement.capabilities)
        if not capabilities:
            raise ValueError("unsupported_ble_sensor")

        raw_identity = identity if isinstance(identity, dict) else {}
        identity = dict(archive_advertisement.metadata) if archive_advertisement is not None else {}
        for key, value in islice(raw_identity.items(), len(REMOTE_BLE_IDENTITY_FIELDS)):
            clean_key = str(key).strip().lower()
            if clean_key not in REMOTE_BLE_IDENTITY_FIELDS:
                continue
            clean_value = str(value).strip()[:160]
            if clean_value:
                identity[clean_key] = clean_value
        # The browser cannot reveal a Bluetooth address. For an M1 its local-name
        # suffix is the exact route bridge shared with HA's verified archive
        # advertisement. Compute it server-side so a client cannot invent an
        # arbitrary physical identity token.
        route_identity = cycplus_m1_name_identity(device_name) or {}
        if (
            not route_identity.get("fitness_physical_identity")
            and CYCPLUS_M1_SERVICE_UUID in services
        ):
            serial_identity = cycplus_m1_serial_identity(
                identity.get("serial_number")
            )
            if serial_identity:
                route_identity.update(serial_identity)
        identity.update(route_identity)
        if archive_advertisement is not None and archives is not None:
            identity = archives.enrich_connected_metadata(identity, services)
        existing = runtime.find_sensor_for_remote_ble_identity(
            name=device_name,
            capabilities=capabilities,
            identity=identity,
            endpoint_id=endpoint_id,
        )
        if existing is not None:
            sensor = existing
            runtime.endpoint_aliases[endpoint_id] = sensor.sensor_id
            runtime.enrich_sensor_capabilities(
                sensor.sensor_id, capabilities, transport="bluetooth"
            )
            sensor.metadata.setdefault("remote_gateways", {})[gateway_id] = {
                "device_id": device_id,
                "profile_entry_id": profile_entry_id,
                **identity,
            }
        else:
            sensor = runtime.register_transport_sensor(
                transport="bluetooth",
                endpoint_id=endpoint_id,
                name=device_name,
                capabilities=capabilities,
                address=f"web:{device_id}",
                source=f"remote:{gateway_id}",
                last_seen=datetime.now(timezone.utc),
                available=True,
                metadata={
                    "remote_gateway": gateway_id,
                    "remote_device_id": device_id,
                    "browser_remote": True,
                    "service_uuids": sorted(services),
                    "characteristic_uuids": sorted(chars),
                    "profile_entry_id": profile_entry_id,
                    "gateway_protocol": REMOTE_GATEWAY_PROTOCOL,
                    **identity,
                },
            )
        self._ble_sensor_ids[(profile_entry_id, gateway_id, device_id)] = sensor.sensor_id
        self._last_seen[(profile_entry_id, gateway_id, device_id)] = time.monotonic()
        canonical_sensor_id = runtime.resolve_sensor_id(sensor.sensor_id)
        if archive_advertisement is not None:
            self._ensure_gatt_session(profile_entry_id, gateway_id, device_id)
            self._gatt_sensor_keys[canonical_sensor_id] = (profile_entry_id, gateway_id, device_id)
        await _async_assign_sensor_to_profile(self.hass, runtime, entry, canonical_sensor_id)
        if archive_advertisement is not None and archives is not None:
            archives.schedule_archive_sync(
                profile_id=entry.entry_id,
                sensor_id=canonical_sensor_id,
                delay=0.0,
                force=True,
                reason="remote_gatt_connected",
            )
        return {
            "sensor_id": canonical_sensor_id,
            "capabilities": sorted(capabilities),
            "archive_adapter": str(identity.get("archive_adapter") or ""),
            "remote_archive": archive_advertisement is not None,
            "assigned_profile_entry_id": entry.entry_id,
        }

    def disconnect_ble_device(
        self,
        *,
        profile_entry_id: str,
        gateway_id: str,
        device_id: str,
    ) -> dict[str, Any]:
        """Mark one browser BLE endpoint offline without deleting assignment."""
        self._prune_ble_state()
        key = (profile_entry_id, gateway_id, device_id)
        runtime = get_live_runtime(self.hass)
        browser_endpoint_id = (
            f"bluetooth:web:{profile_entry_id}:{gateway_id}:{device_id}"
        )
        sensor_id = self._ble_sensor_ids.pop(key, None)
        if not sensor_id:
            sensor_id = runtime.endpoint_aliases.get(browser_endpoint_id)
        if sensor_id:
            sensor_id = runtime.resolve_sensor_id(sensor_id)
            sensor = runtime.sensors.get(sensor_id)
            endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
            other_browser_route_active = any(
                runtime.resolve_sensor_id(mapped_sensor_id) == sensor_id
                for mapped_sensor_id in self._ble_sensor_ids.values()
            )
            # A browser route may be only an alias to a Bluetooth endpoint seen
            # directly by Home Assistant (and possibly already merged with
            # ANT+). Disconnecting the browser must never mark that local route
            # unavailable. Only own the availability flag when this exact web
            # route created the canonical Bluetooth endpoint and no other
            # browser route is still publishing to it.
            if (
                endpoint is not None
                and endpoint.endpoint_id == browser_endpoint_id
                and not other_browser_route_active
            ):
                runtime.refresh_transport_endpoint(
                    sensor_id,
                    "bluetooth",
                    last_seen=endpoint.last_seen,
                    rssi=endpoint.rssi,
                    source=endpoint.source,
                    available=False,
                )
        self._last_seen.pop(key, None)
        session = self._gatt_sessions.pop(key, None)
        if session is not None:
            session.close("remote_ble_disconnected")
        if sensor_id:
            canonical = runtime.resolve_sensor_id(sensor_id)
            if self._gatt_sensor_keys.get(canonical) == key:
                self._gatt_sensor_keys.pop(canonical, None)
        for state_key in tuple(self._ble_revolutions):
            if state_key[:3] == key:
                self._ble_revolutions.pop(state_key, None)
        return {"disconnected": True, "sensor_id": sensor_id or ""}

    def async_publish_ble_frame(
        self,
        *,
        profile_entry_id: str,
        gateway_id: str,
        device_id: str,
        characteristic_uuid: str,
        payload: bytes,
    ) -> dict[str, Any]:
        self._prune_ble_state()
        runtime = get_live_runtime(self.hass)
        sensor_id = self._ble_sensor_ids.get((profile_entry_id, gateway_id, device_id))
        if not sensor_id:
            endpoint = f"bluetooth:web:{profile_entry_id}:{gateway_id}:{device_id}"
            sensor_id = runtime.endpoint_aliases.get(endpoint)
        if not sensor_id:
            raise ValueError("ble_device_not_registered")
        characteristic_uuid = _normalize_uuid(characteristic_uuid)
        spec = BLE_CHARACTERISTICS.get(characteristic_uuid)
        if spec is None:
            return {"accepted": False, "reason": "unsupported_characteristic"}
        state = self._ble_revolutions[(profile_entry_id, gateway_id, device_id, characteristic_uuid)]
        decoder = spec[1]
        if decoder == "hr":
            values = _parse_hr(payload)
        elif decoder == "cycling_power":
            values = _parse_cycling_power(payload, state)
        elif decoder == "csc":
            values = _parse_csc(payload, state)
        elif decoder == "rsc":
            values = _parse_rsc(payload)
        elif decoder == "ftms_indoor_bike":
            values = _parse_ftms_indoor_bike(payload)
        elif decoder == "ftms_treadmill":
            values = _parse_ftms_treadmill(payload)
        else:
            values = {}
        if decoder == "battery":
            values = _parse_battery(payload)
            if values:
                runtime.publish_passive(
                    sensor_id,
                    values,
                    transport="bluetooth",
                    metadata={"battery": _battery_metadata()},
                )
        elif values:
            runtime.publish(sensor_id, values, transport="bluetooth")
        self._last_seen[(profile_entry_id, gateway_id, device_id)] = time.monotonic()
        return {"accepted": True, "values": values}


async def _async_assign_remote_ant_devices(
    hass: HomeAssistant, profile_entry_id: str, device_ids: set[int]
) -> None:
    """Accept ANT+ devices materialized by the existing remote-packet worker."""
    if not device_ids:
        return
    entry = _profile_entry(hass, profile_entry_id)
    if entry is None:
        return
    runtime = get_live_runtime(hass)
    # ANT+ discovery intentionally requires multiple RF pages. Give the existing
    # worker/provider enough time to confirm a semantic device, without blocking
    # the browser's WebSocket packet acknowledgement.
    pending = set(device_ids)
    for _attempt in range(30):
        changed = False
        for device_id in tuple(pending):
            sensor_id = runtime.endpoint_aliases.get(f"antplus:{device_id}")
            if not sensor_id:
                continue
            try:
                await _async_assign_sensor_to_profile(hass, runtime, entry, sensor_id)
            except Exception:  # noqa: BLE001 - background assignment best effort
                _LOGGER.debug("Unable to assign remote ANT+ sensor %s", device_id, exc_info=True)
            pending.discard(device_id)
            changed = True
        if not pending:
            return
        await asyncio.sleep(0.2 if changed else 0.35)


def get_remote_gateway_runtime(hass: HomeAssistant) -> RemoteGatewayRuntime:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.get(REMOTE_GATEWAY_KEY)
    if runtime is None:
        runtime = RemoteGatewayRuntime(hass)
        data[REMOTE_GATEWAY_KEY] = runtime
    return runtime


def _https_origin(value: Any) -> str:
    """Return a canonical HTTPS origin, rejecting credentials and URL tails."""
    raw = str(value or "").strip().rstrip("/")
    try:
        parsed = urlparse(raw)
        port = parsed.port
    except ValueError:
        return ""
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        return ""
    host = parsed.hostname.lower().rstrip(".")
    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != 443:
        authority = f"{authority}:{port}"
    return f"https://{authority}"


def _external_hass_url(
    hass: HomeAssistant,
    browser_origin: str,
    refresh_client_id: str,
) -> str:
    """Resolve a Cast URL without ever forwarding auth to an arbitrary origin."""
    browser_origin = str(browser_origin or "").strip().rstrip("/")
    try:
        configured = _https_origin(
            get_url(hass, require_ssl=True, prefer_external=True)
        )
        if configured:
            return configured
    except NoURLAvailableError:
        pass
    browser = _https_origin(browser_origin)
    client = _https_origin(refresh_client_id)
    if browser and client and browser == client:
        return browser
    raise ValueError("external_https_required")


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/capabilities",
})
@websocket_api.async_response
async def websocket_remote_gateway_capabilities(hass: HomeAssistant, connection, msg) -> None:
    remote_archive_services = sorted({
        str(service).lower()
        for adapter in ARCHIVE_ADAPTERS
        for service in getattr(adapter, "remote_gatt_services", frozenset())
        if str(service).strip()
    })
    connection.send_result(msg["id"], {
        "protocol_version": REMOTE_GATEWAY_PROTOCOL,
        "transports": ["bluetooth", "antplus"],
        "ble_payload": "raw_gatt_characteristic",
        "remote_gatt_proxy": True,
        "remote_ble_optional_services": remote_archive_services,
        "antplus_payload": "decoded_ant_serial_extended_packet",
        "local_cast": {
            "receiver_application_id": LOCAL_CAST_APP_ID,
            "namespace": LOCAL_CAST_NAMESPACE,
            "requires_external_https": True,
        },
    })


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/hello",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Optional("client_name", default="Fitness remote client"): vol.All(str, vol.Length(max=160)),
    vol.Optional("platform", default="browser"): vol.All(str, vol.Length(max=32)),
    vol.Optional("transports", default=[]): vol.All([str], vol.Length(max=16)),
})
@websocket_api.async_response
async def websocket_remote_gateway_hello(hass: HomeAssistant, connection, msg) -> None:
    entry = _profile_entry(hass, msg["profile_entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not found")
        return
    await _require_profile_access(hass, connection, entry.entry_id)
    try:
        gateway_id = _clean_gateway_id(msg["gateway_id"])
        transports = {
            str(item).lower()[:32]
            for item in islice(msg.get("transports") or [], 16)
        }
        remote = get_remote_gateway_runtime(hass)
        for transport in transports & {"bluetooth", "antplus"}:
            await remote.async_ensure_transport(transport)
        if "bluetooth" in transports:
            get_live_runtime(hass).set_adapter_presence("bluetooth", True)
        if "antplus" in transports:
            # A browser saying "I can do ANT+" is not evidence that any
            # physical USB receiver is actually attached.  Do not invent a
            # gateway-scoped adapter here: the authoritative status message
            # sent after WebUSB permission carries VID/PID/serial and is what
            # materializes or reactivates the physical receiver.
            hass.bus.async_fire(REMOTE_GATEWAY_HELLO_EVENT, {
                "gateway_id": gateway_id,
                "control_protocol": 0,
                "adapters": [],
            })
        connection.send_result(msg["id"], {
            "protocol_version": REMOTE_GATEWAY_PROTOCOL,
            "gateway_id": gateway_id,
            "profile_entry_id": entry.entry_id,
            "transports": sorted(transports),
        })
    except Exception as err:  # noqa: BLE001 - WebSocket validation boundary
        connection.send_error(msg["id"], "gateway_error", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/ble_device",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("device_id"): vol.All(str, vol.Length(max=256)),
    vol.Optional("name", default="Remote Bluetooth fitness sensor"): vol.All(str, vol.Length(max=160)),
    vol.Optional("service_uuids", default=[]): vol.All([str], vol.Length(max=64)),
    vol.Optional("characteristic_uuids", default=[]): vol.All([str], vol.Length(max=64)),
    vol.Optional("identity", default={}): {str: str},
})
@websocket_api.async_response
async def websocket_remote_gateway_ble_device(hass: HomeAssistant, connection, msg) -> None:
    await _require_profile_access(hass, connection, str(msg["profile_entry_id"]))
    try:
        bounded_payload(
            msg.get("identity") or {},
            max_nodes=32,
            max_depth=2,
            max_string_length=160,
        )
        result = await get_remote_gateway_runtime(hass).async_register_ble_device(
            profile_entry_id=str(msg["profile_entry_id"]),
            gateway_id=_clean_gateway_id(msg["gateway_id"]),
            device_id=_clean_device_id(msg["device_id"]),
            name=str(msg.get("name") or "Remote Bluetooth fitness sensor"),
            service_uuids=list(msg.get("service_uuids") or []),
            characteristic_uuids=list(msg.get("characteristic_uuids") or []),
            identity=dict(msg.get("identity") or {}),
        )
        connection.send_result(msg["id"], result)
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Remote BLE device registration failed")
        connection.send_error(msg["id"], "ble_gateway_error", "Unable to register Bluetooth sensor")


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/ble_disconnect",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("device_id"): vol.All(str, vol.Length(max=256)),
})
@websocket_api.async_response
async def websocket_remote_gateway_ble_disconnect(hass: HomeAssistant, connection, msg) -> None:
    await _require_profile_access(hass, connection, str(msg["profile_entry_id"]))
    try:
        result = get_remote_gateway_runtime(hass).disconnect_ble_device(
            profile_entry_id=str(msg["profile_entry_id"]),
            gateway_id=_clean_gateway_id(msg["gateway_id"]),
            device_id=_clean_device_id(msg["device_id"]),
        )
        connection.send_result(msg["id"], result)
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Remote BLE disconnect failed")
        connection.send_error(msg["id"], "ble_gateway_error", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/ble_frames",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("device_id"): vol.All(str, vol.Length(max=256)),
    vol.Required("frames"): vol.All(
        [dict], vol.Length(max=64),
        bounded_websocket_payload(max_nodes=512, max_depth=4, max_string_length=1_024),
    ),
})
@websocket_api.async_response
async def websocket_remote_gateway_ble_frames(hass: HomeAssistant, connection, msg) -> None:
    await _require_profile_access(hass, connection, str(msg["profile_entry_id"]))
    try:
        gateway_id = _clean_gateway_id(msg["gateway_id"])
        device_id = _clean_device_id(msg["device_id"])
        frames = list(msg["frames"])
        if len(frames) > 64:
            raise ValueError("too_many_ble_frames")
        accepted = 0
        latest: dict[str, float] = {}
        remote = get_remote_gateway_runtime(hass)
        for frame in frames:
            result = remote.async_publish_ble_frame(
                profile_entry_id=str(msg["profile_entry_id"]),
                gateway_id=gateway_id,
                device_id=device_id,
                characteristic_uuid=str(frame.get("characteristic_uuid") or ""),
                payload=_byte_payload(frame.get("payload"), maximum=256),
            )
            if result.get("accepted"):
                accepted += 1
                latest.update(result.get("values") or {})
        connection.send_result(msg["id"], {"accepted_frames": accepted, "values": latest})
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Remote BLE frame batch failed")
        connection.send_error(msg["id"], "ble_gateway_error", str(err))



@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/gatt_poll",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("device_id"): vol.All(str, vol.Length(max=256)),
})
@websocket_api.async_response
async def websocket_remote_gateway_gatt_poll(hass: HomeAssistant, connection, msg) -> None:
    await _require_profile_access(hass, connection, str(msg["profile_entry_id"]))
    try:
        request = await get_remote_gateway_runtime(hass).async_poll_gatt(
            str(msg["profile_entry_id"]),
            _clean_gateway_id(msg["gateway_id"]),
            _clean_device_id(msg["device_id"]),
        )
        connection.send_result(msg["id"], {"request": request})
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/gatt_result",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("device_id"): vol.All(str, vol.Length(max=256)),
    vol.Required("request_id"): vol.All(str, vol.Length(max=64)),
    vol.Required("ok"): bool,
    vol.Optional("payload", default=[]): vol.All(list, vol.Length(max=4096)),
    vol.Optional("error", default=""): vol.All(str, vol.Length(max=300)),
})
@websocket_api.async_response
async def websocket_remote_gateway_gatt_result(hass: HomeAssistant, connection, msg) -> None:
    await _require_profile_access(hass, connection, str(msg["profile_entry_id"]))
    try:
        payload = _byte_payload(msg.get("payload") or [], maximum=4096)
        resolved = get_remote_gateway_runtime(hass).resolve_gatt_result(
            str(msg["profile_entry_id"]),
            _clean_gateway_id(msg["gateway_id"]),
            _clean_device_id(msg["device_id"]),
            str(msg["request_id"]),
            ok=bool(msg["ok"]),
            payload=list(payload),
            error=str(msg.get("error") or ""),
        )
        connection.send_result(msg["id"], {"resolved": resolved})
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/gatt_notify",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("device_id"): vol.All(str, vol.Length(max=256)),
    vol.Required("characteristic_uuid"): vol.All(str, vol.Length(max=128)),
    vol.Required("payload"): vol.All(list, vol.Length(max=4096)),
})
@websocket_api.async_response
async def websocket_remote_gateway_gatt_notify(hass: HomeAssistant, connection, msg) -> None:
    await _require_profile_access(hass, connection, str(msg["profile_entry_id"]))
    try:
        delivered = get_remote_gateway_runtime(hass).publish_gatt_notify(
            str(msg["profile_entry_id"]),
            _clean_gateway_id(msg["gateway_id"]),
            _clean_device_id(msg["device_id"]),
            str(msg["characteristic_uuid"]),
            _byte_payload(msg["payload"], maximum=4096),
        )
        connection.send_result(msg["id"], {"delivered": delivered})
    except ValueError as err:
        connection.send_error(msg["id"], str(err), str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/ant_packets",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("packets"): vol.All(
        [dict], vol.Length(max=256),
        bounded_websocket_payload(max_nodes=2_048, max_depth=4, max_string_length=1_024),
    ),
})
@websocket_api.async_response
async def websocket_remote_gateway_ant_packets(hass: HomeAssistant, connection, msg) -> None:
    if _profile_entry(hass, msg["profile_entry_id"]) is None:
        connection.send_error(msg["id"], "profile_not_found", "Fitness profile not found")
        return
    await _require_profile_access(hass, connection, str(msg["profile_entry_id"]))
    try:
        gateway_id = _clean_gateway_id(msg["gateway_id"])
        packets = list(msg["packets"])
        if len(packets) > 256:
            raise ValueError("too_many_ant_packets")
        sanitized: list[dict[str, Any]] = []
        for packet in packets:
            item = {
                "device_id": int(packet["device_id"]),
                "device_type": int(packet["device_type"]),
                "transmission_type": int(packet["transmission_type"]),
                "payload": list(_byte_payload(packet.get("payload"), exact=8)),
                # Adapter identity belongs to this authenticated gateway. Never
                # accept a client-selected adapter id that could alias a local
                # dongle or another user's gateway.
                "adapter_id": f"webusb:{gateway_id}",
            }
            if not 0 <= item["device_id"] <= 0xFFFF:
                raise ValueError("invalid_ant_device_id")
            if not 0 <= item["device_type"] <= 0xFF or not 0 <= item["transmission_type"] <= 0xFF:
                raise ValueError("invalid_ant_channel_id")
            sanitized.append(item)
        # Existing ANT remote worker owns coalescing, profile decoding and physical
        # sensor registration. Browser/native gateways only transport RF packets.
        hass.bus.async_fire(REMOTE_PACKET_EVENT, {"gateway_id": gateway_id, "packets": sanitized})
        device_ids = {int(item["device_id"]) for item in sanitized}
        get_remote_gateway_runtime(hass).schedule_ant_assignments(
            str(msg["profile_entry_id"]),
            gateway_id,
            device_ids,
        )
        connection.send_result(msg["id"], {"accepted_packets": len(sanitized)})
    except (KeyError, TypeError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_ant_packet", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/remote_gateway/status",
    vol.Required("profile_entry_id"): vol.All(str, vol.Length(max=128)),
    vol.Required("gateway_id"): vol.All(str, vol.Length(max=128)),
    vol.Optional("antplus_connected", default=False): bool,
    vol.Optional("antplus_vendor_id"): vol.All(str, vol.Length(max=16)),
    vol.Optional("antplus_product_id"): vol.All(str, vol.Length(max=16)),
    vol.Optional("antplus_serial_number"): vol.All(str, vol.Length(max=160)),
    vol.Optional("antplus_serial_source"): vol.All(str, vol.Length(max=32)),
    vol.Optional("antplus_usb_serial_number"): vol.All(str, vol.Length(max=160)),
    vol.Optional("antplus_manufacturer"): vol.All(str, vol.Length(max=160)),
    vol.Optional("antplus_product"): vol.All(str, vol.Length(max=160)),
})
@websocket_api.async_response
async def websocket_remote_gateway_status(hass: HomeAssistant, connection, msg) -> None:
    await _require_profile_access(hass, connection, str(msg["profile_entry_id"]))
    try:
        gateway_id = _clean_gateway_id(msg["gateway_id"])
        connected = bool(msg.get("antplus_connected"))
        adapter: AntUsbAdapter | None = None
        adapters: list[dict[str, Any]] = []
        if connected:
            vid = str(msg.get("antplus_vendor_id") or "0FCF").strip().upper().zfill(4)
            pid = str(msg.get("antplus_product_id") or "").strip().upper().zfill(4)
            if (vid, pid) not in {("0FCF", "1008"), ("0FCF", "1009")}:
                raise ValueError(f"Unsupported remote ANT+ USB adapter {vid}:{pid}")
            adapter = AntUsbAdapter(
                vid=vid,
                pid=pid,
                serial=str(msg.get("antplus_serial_number") or "").strip() or None,
                manufacturer=str(msg.get("antplus_manufacturer") or "").strip() or None,
                product=str(msg.get("antplus_product") or "").strip() or None,
                source="remote",
                gateway_id=gateway_id,
                serial_source=str(msg.get("antplus_serial_source") or "").strip() or None,
                usb_serial=str(msg.get("antplus_usb_serial_number") or "").strip() or None,
            )
            # ``_parse_adapters`` consumes the same canonical mapping used by
            # local ANT discovery (vid/pid/serial).  This is deliberately not a
            # browser/gateway identifier: a serial-numbered stick therefore
            # resolves to the exact same stable key when moved between hosts.
            adapters.append({
                **adapter.identity_storage(),
                "transport": "webusb",
                "serial_source": adapter.serial_source,
                "usb_serial": adapter.usb_serial,
            })
        hass.bus.async_fire(REMOTE_GATEWAY_STATUS_EVENT, {
            "gateway_id": gateway_id,
            "control_protocol": 0,
            "authoritative": True,
            "adapters": adapters,
            # WebUSB has already claimed/configured the stick before this
            # status is sent, so this is an authoritative physical Capture
            # state even though protocol-v1 browsers do not yet accept remote
            # Capture commands from Home Assistant.
            "capture_states": ({adapter.stable_key: True} if adapter is not None else {}),
        })
        connection.send_result(msg["id"], {
            "ok": True,
            "adapter_id": adapter.stable_key if adapter is not None else None,
        })
    except ValueError as err:
        connection.send_error(msg["id"], "gateway_error", str(err))


async def _async_cleanup_legacy_local_cast_tokens(hass: HomeAssistant) -> None:
    """Remove temporary Cast tokens created by pre-unreleased-59 Fitness.

    Browser-local Cast now reuses the already-authenticated browser session's
    refresh token, exactly like Home Assistant's own Web Sender. Do not remove
    the Home Assistant Cast integration's normal token; only remove tokens whose
    client name proves they were created by the old Fitness implementation.
    """
    for user in await hass.auth.async_get_users():
        if not user.system_generated or user.name not in LEGACY_LOCAL_CAST_USER_NAMES:
            continue
        for token in list(user.refresh_tokens.values()):
            if str(token.client_name or "").startswith("Fitness TV local Cast ·"):
                hass.auth.async_remove_refresh_token(token)


def _current_browser_refresh_token(hass: HomeAssistant, connection):
    """Return the refresh token backing the authenticated WebSocket session."""
    token_id = getattr(connection, "refresh_token_id", None)
    if not token_id:
        return None
    token = hass.auth.async_get_refresh_token(str(token_id))
    user = getattr(connection, "user", None)
    if token is None or user is None or token.user.id != user.id:
        return None
    return token


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/tv/local_cast_credentials",
    vol.Optional("profile_entry_id", default=""): vol.All(str, vol.Length(max=128)),
    vol.Optional("overview", default=False): bool,
    vol.Optional("browser_origin", default=""): vol.All(str, vol.Length(max=2_048)),
})
@websocket_api.async_response
async def websocket_tv_local_cast_credentials(hass: HomeAssistant, connection, msg) -> None:
    overview = bool(msg.get("overview"))
    entry = None
    if overview:
        await get_fitness_access_controller(hass).async_require_admin(connection)
    else:
        entry = _profile_entry(hass, msg.get("profile_entry_id"))
        if entry is None:
            connection.send_error(msg["id"], "profile_not_found", "Fitness profile not found")
            return
        await _require_profile_access(hass, connection, entry.entry_id)
    user = getattr(connection, "user", None)
    if user is None:
        connection.send_error(msg["id"], "auth_required", "Authenticated Home Assistant user required")
        return
    try:
        refresh = _current_browser_refresh_token(hass, connection)
        if refresh is None:
            connection.send_error(
                msg["id"],
                "local_cast_session_auth_unavailable",
                "Local Cast needs a normal authenticated Home Assistant browser session. Reload Home Assistant and sign in again.",
            )
            return
        hass_url = _external_hass_url(
            hass,
            str(msg.get("browser_origin") or ""),
            str(refresh.client_id or ""),
        )

        # This is intentionally the *current browser user's* refresh token and
        # its matching client id. Home Assistant frontend's Web Sender uses these
        # exact credentials for Home Assistant Cast. It also preserves the current
        # user's permissions on the TV instead of elevating Cast to an admin-only
        # system account. The token belongs to the existing browser session, so
        # Fitness must never revoke it when the Cast session ends.
        connection.send_result(msg["id"], {
            "receiver_application_id": LOCAL_CAST_APP_ID,
            "namespace": LOCAL_CAST_NAMESPACE,
            "refresh_token": refresh.token,
            "client_id": refresh.client_id,
            "credential_source": "current_browser_session",
            "hass_url": hass_url,
            "dashboard_path": "fitness-tv",
            "view_path": "cast-overview" if overview else f"cast-{entry.entry_id}",
        })
    except ValueError as err:
        connection.send_error(msg["id"], str(err), "Local Cast requires an externally reachable HTTPS Home Assistant URL")
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unable to prepare browser-local Fitness Cast")
        connection.send_error(msg["id"], "local_cast_error", "Unable to prepare local Cast")


@websocket_api.websocket_command({
    vol.Required("type"): "fitness/tv/local_cast_release",
    vol.Required("token_id"): vol.All(str, vol.Length(max=128)),
})
@websocket_api.async_response
async def websocket_tv_local_cast_release(hass: HomeAssistant, connection, msg) -> None:
    """Backward-compatible cleanup for old Fitness-created Cast tokens only.

    unreleased-59 and newer never return a token_id and never call this command.
    Explicitly refuse to remove the refresh token backing the caller's current
    Home Assistant session.
    """
    await get_fitness_access_controller(hass).async_require_admin(connection)
    token_id = str(msg["token_id"])
    if token_id == getattr(connection, "refresh_token_id", None):
        connection.send_result(msg["id"], {"released": False})
        return
    token = hass.auth.async_get_refresh_token(token_id)
    if (
        token is None
        or not token.user.system_generated
        or token.user.name not in LEGACY_LOCAL_CAST_USER_NAMES
        or not str(token.client_name or "").startswith("Fitness TV local Cast ·")
    ):
        connection.send_result(msg["id"], {"released": False})
        return
    hass.auth.async_remove_refresh_token(token)
    connection.send_result(msg["id"], {"released": True})


def async_register_remote_gateway_websocket_commands(hass: HomeAssistant) -> None:
    """Register remote-gateway and local-Cast WebSocket commands once."""
    data = hass.data.setdefault(DOMAIN, {})
    key = "_remote_gateway_websocket_registered"
    if data.get(key):
        return
    data[key] = True
    hass.async_create_background_task(
        _async_cleanup_legacy_local_cast_tokens(hass),
        "fitness cleanup legacy local cast tokens",
        eager_start=False,
    )
    for command in (
        websocket_remote_gateway_capabilities,
        websocket_remote_gateway_hello,
        websocket_remote_gateway_ble_device,
        websocket_remote_gateway_ble_disconnect,
        websocket_remote_gateway_ble_frames,
        websocket_remote_gateway_gatt_poll,
        websocket_remote_gateway_gatt_result,
        websocket_remote_gateway_gatt_notify,
        websocket_remote_gateway_ant_packets,
        websocket_remote_gateway_status,
        websocket_tv_local_cast_credentials,
        websocket_tv_local_cast_release,
    ):
        websocket_api.async_register_command(hass, command)
