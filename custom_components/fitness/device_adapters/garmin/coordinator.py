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
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from ...const import (
    CAPABILITY_WORKOUT_HISTORY,
    DOMAIN,
    GARMIN_LOCAL_SYNC_STORE_KEY,
    GARMIN_LOCAL_SYNC_STORE_VERSION,
)
from ...providers.workouts import Workout, _dt
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
MAX_BYTES_PER_SYNC = 16 * 1024 * 1024
MAX_CACHED_FILE_RECORDS = 2_000
BATCH_CONTINUE_DELAY = 120.0
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
                failures.append(f"{transport.backend}:{type(err).__name__}")
                try:
                    async with asyncio.timeout(CLEANUP_TIMEOUT):
                        await session.async_stop()
                except Exception:
                    pass
    raise RuntimeError(
        "Garmin GFDI capability candidates did not handshake: "
        + ", ".join(failures[:6])
    )


class GarminLocalCoordinator:
    """Own automatic Garmin sync tasks, checkpoints, retries and cleanup."""

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

    async def async_setup(self) -> None:
        stored = await self._store.async_load() or {}
        devices = stored.get("devices")
        if isinstance(devices, dict):
            self._state = {"devices": devices}
        self._initialized = True

    def _device(self, sensor_id: str) -> dict[str, Any]:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        devices = self._state.setdefault("devices", {})
        state = devices.get(sensor_id)
        if not isinstance(state, dict):
            state = devices[sensor_id] = {"files": {}, "retry_count": 0}
        return state

    def _pairing_issue_id(self, sensor_id: str) -> str:
        """Return a stable opaque Repairs id across physical-device merges."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        identity = str(getattr(endpoint, "address", None) or canonical)
        digest = hashlib.sha256(identity.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"garmin_pairing_required_{digest}"

    def _report_pairing_required(self, sensor_id: str) -> None:
        """Ask for device-side interaction only after automatic pairing failed."""
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        device = sensor.label() if sensor is not None else "Garmin device"
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._pairing_issue_id(canonical),
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="garmin_pairing_required",
            translation_placeholders={"device": device},
        )

    def _clear_pairing_issue(self, sensor_id: str) -> None:
        ir.async_delete_issue(
            self.hass, DOMAIN, self._pairing_issue_id(sensor_id)
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
        if (
            self.runtime.sensor_is_accepted(sensor_id)
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

    async def async_sync_now(self, sensor_id: str) -> None:
        self.schedule(sensor_id, delay=0.0, force=True)

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
            or CAPABILITY_WORKOUT_HISTORY not in sensor.capabilities
            or not self.runtime.sensor_is_accepted(sensor_id)
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
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, BUSY_RETRY_DELAY)
            return

        ble_device = bluetooth.async_ble_device_from_address(self.hass, endpoint.address, connectable=True)
        if ble_device is None:
            # Do not spin every 90 seconds when the watch has left the house or
            # only a non-connectable route can see it. Keep one sparse wake-up; a
            # fresh matching advertisement can safely replace the sleeping task.
            state.update(sync_state="waiting", last_error_code="none", next_attempt=None)
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, UNREACHABLE_RETRY_DELAY)
            return

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
                    # Pairing is requested on every Garmin archive connection.
                    # Bleak/BlueZ treats this as a no-op when a bond already exists,
                    # while a new watch gets a one-time automatic Pair request before
                    # service discovery. One attempt prevents repeated pairing prompts;
                    # the whole operation remains inside the hard session deadline.
                    async with asyncio.timeout(PAIR_CONNECT_TIMEOUT):
                        client = await self.provider.establish_connection(
                            ble_device,
                            sensor.name or endpoint.address,
                            max_attempts=PAIR_CONNECT_ATTEMPTS,
                            pair=True,
                        )
                    stage = "handshake"
                    session, candidate_backends = await _start_best_session(client)
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
                    ][:MAX_FILES_PER_SYNC]
                    slots = max(0, MAX_FILES_PER_SYNC - len(records_to_import))
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
                    async with asyncio.timeout(IMPORT_TIMEOUT):
                        await self._import_records(records_to_import, profile_ids)
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
                        next_attempt=(
                            (now_utc + timedelta(seconds=BATCH_CONTINUE_DELAY)).isoformat()
                            if more_work
                            else None
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
            state = self._device(sensor_id)
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=UNSUPPORTED_RETRY_DELAY)
            state.update(
                sync_state="unsupported",
                last_error_code="unsupported_transport",
                retry_count=0,
                next_attempt=retry_at.isoformat(),
            )
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, UNSUPPORTED_RETRY_DELAY)
            _LOGGER.debug("Garmin transport unsupported for %s: %s", sensor_id, err)
        except Exception as err:
            state = self._device(sensor_id)
            retries = int(state.get("retry_count") or 0) + 1
            text = str(err).lower()
            error_code = _ERROR_CODE.get(stage, "unknown")
            if stage in {"connection", "handshake"} and any(
                token in text
                for token in (
                    "pair", "bond", "authentication", "not authorized",
                    "passkey", "pin", "rejected", "canceled", "cancelled",
                )
            ):
                error_code = "pairing_required"
            if error_code == "pairing_required":
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
                sync_state="error" if retries >= MAX_RETRIES else "retrying",
                last_error_code=error_code,
                retry_count=retries,
                next_attempt=retry_at.isoformat(),
                active_file=None,
            )
            await self._save()
            self._publish(sensor_id)
            self._schedule_after_current(sensor_id, delay)
            _LOGGER.debug("Garmin local sync failed for %s at %s: %s", sensor_id, stage, err)
        finally:
            if session is not None:
                try:
                    async with asyncio.timeout(CLEANUP_TIMEOUT):
                        await session.async_stop()
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

    async def async_shutdown(self) -> None:
        self._stopping = True
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
