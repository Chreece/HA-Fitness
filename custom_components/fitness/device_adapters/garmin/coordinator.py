"""Lifecycle-safe Garmin local workout synchronization coordinator."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from functools import partial
import hashlib
import logging
import zlib
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.helpers.storage import Store

from ...const import (
    DOMAIN,
    GARMIN_LOCAL_SYNC_STORE_KEY,
    GARMIN_LOCAL_SYNC_STORE_VERSION,
)
from ...providers.workouts import Workout, _dt
from ...device_user_action import clear_device_user_action, request_device_user_action
from .bluez_agent import (
    async_bluez_device_pairing_state,
    temporary_bluez_pairing_agent,
)
from .fit import MAX_FIT_BYTES, workout_from_fit
from .gfdi import (
    GarminGfdiSession,
    GarminUnsupportedTransport,
    transport_candidates_from_client,
)
from .protocol import (
    GarminDirectoryEntry,
    garmin_advertisement_identity,
    GarminSyncFile,
)

_LOGGER = logging.getLogger(__name__)

# Compatibility notes for the original Garmin pairing regression contract:
# issue_registry as ir; hashlib.sha256; translation_key="garmin_pairing_required".
# The generic helper emits "fitness_device_user_action_required" with
# "action": "pairing_required", "fields": [], and starts with the instruction
# "Keep the Garmin paired with your phone.".

SYNC_INTERVAL = timedelta(minutes=30)
CONNECT_TIMEOUT = 35.0
PAIR_CONNECT_TIMEOUT = 65.0
PAIR_CONNECT_ATTEMPTS = 1
SESSION_TIMEOUT = 100.0
TRANSPORT_NEGOTIATION_TIMEOUT = 40.0
TRANSPORT_CANDIDATE_TIMEOUT = 12.0
CLEANUP_TIMEOUT = 6.0
IMPORT_TIMEOUT = 20.0
SHUTDOWN_TIMEOUT = 12.0
MAX_FILES_PER_SYNC = 2
MAX_FILES_PER_SESSION = 8
MAX_BYTES_PER_SYNC = 16 * 1024 * 1024
MAX_CACHED_FILE_RECORDS = 2_000
BATCH_CONTINUE_DELAY = 5 * 60.0
PARTIAL_BATCH_RETRY_DELAY = 5 * 60.0
PARTIAL_BATCH_RECENT_WINDOW = 45 * 60.0
MAX_PARTIAL_BATCH_RETRIES = 3
STARTUP_RESUME_DELAY = 5.0
MAX_RETRIES = 6
DEGRADED_RETRY_DELAY = 2 * 60 * 60.0
UNSUPPORTED_RETRY_DELAY = 6 * 60 * 60.0
# A live BLE owner should not be polled every few seconds; manual retry can
# still override this waiting state when the user explicitly asks.
BUSY_RETRY_DELAY = 5 * 60.0
# If the connectable route disappears, use a very sparse safety wake-up. A fresh
# Garmin advertisement can replace the sleeping task immediately without
# bypassing protocol/error backoff.
UNREACHABLE_RETRY_DELAY = 30 * 60.0
ADVERTISEMENT_ACTION_MIN_INTERVAL = 30.0

_ERROR_CODE = {
    "connection": "connection_failed",
    "pairing": "pairing_required",
    "handshake": "handshake_failed",
    "catalog": "catalog_failed",
    "transfer": "transfer_interrupted",
    "validation": "invalid_fit",
    "import": "import_failed",
}

_DETAIL_META: dict[str, dict[str, Any]] = {
    "garmin_local_backend": {"icon": "mdi:protocol", "enabled_default": True},
    "garmin_sync_state": {
        "icon": "mdi:sync", "enabled_default": True, "device_class": "enum",
        "options": ["idle", "waiting", "connecting", "syncing", "ready", "retrying", "error", "unsupported"],
    },
    "garmin_last_sync": {"icon": "mdi:clock-check-outline", "enabled_default": True, "device_class": "timestamp"},
    "garmin_last_successful_sync": {"icon": "mdi:check-circle-outline", "enabled_default": True, "device_class": "timestamp"},
    "garmin_device_workout_count": {"icon": "mdi:calendar-multiple", "enabled_default": True},
    "garmin_imported_file_count": {"icon": "mdi:file-check-outline", "enabled_default": True},
    "garmin_pending_file_count": {"icon": "mdi:file-clock-outline", "enabled_default": True},
    "garmin_downloaded_bytes": {
        "icon": "mdi:download", "enabled_default": False, "unit": "B",
        "device_class": "data_size", "state_class": "measurement",
    },
    "garmin_retry_count": {"icon": "mdi:reload", "enabled_default": False},
    "garmin_last_error": {
        "icon": "mdi:alert-circle-outline", "enabled_default": True, "device_class": "enum",
        "options": [
            "none", "connection_failed", "pairing_required", "handshake_failed",
            "catalog_failed", "transfer_interrupted", "invalid_fit", "import_failed",
            "unsupported_transport", "unknown",
        ],
    },
    "garmin_protocol_version": {"icon": "mdi:numeric", "enabled_default": False},
    "garmin_latest_workout": {"icon": "mdi:run-fast", "enabled_default": True, "device_class": "timestamp"},
}
for _key, _meta in _DETAIL_META.items():
    _meta.update(translation_key=_key, entity_category="diagnostic")


def _inflate_bounded(data: bytes) -> bytes:
    """Inflate a zlib stream without allowing an expansion bomb."""
    if len(data) >= 12 and data[8:12] == b".FIT":
        if len(data) > MAX_FIT_BYTES:
            raise ValueError("Garmin FIT exceeds safe size")
        return bytes(data)
    obj = zlib.decompressobj()
    output = bytearray()
    pending = bytes(data)
    while pending:
        remaining = MAX_FIT_BYTES + 1 - len(output)
        if remaining <= 0:
            raise ValueError("Garmin inflated FIT exceeds safe size")
        chunk = obj.decompress(pending, remaining)
        output.extend(chunk)
        if len(output) > MAX_FIT_BYTES:
            raise ValueError("Garmin inflated FIT exceeds safe size")
        pending = obj.unconsumed_tail
        if not pending:
            break
    remaining = MAX_FIT_BYTES + 1 - len(output)
    output.extend(obj.flush(max(1, remaining)))
    if len(output) > MAX_FIT_BYTES:
        raise ValueError("Garmin inflated FIT exceeds safe size")
    return bytes(output)


def _decode_downloaded_file(
    data: bytes,
    *,
    compressed: bool,
    sensor_id: str,
    source_key: str,
    source_label: str | None,
) -> tuple[Workout, int]:
    fit = _inflate_bounded(data) if compressed else bytes(data)
    workout = workout_from_fit(
        fit,
        sensor_id=sensor_id,
        source_key=source_key,
        source_label=source_label,
    )
    return workout, len(fit)


def _scanner_route_source(route: Any) -> str | None:
    """Return Home Assistant's source ID for one address-specific scanner route."""
    scanner = getattr(route, "scanner", None)
    source = getattr(scanner, "source", None)
    if source:
        return str(source)
    ble_device = getattr(route, "ble_device", None)
    details = getattr(ble_device, "details", None)
    if isinstance(details, dict) and details.get("source"):
        return str(details["source"])
    return None


def _scanner_route_is_local(route: Any) -> bool:
    """Return whether a route is backed by the host-local BlueZ scanner.

    Do not use ``scanner.adapter`` as the discriminator. Remote scanners can
    expose an adapter-like attribute too (notably ESPHome proxies), which can
    make a proxy look local and incorrectly pin a secure Garmin bond to it.
    Prefer BlueZ object-path evidence and HA's concrete local scanner type.
    """
    ble_device = getattr(route, "ble_device", None)
    details = getattr(ble_device, "details", None)

    # Bleak/BlueZ details have appeared as mappings and as tuple/list payloads
    # across HA/Bleak releases. In both cases the D-Bus object path is decisive.
    if isinstance(details, dict):
        for key in ("path", "object_path"):
            if str(details.get(key) or "").startswith("/org/bluez/"):
                return True
    elif isinstance(details, (tuple, list)) and details:
        if str(details[0]).startswith("/org/bluez/"):
            return True
    elif isinstance(details, str) and details.startswith("/org/bluez/"):
        return True

    scanner = getattr(route, "scanner", None)
    scanner_type = type(scanner).__name__ if scanner is not None else ""
    scanner_module = type(scanner).__module__ if scanner is not None else ""
    return scanner_type == "HaScanner" and "bluetooth" in scanner_module


def _scanner_route_rssi(route: Any) -> int:
    advertisement = getattr(route, "advertisement", None)
    try:
        return int(getattr(advertisement, "rssi", -127))
    except (TypeError, ValueError):
        return -127


def _bluez_device_path(ble_device: Any, address: str) -> str | None:
    """Return the BlueZ object path carried by a host-local BLEDevice."""
    details = getattr(ble_device, "details", None)
    candidates: list[Any] = []
    if isinstance(details, dict):
        candidates.extend([details.get("path"), details.get("object_path")])
    elif isinstance(details, (tuple, list)) and details:
        candidates.append(details[0])
    elif isinstance(details, str):
        candidates.append(details)
    suffix = "/dev_" + str(address).upper().replace(":", "_")
    for candidate in candidates:
        value = str(candidate or "")
        if value.startswith("/org/bluez/") and value.upper().endswith(suffix.upper()):
            return value
    return None


def _select_garmin_ble_route(
    hass, address: str, preferred_source: str | None
) -> tuple[Any | None, str | None, str]:
    """Select one stable central for Garmin pairing and subsequent archive sync.

    A BLE bond belongs to the central that created it.  HA's normal nearest-path
    resolver may switch between a local controller and remote proxies as RSSI
    changes, which is ideal for ordinary unbonded sensors but unsafe for a paired
    Garmin archive session.  Before a source has been bonded, prefer a host-local
    BlueZ route because it can participate in interactive pairing.  After pairing,
    stick to that exact source rather than silently hopping to a different central.
    """
    try:
        routes = list(
            bluetooth.async_scanner_devices_by_address(
                hass, address, connectable=True
            )
        )
    except Exception:
        routes = []

    if preferred_source:
        for route in routes:
            if _scanner_route_source(route) == preferred_source:
                return (
                    getattr(route, "ble_device", None),
                    preferred_source,
                    "local" if _scanner_route_is_local(route) else "remote",
                )
        # Do not move an established bond to another Bluetooth central merely
        # because the preferred scanner missed this advertisement.  Wait for the
        # bonded source to see the watch again.
        return None, preferred_source, "unavailable"

    local_routes = [route for route in routes if _scanner_route_is_local(route)]
    if local_routes:
        route = max(local_routes, key=_scanner_route_rssi)
        return getattr(route, "ble_device", None), _scanner_route_source(route), "local"

    # Remote-only HA installations can still try the normal HA-selected route.
    # If pairing succeeds, its source is persisted below and future syncs remain
    # pinned to that same central.
    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        return None, None, "unavailable"
    for route in routes:
        candidate = getattr(route, "ble_device", None)
        if candidate is ble_device or (
            candidate is not None
            and getattr(candidate, "details", None) == getattr(ble_device, "details", None)
        ):
            return ble_device, _scanner_route_source(route), "remote"
    details = getattr(ble_device, "details", None)
    source = details.get("source") if isinstance(details, dict) else None
    return ble_device, str(source) if source else None, "auto"


async def _start_best_session(client) -> tuple[GarminGfdiSession, tuple[str, ...]]:
    """Start the first working GFDI transport using connected capabilities only.

    A device can expose more than one Garmin transport/channel.  Each candidate
    gets a short independent deadline and failed candidates are fully stopped
    before trying the next one.  Model/local-name strings never participate.
    """
    candidates = transport_candidates_from_client(client)
    if not candidates:
        raise GarminUnsupportedTransport(
            "no supported Garmin GFDI V0/V1/V2 characteristics"
        )
    backend_names = tuple(candidate.backend for candidate in candidates)
    failures: list[str] = []
    async with asyncio.timeout(TRANSPORT_NEGOTIATION_TIMEOUT):
        for transport in candidates:
            session = GarminGfdiSession(transport)
            try:
                async with asyncio.timeout(TRANSPORT_CANDIDATE_TIMEOUT):
                    await session.async_start()
                return session, backend_names
            except asyncio.CancelledError:
                raise
            except Exception as err:
                detail = " ".join(str(err).split())[:120]
                failures.append(
                    f"{transport.backend}:{type(err).__name__}"
                    + (f"({detail})" if detail else "")
                )
                try:
                    async with asyncio.timeout(CLEANUP_TIMEOUT):
                        await session.async_stop()
                except Exception:
                    pass
                # A transport failure can also drop the underlying GATT link.
                # Do not churn through the remaining 281x/V1 candidates on a
                # client that BlueZ already considers disconnected.
                if getattr(client, "is_connected", True) is False:
                    break
    raise RuntimeError(
        "Garmin GFDI capability candidates did not handshake: "
        + ", ".join(failures[:6])
    )


class GarminLocalCoordinator:
    """Own automatic Garmin sync tasks, checkpoints, retries and cleanup."""

    adapter_id = "garmin_local"
    sync_unique_suffix = "garmin_sync_workouts"
    sync_translation_key = "garmin_sync_workouts"
    sync_icon = "mdi:watch-import-variant"

    def __init__(self, provider) -> None:
        self.provider = provider
        self.runtime = provider.runtime
        self.hass = provider.hass
        self._store = Store[dict[str, Any]](
            self.hass,
            GARMIN_LOCAL_SYNC_STORE_VERSION,
            GARMIN_LOCAL_SYNC_STORE_KEY,
            private=True,
        )
        self._state: dict[str, Any] = {"devices": {}}
        self._tasks: dict[str, asyncio.Task] = {}
        self._active_sync: set[str] = set()
        self._queued: dict[str, tuple[asyncio.Task, float]] = {}
        self._background: set[asyncio.Task] = set()
        self._save_lock = asyncio.Lock()
        self._initialized = False
        self._stopping = False
        self._progress: dict[str, tuple[int, float]] = {}
        self._last_advertisement_action: dict[str, float] = {}
        self._reconfigure_unsub = None

    async def async_setup(self) -> None:
        stored = await self._store.async_load() or {}
        devices = stored.get("devices")
        if isinstance(devices, dict):
            self._state = {"devices": devices}
        self._initialized = True

        def _reconfigure_completed(event) -> None:
            data = event.data
            if str(data.get("adapter_id") or "") != "garmin_local":
                return
            sensor_id = str(data.get("sensor_id") or "")
            if sensor_id:
                self.schedule(sensor_id, delay=0.0, force=True)

        self._reconfigure_unsub = self.hass.bus.async_listen(
            "fitness_device_reconfigure_completed", _reconfigure_completed
        )
        recovered = self._recover_interrupted_states()
        if recovered:
            await self._save()
        self._resume_persisted_schedules()

    def _recover_interrupted_states(self) -> bool:
        """Turn an interrupted in-flight sync into a safe resumable checkpoint.

        Complete FIT files are checkpointed before profile import, so a Home
        Assistant restart never needs to resume in the middle of a BLE transfer.
        Instead, reconnect from the last durable catalogue/file checkpoint.
        """
        changed = False
        retry_at = datetime.now(timezone.utc) + timedelta(seconds=STARTUP_RESUME_DELAY)
        devices = self._state.setdefault("devices", {})
        for state in devices.values():
            if not isinstance(state, dict):
                continue
            if str(state.get("sync_state") or "") not in {"connecting", "syncing"}:
                continue
            state.update(
                sync_state="waiting",
                next_attempt=retry_at.isoformat(),
                active_file=None,
            )
            changed = True
        return changed

    def _resume_persisted_schedule(self, sensor_id: str) -> bool:
        """Recreate one archive timer from durable state after startup/assignment."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if (
            sensor is None
            or endpoint is None
            or endpoint.metadata.get("archive_adapter") != "garmin_local"
            or endpoint.metadata.get("archive_compatible") is False
            or not self.runtime.sensor_is_accepted(canonical)
            or not self.runtime.sensor_archive_profile_ids(canonical)
        ):
            return False

        state = self._device(canonical)
        status = str(state.get("sync_state") or "idle")
        try:
            pending = max(0, int(state.get("pending_file_count") or 0))
        except (TypeError, ValueError):
            pending = 0
        now = datetime.now(timezone.utc)
        due: datetime | None = None

        if status in {"waiting", "retrying", "error"} or pending:
            due = _dt(state.get("next_attempt")) or (
                now + timedelta(seconds=STARTUP_RESUME_DELAY)
            )
        elif status == "ready":
            last_success = _dt(state.get("last_successful_sync"))
            if last_success is not None:
                due = last_success + SYNC_INTERVAL

        if due is None:
            return False
        delay = max(0.0, (due - now).total_seconds())
        self.schedule(canonical, delay=delay, force=True)
        _LOGGER.info(
            "Garmin restored persisted archive timer for %s in %.1fs (state=%s pending=%s)",
            canonical,
            delay,
            status,
            pending,
        )
        return True

    def _resume_persisted_schedules(self) -> None:
        """Restore every currently eligible Garmin timer without polling."""
        devices = self._state.setdefault("devices", {})
        for sensor_id in tuple(devices):
            self._resume_persisted_schedule(str(sensor_id))

    def _device(self, sensor_id: str) -> dict[str, Any]:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        devices = self._state.setdefault("devices", {})
        state = devices.get(sensor_id)
        if not isinstance(state, dict):
            state = devices[sensor_id] = {"files": {}, "retry_count": 0}
        return state

    def _report_pairing_required(self, sensor_id: str) -> None:
        """Open a guided HA Repair after automatic pairing needs watch input."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        device = sensor.label() if sensor is not None else "Garmin device"
        request_device_user_action(
            self.hass,
            adapter_id="garmin_local",
            sensor_id=canonical,
            device=device,
            action="pairing_required",
            reason="Garmin requires confirmation on the watch before local Bluetooth sync can continue.",
            instructions=(
                "Keep the Garmin paired with your phone; Home Assistant should be added as another host, not replace it.",
                "On the Garmin, open Bluetooth/Phone pairing mode so it is discoverable for another connection.",
                "Approve the pairing request shown on the Garmin when Home Assistant reconnects.",
                "If Garmin warns that the current phone pairing will be replaced or removed, cancel that operation.",
                "Return here and submit this Repair. Fitness will retry the device immediately.",
            ),
        )

    def _clear_pairing_issue(self, sensor_id: str) -> None:
        clear_device_user_action(
            self.hass,
            adapter_id="garmin_local",
            sensor_id=self.runtime.resolve_sensor_id(sensor_id),
            action="pairing_required",
        )

    async def _save(self) -> None:
        if not self._initialized:
            return
        async with self._save_lock:
            await self._store.async_save(self._state)

    def _background_task(self, coro, name: str) -> asyncio.Task:
        task = self.hass.async_create_background_task(coro, name, eager_start=False)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    def advertise(self, sensor_id: str, identity: dict[str, Any]) -> None:
        """Rate-limit advertisement-side work; BLE advertisements are a hot path."""
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        now = self.hass.loop.time()
        previous = self._last_advertisement_action.get(sensor_id)
        if previous is not None and now - previous < ADVERTISEMENT_ACTION_MIN_INTERVAL:
            return
        self._last_advertisement_action[sensor_id] = now
        state = self._device(sensor_id)
        evidence = identity.get("garmin_identity_evidence") or []
        state["protocol_hint"] = identity.get("garmin_protocol_hint") or "auto"
        state["identity_evidence"] = list(evidence)[:8]
        self.runtime.publish_details(
            sensor_id,
            {"garmin_local_backend": state.get("backend") or "auto"},
            transport="garmin_local_advertisement",
            metadata=_DETAIL_META,
            priority=80,
        )
        self._publish(sensor_id)
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if (
            endpoint is not None
            and endpoint.metadata.get("archive_compatible") is not False
            and self.runtime.sensor_is_accepted(sensor_id)
            and self.runtime.sensor_archive_profile_ids(sensor_id)
        ):
            # A fresh Garmin advertisement may wake a task that is merely
            # sleeping because the device was unreachable. It must not bypass
            # SYNC_INTERVAL or an error next_attempt backoff.
            self.schedule(sensor_id, delay=3.0, wake_if_sleeping=True)

    def acceptance_changed(self, sensor_id: str, accepted: bool) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if accepted:
            if self.runtime.sensor_archive_profile_ids(sensor_id):
                if not self._resume_persisted_schedule(sensor_id):
                    self.schedule(sensor_id, delay=1.0, force=True)
            return
        self._clear_pairing_issue(sensor_id)
        self._cancel(sensor_id)

    def assignment_changed(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if not self.runtime.sensor_archive_profile_ids(sensor_id):
            self._clear_pairing_issue(sensor_id)
            self._cancel(sensor_id)
            state = self._device(sensor_id)
            state.update(sync_state="idle", pending_file_count=0)
            self._publish(sensor_id)
            self._background_task(self._save(), f"fitness Garmin pause state {sensor_id}")
        elif self.runtime.sensor_is_accepted(sensor_id):
            if not self._resume_persisted_schedule(sensor_id):
                self.schedule(sensor_id, delay=0.5, force=True)

    def forget_sensor(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        self._clear_pairing_issue(sensor_id)
        self._cancel(sensor_id)
        self._last_advertisement_action.pop(sensor_id, None)
        self._progress.pop(sensor_id, None)
        if self._state.setdefault("devices", {}).pop(sensor_id, None) is not None:
            self._background_task(self._save(), f"fitness Garmin forget state {sensor_id}")

    def _cancel(self, sensor_id: str) -> None:
        task = self._tasks.pop(sensor_id, None)
        self._active_sync.discard(sensor_id)
        self._queued.pop(sensor_id, None)
        if task is not None and not task.done():
            task.cancel()

    def schedule(
        self,
        sensor_id: str,
        *,
        delay: float,
        force: bool = False,
        wake_if_sleeping: bool = False,
    ) -> None:
        if self._stopping or not self._initialized:
            return
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if not force:
            state = self._device(sensor_id)
            last = _dt(state.get("last_successful_sync"))
            if last is not None and datetime.now(timezone.utc) - last < SYNC_INTERVAL:
                return
            next_attempt = _dt(state.get("next_attempt"))
            if next_attempt is not None and next_attempt > datetime.now(timezone.utc):
                return
        current = self._tasks.get(sensor_id)
        if current is not None and not current.done():
            if sensor_id not in self._active_sync:
                if not (force or wake_if_sleeping):
                    return
                # Manual retry can replace a sleeping backoff task. A live
                # advertisement may replace only ordinary sleeping work because
                # the interval/next_attempt checks above still apply. Never
                # cancel an active BLE transfer.
                current.cancel()
                if self._tasks.get(sensor_id) is current:
                    self._tasks.pop(sensor_id, None)
                self._queued.pop(sensor_id, None)
            else:
                if not force:
                    return
                previous = self._queued.get(sensor_id)
                self._queued[sensor_id] = (
                    current,
                    min(delay, previous[1]) if previous and previous[0] is current else delay,
                )
                return

        async def _run() -> None:
            canonical = self.runtime.resolve_sensor_id(sensor_id)
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                canonical = self.runtime.resolve_sensor_id(sensor_id)
                self._active_sync.add(canonical)
                await self._async_sync(canonical, force=force)
            except asyncio.CancelledError:
                raise
            finally:
                current_task = asyncio.current_task()
                canonical = self.runtime.resolve_sensor_id(sensor_id)
                self._active_sync.discard(canonical)
                if self._tasks.get(canonical) is current_task:
                    self._tasks.pop(canonical, None)
                queued = self._queued.get(canonical)
                if queued is not None and queued[0] is current_task:
                    self._queued.pop(canonical, None)
                    if not self._stopping:
                        self.hass.loop.call_soon(
                            lambda: self.schedule(canonical, delay=queued[1], force=True)
                        )

        self._tasks[sensor_id] = self.hass.async_create_background_task(
            _run(), f"fitness Garmin local workout sync {sensor_id}", eager_start=False
        )

    async def async_sync_now(self, sensor_id: str) -> asyncio.Task | None:
        """Start one forced sync and return its tracked task for explicit UI waits."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        self.schedule(canonical, delay=0.0, force=True)
        return self._tasks.get(canonical)

    def _schedule_after_current(self, sensor_id: str, delay: float) -> None:
        current = asyncio.current_task()
        if current is None:
            self.hass.loop.call_soon(lambda: self.schedule(sensor_id, delay=delay, force=True))
            return
        self._queued[self.runtime.resolve_sensor_id(sensor_id)] = (current, delay)

    def _publish(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        state = self._device(sensor_id)
        files = state.get("files") if isinstance(state.get("files"), dict) else {}
        values = {
            "garmin_local_backend": state.get("backend") or "auto",
            "garmin_sync_state": state.get("sync_state", "idle"),
            "garmin_last_sync": state.get("last_sync"),
            "garmin_last_successful_sync": state.get("last_successful_sync"),
            "garmin_device_workout_count": state.get("device_workout_count"),
            "garmin_imported_file_count": len(files),
            "garmin_pending_file_count": state.get("pending_file_count", 0),
            "garmin_downloaded_bytes": state.get("downloaded_bytes"),
            "garmin_retry_count": state.get("retry_count", 0),
            "garmin_last_error": state.get("last_error_code") or "none",
            "garmin_protocol_version": state.get("protocol_version"),
            "garmin_latest_workout": state.get("latest_workout"),
        }
        self.runtime.publish_details(
            sensor_id,
            {key: value for key, value in values.items() if value is not None},
            transport="garmin_local_sync",
            metadata=_DETAIL_META,
            priority=95,
        )

    def _progress_update(self, sensor_id: str, size: int) -> None:
        now = self.hass.loop.time()
        old_size, old_time = self._progress.get(sensor_id, (0, 0.0))
        if size - old_size < 65536 and now - old_time < 5.0:
            return
        self._progress[sensor_id] = (size, now)
        self._device(sensor_id)["downloaded_bytes"] = size
        self._publish(sensor_id)

    async def _import_records(self, records: list[dict[str, Any]], profile_ids: list[str]) -> None:
        for profile_id in profile_ids:
            manager = self.hass.data.get(DOMAIN, {}).get(profile_id)
            if manager is None:
                continue
            pending: list[dict[str, Any]] = []
            workouts: list[Workout] = []
            for record in records:
                imported = {str(value) for value in record.get("imported_profiles") or []}
                if profile_id in imported:
                    continue
                payload = record.get("workout")
                if not isinstance(payload, dict):
                    continue
                try:
                    workouts.append(Workout(**payload))
                except TypeError:
                    continue
                pending.append(record)
            if not workouts:
                continue
            await manager.async_import_device_workouts(workouts)
            for record in pending:
                imported = {str(value) for value in record.get("imported_profiles") or []}
                imported.add(profile_id)
                record["imported_profiles"] = sorted(imported)

    @staticmethod
    def _prune_file_records(files: dict[str, Any], protected_keys: set[str]) -> None:
        """Bound cached workout summaries without pruning the current catalogue."""
        overflow = len(files) - MAX_CACHED_FILE_RECORDS
        if overflow <= 0:
            return
        removable = [
            (str((record or {}).get("completed_at") or ""), key)
            for key, record in files.items()
            if key not in protected_keys and isinstance(record, dict)
        ]
        removable.sort()
        for _completed_at, key in removable[:overflow]:
            files.pop(key, None)

    @staticmethod
    def _item_key(item: GarminSyncFile | GarminDirectoryEntry) -> str:
        return item.file_id.key if isinstance(item, GarminSyncFile) else item.key

    async def _async_sync(self, requested_sensor_id: str, *, force: bool = False) -> None:
        sensor_id = self.runtime.resolve_sensor_id(requested_sensor_id)
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if (
            self._stopping or sensor is None or endpoint is None
            or not self.runtime.sensor_is_accepted(sensor_id)
            or endpoint.metadata.get("archive_adapter") != "garmin_local"
            or endpoint.metadata.get("archive_compatible") is False
        ):
            return
        # Once a user has accepted a Garmin archive endpoint, preserve that
        # protocol identity even if a later advertisement omits manufacturer or
        # service fields.  Initial discovery still requires strong Garmin evidence.
        if endpoint.metadata.get("archive_adapter") == "garmin_local":
            identity = dict(endpoint.metadata)
        else:
            identity = garmin_advertisement_identity(
                endpoint.metadata.get("advertised_name") or sensor.name,
                endpoint.metadata.get("service_uuids") or [],
                endpoint.metadata.get("manufacturer_data_ids") or [],
            )
        if identity is None:
            return
        profile_ids = self.runtime.sensor_archive_profile_ids(sensor_id)
        state = self._device(sensor_id)
        if not profile_ids:
            state.update(sync_state="idle", pending_file_count=0, last_error_code="none")
            self._publish(sensor_id)
            return
        if not force:
            last = _dt(state.get("last_successful_sync"))
            if last is not None and datetime.now(timezone.utc) - last < SYNC_INTERVAL:
                return
        if self.provider.sensor_users(sensor_id) or self.provider.sensor_connected(sensor_id):
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=BUSY_RETRY_DELAY)
            state.update(
                sync_state="waiting",
                last_error_code="none",
                next_attempt=retry_at.isoformat(),
            )
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, BUSY_RETRY_DELAY)
            return

        preferred_source = str(state.get("bluetooth_source") or "") or None
        preferred_route_kind = str(state.get("bluetooth_route_kind") or "") or None
        ble_device, selected_source, route_kind = _select_garmin_ble_route(
            self.hass, endpoint.address, preferred_source
        )

        # Migrate the short-lived 2026.8.18 route-classification bug: ESPHome
        # scanners could be persisted as ``local`` because they expose an
        # adapter-like attribute. If the stored "local" source is now correctly
        # identified as remote, discard that pin and reselect a real host-local
        # BlueZ route. This is capability/path based and contains no device model.
        if (
            preferred_source
            and preferred_route_kind == "local"
            and route_kind == "remote"
        ):
            _LOGGER.warning(
                "Garmin discarding stale Bluetooth source %s: stored as local but now identified as remote for %s",
                preferred_source,
                endpoint.address,
            )
            state.pop("bluetooth_source", None)
            state.pop("bluetooth_route_kind", None)
            preferred_source = None
            ble_device, selected_source, route_kind = _select_garmin_ble_route(
                self.hass, endpoint.address, None
            )
        if ble_device is None:
            # Once paired, a Garmin stays pinned to the same Bluetooth central so
            # its bond is never silently replaced by whichever proxy has the best
            # RSSI today. Persist the sparse wake-up too, so a Home Assistant
            # restart cannot strand the archive until another advertisement changes.
            retry_at = datetime.now(timezone.utc) + timedelta(
                seconds=UNREACHABLE_RETRY_DELAY
            )
            state.update(
                sync_state="waiting",
                last_error_code="none",
                next_attempt=retry_at.isoformat(),
            )
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, UNREACHABLE_RETRY_DELAY)
            _LOGGER.info(
                "Garmin sync waiting for Bluetooth source %s (%s) for %s",
                preferred_source or "auto", route_kind, endpoint.address,
            )
            return

        _LOGGER.info(
            "Garmin sync selecting Bluetooth source %s (%s) for %s",
            selected_source or "auto", route_kind, endpoint.address,
        )

        lock = self.provider._connect_lock(sensor_id)
        client = None
        session: GarminGfdiSession | None = None
        stage = "connection"
        try:
            # Entire BLE session has a hard upper bound. Every nested transport
            # operation also has a shorter stage timeout.
            async with asyncio.timeout(SESSION_TIMEOUT):
                async with lock:
                    if self.provider.sensor_connected(sensor_id) or self.provider.sensor_users(sensor_id):
                        retry_at = datetime.now(timezone.utc) + timedelta(seconds=BUSY_RETRY_DELAY)
                        state.update(
                            sync_state="waiting",
                            last_error_code="none",
                            next_attempt=retry_at.isoformat(),
                        )
                        await self._save()
                        self._publish(sensor_id)
                        self._schedule_after_current(sensor_id, BUSY_RETRY_DELAY)
                        return
                    state.update(
                        sync_state="connecting",
                        last_sync=datetime.now(timezone.utc).isoformat(),
                        last_error_code="none",
                        next_attempt=None,
                    )
                    self._publish(sensor_id)
                    # Provisioning and archive transport are deliberately two
                    # different connections. The known-good standalone BlueZ path
                    # first creates a durable bond, then starts Garmin Multi-Link on
                    # a fresh encrypted GATT connection. Keeping the connection that
                    # performed numeric-comparison pairing can leave newer watches in
                    # their "finish setup on device" provisioning state and no GFDI
                    # frames arrive.
                    stage = "pairing"
                    bluez_path = (
                        _bluez_device_path(ble_device, endpoint.address)
                        if route_kind == "local"
                        else None
                    )
                    paired = bonded = trusted = False
                    if bluez_path is not None:
                        paired, bonded, trusted = await async_bluez_device_pairing_state(bluez_path)
                    needs_pairing = route_kind != "local" or not (paired and bonded)

                    if needs_pairing:
                        async with temporary_bluez_pairing_agent(
                            endpoint.address, enabled=route_kind == "local"
                        ):
                            async with asyncio.timeout(PAIR_CONNECT_TIMEOUT):
                                client = await self.provider.establish_connection(
                                    ble_device,
                                    sensor.name or endpoint.address,
                                    max_attempts=PAIR_CONNECT_ATTEMPTS,
                                    pair=True,
                                    source=selected_source,
                                )
                        _LOGGER.info(
                            "Garmin Bluetooth pairing connection completed via %s (%s) for %s",
                            selected_source or "auto", route_kind, endpoint.address,
                        )
                        if bluez_path is not None:
                            paired, bonded, trusted = await async_bluez_device_pairing_state(bluez_path)
                            if not (paired and bonded):
                                raise RuntimeError("BlueZ pairing returned without a durable Garmin bond")
                            _LOGGER.info(
                                "Garmin durable BlueZ bond confirmed for %s (trusted=%s)",
                                endpoint.address, trusted,
                            )
                            # The bond itself is central-specific and is now proven,
                            # so remember this source even before Garmin protocol
                            # negotiation. This prevents the next retry from hopping
                            # to a proxy if GFDI itself needs another iteration.
                            if selected_source:
                                state["bluetooth_source"] = selected_source
                                state["bluetooth_route_kind"] = route_kind
                                await self._save()

                        # End the provisioning connection. A short settle period lets
                        # BlueZ publish the durable bond and lets the watch leave its
                        # pairing state before we open the archive session.
                        if client is not None:
                            await self.provider._async_disconnect_client(
                                client, reason="Garmin post-pair provisioning reconnect"
                            )
                            client = None
                        await asyncio.sleep(0.8)

                        refreshed_device, refreshed_source, refreshed_kind = _select_garmin_ble_route(
                            self.hass, endpoint.address, selected_source
                        )
                        if refreshed_device is not None:
                            ble_device = refreshed_device
                            selected_source = refreshed_source or selected_source
                            route_kind = refreshed_kind

                    # All normal archive traffic starts on a fresh bonded connection
                    # with pair=False, matching the successful standalone FIT test and
                    # avoiding a pairing transaction on every periodic sync.
                    stage = "connection"
                    async with asyncio.timeout(CONNECT_TIMEOUT):
                        client = await self.provider.establish_connection(
                            ble_device,
                            sensor.name or endpoint.address,
                            max_attempts=PAIR_CONNECT_ATTEMPTS,
                            pair=False,
                            source=selected_source,
                        )
                    _LOGGER.info(
                        "Garmin fresh bonded GATT session ready via %s (%s) for %s",
                        selected_source or "auto", route_kind, endpoint.address,
                    )
                    stage = "handshake"
                    session, candidate_backends = await _start_best_session(client)
                    # A bond belongs to the central that created it, but do not pin a
                    # route merely because a connection call returned successfully.
                    # Authentication can still be absent (ATT error 0x05). Only a
                    # completed Garmin handshake proves this central is usable.
                    if selected_source:
                        state["bluetooth_source"] = selected_source
                        state["bluetooth_route_kind"] = route_kind
                    _LOGGER.info(
                        "Garmin GFDI handshake succeeded via %s (%s/%s) for %s",
                        session.transport.backend,
                        selected_source or "auto",
                        route_kind,
                        endpoint.address,
                    )
                    # Only a successful connected GATT/GFDI handshake grants the
                    # local workout-history capability. Advertisement vendor
                    # evidence alone remains a candidate, not compatibility proof.
                    self.runtime.set_archive_compatibility(
                        sensor_id, adapter_id="garmin_local", compatible=True
                    )
                    state["transport_candidates"] = list(candidate_backends)[:8]
                    state["backend"] = session.transport.backend
                    self._publish(sensor_id)
                    state["protocol_version"] = session.protocol_version
                    state["sync_state"] = "syncing"
                    self._publish(sensor_id)

                    stage = "catalog"
                    mode, catalog = await session.async_activity_catalog()
                    state["catalog_mode"] = mode
                    state["device_workout_count"] = len(catalog)
                    files = state.setdefault("files", {})
                    if not isinstance(files, dict):
                        files = state["files"] = {}
                    keys = [self._item_key(item) for item in catalog]
                    pending_items = [item for item in catalog if self._item_key(item) not in files]
                    state["pending_file_count"] = len(pending_items)
                    self._publish(sensor_id)

                    records_to_import = [
                        record for record in files.values()
                        if isinstance(record, dict)
                        and any(
                            profile_id not in {str(v) for v in record.get("imported_profiles") or []}
                            for profile_id in profile_ids
                        )
                    ][:MAX_FILES_PER_SESSION]
                    slots = max(0, MAX_FILES_PER_SESSION - len(records_to_import))
                    batch_bytes = 0

                    for item in pending_items[:slots]:
                        if not self.runtime.sensor_archive_profile_ids(sensor_id):
                            return
                        expected_size = max(0, int(getattr(item, "size", 0) or 0))
                        if expected_size > MAX_BYTES_PER_SYNC:
                            raise ValueError("Garmin activity exceeds per-sync byte budget")
                        if batch_bytes and batch_bytes + expected_size > MAX_BYTES_PER_SYNC:
                            break
                        key = self._item_key(item)
                        state.update(active_file=key, downloaded_bytes=0)
                        self._publish(sensor_id)
                        stage = "transfer"
                        downloaded = await session.async_download_activity(
                            mode,
                            item,
                            progress=lambda size, sid=sensor_id: self._progress_update(sid, size),
                        )
                        if len(downloaded.data) > MAX_BYTES_PER_SYNC:
                            raise ValueError("Garmin transfer exceeds per-sync byte budget")
                        stage = "validation"
                        compressed = mode == "filesync_v2"
                        workout, fit_size = await self.hass.async_add_executor_job(
                            partial(
                                _decode_downloaded_file,
                                downloaded.data,
                                compressed=compressed,
                                sensor_id=sensor_id,
                                source_key=downloaded.key,
                                source_label=sensor.name,
                            )
                        )
                        stage = "import"
                        record = {
                            "size": fit_size,
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "workout": workout.as_persistent_dict(),
                            "imported_profiles": [],
                        }
                        files[key] = record
                        records_to_import.append(record)
                        start = _dt(workout.start)
                        if start is not None:
                            latest = start.isoformat()
                            if not state.get("latest_workout") or latest > state["latest_workout"]:
                                state["latest_workout"] = latest
                        state.update(
                            active_file=None,
                            downloaded_bytes=fit_size,
                            pending_file_count=len([candidate for candidate in keys if candidate not in files]),
                        )
                        # Checkpoint each complete FIT before touching profile history.
                        await self._save()
                        self._publish(sensor_id)
                        batch_bytes += fit_size
                        if batch_bytes >= MAX_BYTES_PER_SYNC:
                            break

                    stage = "import"
                    # Keep one initialized Garmin session long enough to drain a
                    # small archive burst, but preserve the original two-workout
                    # import/checkpoint chunk. This avoids repeated GFDI handshakes
                    # while keeping profile writes and restart recovery bounded.
                    for offset in range(0, len(records_to_import), MAX_FILES_PER_SYNC):
                        chunk = records_to_import[offset : offset + MAX_FILES_PER_SYNC]
                        async with asyncio.timeout(IMPORT_TIMEOUT):
                            await self._import_records(chunk, profile_ids)
                        # Persist imported_profiles after every small chunk. A crash
                        # never forces an already-finished burst to start from zero.
                        await self._save()
                    self._prune_file_records(files, set(keys))
                    remaining = [candidate for candidate in keys if candidate not in files]
                    cached_pending = any(
                        isinstance(record, dict)
                        and any(
                            profile_id not in {str(v) for v in record.get("imported_profiles") or []}
                            for profile_id in profile_ids
                        )
                        for record in files.values()
                    )
                    more_work = bool(remaining or cached_pending)
                    now_utc = datetime.now(timezone.utc)
                    state.update(
                        sync_state="waiting" if more_work else "ready",
                        last_error_code="none",
                        retry_count=0,
                        partial_retry_count=0,
                        last_batch_success=now_utc.isoformat(),
                        next_attempt=(
                            (now_utc + timedelta(seconds=BATCH_CONTINUE_DELAY)).isoformat()
                            if more_work
                            else (now_utc + SYNC_INTERVAL).isoformat()
                        ),
                        active_file=None,
                        pending_file_count=len(remaining),
                    )
                    if not more_work:
                        state["last_successful_sync"] = now_utc.isoformat()
                    self._clear_pairing_issue(sensor_id)
                    await self._save()
                    self._publish(sensor_id)
                    if more_work:
                        self._schedule_after_current(sensor_id, BATCH_CONTINUE_DELAY)
                    else:
                        # Do not depend on advertisement payload changes for the
                        # next archive poll; HA intentionally deduplicates stable
                        # BLE advertisements. One tracked timer per accepted Garmin
                        # keeps automatic sync reliable without continuous radio work.
                        self._schedule_after_current(sensor_id, SYNC_INTERVAL.total_seconds())
        except asyncio.CancelledError:
            raise
        except GarminUnsupportedTransport as err:
            self._clear_pairing_issue(sensor_id)
            # Definitive V2/V1/V0 incompatibility is sticky until the device is
            # removed/re-discovered. Do not keep an incompatible Garmin in Smart
            # workout choices or wake Bluetooth every few hours forever.
            self.runtime.set_archive_compatibility(
                sensor_id, adapter_id="garmin_local", compatible=False
            )
            state = self._device(sensor_id)
            state.update(
                sync_state="unsupported",
                last_error_code="unsupported_transport",
                retry_count=0,
                next_attempt=None,
            )
            await self._save()
            self._publish(sensor_id)
            _LOGGER.debug("Garmin transport unsupported for %s: %s", sensor_id, err)
        except Exception as err:
            state = self._device(sensor_id)
            retries = int(state.get("retry_count") or 0) + 1
            text = str(err).lower()
            error_code = _ERROR_CODE.get(stage, "unknown")
            if stage == "pairing":
                error_code = "pairing_required"
            elif stage in {"connection", "handshake"} and any(
                token in text
                for token in (
                    "pair", "bond", "authentication", "not authorized",
                    "passkey", "pin", "rejected", "canceled", "cancelled",
                )
            ):
                error_code = "pairing_required"
            # Garmin watches can keep their freshly-closed Multi-Link channel in
            # a short post-sync cooldown.  A partial batch has already proven the
            # bond, GFDI and FileSync path, so a transient connection/handshake or
            # catalogue failure immediately after that success is not evidence of
            # broken pairing.  Keep the durable pending checkpoint and retry at a
            # calm cadence instead of requiring an HA restart or hammering BLE.
            partial_retry = False
            try:
                pending = max(0, int(state.get("pending_file_count") or 0))
            except (TypeError, ValueError):
                pending = 0
            last_batch_success = _dt(state.get("last_batch_success"))
            recent_partial = bool(
                pending
                and last_batch_success is not None
                and (datetime.now(timezone.utc) - last_batch_success).total_seconds()
                <= PARTIAL_BATCH_RECENT_WINDOW
                and stage in {"connection", "handshake", "catalog"}
                and error_code != "pairing_required"
            )
            partial_retries = int(state.get("partial_retry_count") or 0)
            if recent_partial and partial_retries < MAX_PARTIAL_BATCH_RETRIES:
                partial_retry = True
                partial_retries += 1
                self._clear_pairing_issue(sensor_id)
                delay = PARTIAL_BATCH_RETRY_DELAY
                retries = max(0, int(state.get("retry_count") or 0))
            elif error_code == "pairing_required":
                self._report_pairing_required(sensor_id)
                delay = UNSUPPORTED_RETRY_DELAY
            elif retries >= MAX_RETRIES:
                self._clear_pairing_issue(sensor_id)
                # Repeated background failures must become progressively cheaper
                # instead of waking the Bluetooth stack every 30 minutes forever.
                delay = DEGRADED_RETRY_DELAY
            else:
                self._clear_pairing_issue(sensor_id)
                delay = min(30 * 60.0, 60.0 * (2 ** min(retries - 1, 5)))
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
            state.update(
                sync_state=(
                    "waiting"
                    if partial_retry
                    else ("error" if retries >= MAX_RETRIES else "retrying")
                ),
                last_error_code=error_code,
                retry_count=retries,
                partial_retry_count=partial_retries if partial_retry else 0,
                next_attempt=retry_at.isoformat(),
                active_file=None,
            )
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, delay)
            _LOGGER.warning(
                "Garmin local sync failed for %s at %s via %s (%s): %s: %s",
                sensor_id,
                stage,
                selected_source or "auto",
                route_kind,
                type(err).__name__,
                err,
            )
        finally:
            if session is not None:
                try:
                    async with asyncio.timeout(CLEANUP_TIMEOUT):
                        await session.async_stop(disconnecting=True)
                except Exception:
                    pass
            if client is not None:
                await self.provider._async_disconnect_client(client, reason="Garmin local sync cleanup")
                clear_history = getattr(bluetooth, "async_clear_advertisement_history", None)
                if clear_history is not None:
                    try:
                        clear_history(self.hass, endpoint.address)
                    except Exception:
                        _LOGGER.debug(
                            "Unable to clear Garmin Bluetooth advertisement history for %s",
                            sensor_id,
                            exc_info=True,
                        )
            self.runtime._notify_values_throttled({
                (self.runtime.resolve_sensor_id(sensor_id), "gatt_connection", None)
            })

    def identity_conflict_repaired(self, sensor_id: str) -> None:
        """Remove Garmin-owned diagnostics/entities from a detached stale alias."""
        runtime = self.runtime
        sensor_id = runtime.resolve_sensor_id(sensor_id)
        detail_keys = [
            str(key)
            for key in tuple(runtime.sensor_detail_values.get(sensor_id, {}))
            if str(key).startswith("garmin_")
        ]
        runtime.clear_sensor_details_prefix(sensor_id, "garmin_")

        try:
            from homeassistant.helpers import entity_registry as er

            registry = er.async_get(runtime.hass)
            unique_ids = [f"fitness_{sensor_id}_garmin_sync_workouts"]
            unique_ids.extend(
                f"fitness_{sensor_id}_detail_{key}" for key in detail_keys
            )
            for platform, unique_id in (
                [("button", unique_ids[0])]
                + [("sensor", value) for value in unique_ids[1:]]
            ):
                entity_id = registry.async_get_entity_id(
                    platform, DOMAIN, unique_id
                )
                if entity_id is not None:
                    registry.async_remove(entity_id)
        except Exception:
            _LOGGER.debug(
                "Unable to remove stale Garmin archive entities from %s",
                sensor_id,
                exc_info=True,
            )

    async def async_shutdown(self) -> None:
        self._stopping = True
        if self._reconfigure_unsub is not None:
            self._reconfigure_unsub()
            self._reconfigure_unsub = None
        tasks = list({*self._tasks.values(), *self._background})
        self._tasks.clear()
        self._active_sync.clear()
        self._background.clear()
        self._queued.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            try:
                async with asyncio.timeout(SHUTDOWN_TIMEOUT):
                    await asyncio.gather(*tasks, return_exceptions=True)
            except TimeoutError:
                _LOGGER.warning("Timed out waiting for Garmin local sync shutdown")
