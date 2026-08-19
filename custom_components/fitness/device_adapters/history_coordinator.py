"""Low-overhead coordinator for direct wearable health-history adapters."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import partial
import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.helpers.storage import Store

from ..const import DOMAIN
from ..device_credentials import async_get_device_credential_store
from .history import DeviceHistoryBatch

_LOGGER = logging.getLogger(__name__)

DEFAULT_SYNC_INTERVAL = timedelta(hours=1)
SESSION_TIMEOUT = 45.0
CONNECT_TIMEOUT = 20.0
UNREACHABLE_RETRY = 30 * 60.0
BUSY_RETRY = 15 * 60.0
ERROR_RETRY_BASE = 30 * 60.0
MAX_ERROR_RETRY = 4 * 60 * 60.0
ADVERTISEMENT_ACTION_MIN_INTERVAL = 60.0
SHUTDOWN_TIMEOUT = 8.0
MAX_STORED_DEVICES = 64


@dataclass(slots=True, frozen=True)
class DeviceHistoryFetch:
    """One successful protocol fetch and the adapter checkpoint to persist."""

    batch: DeviceHistoryBatch
    state: dict[str, Any]
    continue_after: float | None = None
    workouts: tuple[Any, ...] = ()


class DirectHistoryCoordinator:
    """Shared bounded lifecycle for read-only BLE wellness history adapters.

    Subclasses implement only protocol parsing/fetching.  Connection ownership,
    backoff, persistence and profile import are common so every adapter has the
    same Home Assistant safety properties.
    """

    adapter_id = "direct_history"
    sync_unique_suffix = "sync_device_health_history"
    sync_translation_key = "sync_device_data"
    sync_icon = "mdi:heart-pulse"
    sync_interval = DEFAULT_SYNC_INTERVAL

    def __init__(self, provider) -> None:
        self.provider = provider
        self.runtime = provider.runtime
        self.hass = provider.hass
        self._store = Store(
            self.hass,
            1,
            f"fitness_direct_history_{self.adapter_id}",
        )
        self._state: dict[str, Any] = {"devices": {}}
        self._tasks: dict[str, asyncio.Task] = {}
        self._background: set[asyncio.Task] = set()
        self._save_lock = asyncio.Lock()
        self._stopping = False
        self._initialized = False
        self._last_advertisement_action: dict[str, float] = {}
        self._reconfigure_unsub = None

    async def async_setup(self) -> None:
        stored = await self._store.async_load() or {}
        devices = stored.get("devices")
        if isinstance(devices, dict):
            self._state = {"devices": devices}
        self._initialized = True
        self._prune_devices()

        def _reconfigure_completed(event) -> None:
            data = event.data
            if str(data.get("adapter_id") or "") != self.adapter_id:
                return
            sensor_id = str(data.get("sensor_id") or "")
            if sensor_id:
                self.schedule(sensor_id, delay=0.0, force=True)

        self._reconfigure_unsub = self.hass.bus.async_listen(
            "fitness_device_reconfigure_completed", _reconfigure_completed
        )
        for sensor in tuple(self.runtime.sensors.values()):
            sensor_id = self.runtime.resolve_sensor_id(sensor.sensor_id)
            endpoint = sensor.endpoints.get("bluetooth")
            if (
                endpoint is not None
                and endpoint.metadata.get("archive_adapter") == self.adapter_id
                and self._eligible(sensor_id)
            ):
                state = self._device(sensor_id)
                due = self._parse_dt(state.get("next_attempt"))
                if due is None:
                    last = self._parse_dt(state.get("last_successful_sync"))
                    due = (
                        last + self.sync_interval
                        if last is not None
                        else datetime.now(timezone.utc) + timedelta(seconds=5)
                    )
                self.schedule(
                    sensor_id,
                    delay=max(0.0, (due - datetime.now(timezone.utc)).total_seconds()),
                    force=True,
                )

    async def async_shutdown(self) -> None:
        self._stopping = True
        if self._reconfigure_unsub is not None:
            self._reconfigure_unsub()
            self._reconfigure_unsub = None
        tasks = list(self._tasks.values()) + list(self._background)
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            try:
                async with asyncio.timeout(SHUTDOWN_TIMEOUT):
                    await asyncio.gather(*tasks, return_exceptions=True)
            except TimeoutError:
                _LOGGER.warning("Timed out stopping %s direct-history tasks", self.adapter_id)

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)

    def _device(self, sensor_id: str) -> dict[str, Any]:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        devices = self._state.setdefault("devices", {})
        state = devices.get(sensor_id)
        if not isinstance(state, dict):
            state = devices[sensor_id] = {"retry_count": 0}
        return state

    def _prune_devices(self) -> None:
        devices = self._state.setdefault("devices", {})
        if len(devices) <= MAX_STORED_DEVICES:
            return
        ordered = sorted(
            devices,
            key=lambda key: str((devices.get(key) or {}).get("last_successful_sync") or ""),
            reverse=True,
        )
        keep = set(ordered[:MAX_STORED_DEVICES])
        self._state["devices"] = {key: devices[key] for key in ordered if key in keep}

    async def _save(self) -> None:
        if not self._initialized:
            return
        self._prune_devices()
        async with self._save_lock:
            await self._store.async_save(self._state)

    def _background_task(self, coro, name: str) -> asyncio.Task:
        task = self.hass.async_create_background_task(coro, name, eager_start=False)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    def _eligible(self, sensor_id: str) -> bool:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        return bool(
            sensor is not None
            and endpoint is not None
            and endpoint.metadata.get("archive_adapter") == self.adapter_id
            and self.runtime.sensor_is_accepted(sensor_id)
            and self.runtime.sensor_archive_profile_ids(sensor_id)
        )

    def advertise(self, sensor_id: str, _identity: dict[str, Any]) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        now_mono = self.hass.loop.time()
        previous = self._last_advertisement_action.get(sensor_id)
        if previous is not None and now_mono - previous < ADVERTISEMENT_ACTION_MIN_INTERVAL:
            return
        self._last_advertisement_action[sensor_id] = now_mono
        if not self._eligible(sensor_id):
            return
        state = self._device(sensor_id)
        due = self._parse_dt(state.get("next_attempt"))
        now = datetime.now(timezone.utc)
        if due is not None and due > now:
            return
        last = self._parse_dt(state.get("last_successful_sync"))
        if last is not None and now - last < self.sync_interval:
            return
        self.schedule(sensor_id, delay=1.0)

    def acceptance_changed(self, sensor_id: str, accepted: bool) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if not accepted:
            task = self._tasks.pop(sensor_id, None)
            if task is not None:
                task.cancel()
            return
        if self._eligible(sensor_id):
            self.schedule(sensor_id, delay=2.0, force=True)

    def assignment_changed(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if self._eligible(sensor_id):
            self.schedule(sensor_id, delay=2.0, force=True)

    def forget_sensor(self, sensor_id: str) -> None:
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        task = self._tasks.pop(sensor_id, None)
        if task is not None:
            task.cancel()
        if self._state.setdefault("devices", {}).pop(sensor_id, None) is not None:
            self._background_task(
                self._save(), f"fitness {self.adapter_id} forget {sensor_id}"
            )
        credential_store = async_get_device_credential_store(self.hass)
        self._background_task(
            credential_store.async_remove(sensor_id, self.adapter_id),
            f"fitness {self.adapter_id} forget credentials {sensor_id}",
        )

    def identity_conflict_repaired(self, sensor_id: str) -> None:
        self.forget_sensor(sensor_id)

    def schedule(self, sensor_id: str, *, delay: float = 0.0, force: bool = False) -> None:
        if self._stopping:
            return
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        current = self._tasks.get(sensor_id)
        if current is not None and not current.done():
            if not force:
                return
            current.cancel()

        async def _runner() -> None:
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                await self._async_sync(sensor_id, force=force)
            except asyncio.CancelledError:
                raise
            finally:
                if self._tasks.get(sensor_id) is asyncio.current_task():
                    self._tasks.pop(sensor_id, None)

        task = self.hass.async_create_background_task(
            _runner(), f"fitness {self.adapter_id} sync {sensor_id}", eager_start=False
        )
        self._tasks[sensor_id] = task

    async def async_sync_now(self, sensor_id: str) -> asyncio.Task | None:
        """Start one forced *full* device sync for this adapter.

        Direct-history adapters perform their complete protocol transaction in
        ``async_fetch_history`` (health, sleep, device state and workouts where
        supported).  The generic UI calls this method so every direct device has
        the same manual-sync contract instead of a product-specific retry path.
        """
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        self.schedule(canonical, delay=0.0, force=True)
        return self._tasks.get(canonical)

    async def async_fetch_history(
        self, client, state: dict[str, Any], *, sensor_id: str
    ) -> DeviceHistoryFetch:
        """Fetch one protocol-specific bounded history transaction."""
        raise NotImplementedError

    async def _async_import(self, sensor_id: str, batch: DeviceHistoryBatch) -> None:
        profile_ids = self.runtime.sensor_archive_profile_ids(sensor_id)
        for profile_id in profile_ids:
            manager = self.hass.data.get(DOMAIN, {}).get(profile_id)
            if manager is None:
                raise RuntimeError(f"Fitness profile {profile_id} is not loaded")
            await manager.async_import_device_history(batch)

    def _schedule_after_current(
        self, sensor_id: str, delay: float, *, force: bool = True
    ) -> None:
        """Schedule after the current coordinator task has unwound."""
        self.hass.loop.call_soon(
            partial(self.schedule, sensor_id, delay=delay, force=force)
        )

    async def _schedule_retry(
        self,
        sensor_id: str,
        state: dict[str, Any],
        *,
        delay: float,
        error: str | None = None,
    ) -> None:
        next_attempt = datetime.now(timezone.utc) + timedelta(seconds=delay)
        state["next_attempt"] = next_attempt.isoformat()
        if error is not None:
            state["last_error"] = error[:500]
        await self._save()
        self._schedule_after_current(sensor_id, delay, force=True)

    async def _async_sync(self, requested_sensor_id: str, *, force: bool = False) -> None:
        sensor_id = self.runtime.resolve_sensor_id(requested_sensor_id)
        if not self._eligible(sensor_id):
            return
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if sensor is None or endpoint is None:
            return
        state = self._device(sensor_id)
        now = datetime.now(timezone.utc)
        if not force:
            due = self._parse_dt(state.get("next_attempt"))
            if due is not None and due > now:
                return
            last = self._parse_dt(state.get("last_successful_sync"))
            if last is not None and now - last < self.sync_interval:
                return

        if self.provider.sensor_connected(sensor_id) or self.provider.sensor_users(sensor_id):
            await self._schedule_retry(sensor_id, state, delay=BUSY_RETRY)
            return

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, endpoint.address, connectable=True
        )
        if ble_device is None:
            await self._schedule_retry(sensor_id, state, delay=UNREACHABLE_RETRY)
            return

        client = None
        lock = self.provider._connect_lock(sensor_id)
        try:
            async with asyncio.timeout(SESSION_TIMEOUT):
                async with lock:
                    if self.provider.sensor_connected(sensor_id) or self.provider.sensor_users(sensor_id):
                        await self._schedule_retry(sensor_id, state, delay=BUSY_RETRY)
                        return
                    state.update(
                        sync_state="connecting",
                        last_attempt=now.isoformat(),
                        next_attempt=None,
                    )
                    await self._save()
                    async with asyncio.timeout(CONNECT_TIMEOUT):
                        client = await self.provider.establish_connection(
                            ble_device,
                            sensor.name or endpoint.address,
                            max_attempts=2,
                        )
                    working = deepcopy(state)
                    working["sync_state"] = "syncing"
                    fetched = await self.async_fetch_history(
                        client, working, sensor_id=sensor_id
                    )
                    await self._async_import(sensor_id, fetched.batch)
                    if fetched.workouts:
                        profile_ids = self.runtime.sensor_archive_profile_ids(sensor_id)
                        for profile_id in profile_ids:
                            manager = self.hass.data.get(DOMAIN, {}).get(profile_id)
                            if manager is None:
                                raise RuntimeError(f"Fitness profile {profile_id} is not loaded")
                            await manager.async_import_device_workouts(list(fetched.workouts))
                    committed = dict(fetched.state)
                    success = datetime.now(timezone.utc)
                    continue_delay = (
                        max(30.0, float(fetched.continue_after))
                        if fetched.continue_after is not None
                        else self.sync_interval.total_seconds()
                    )
                    committed.update(
                        sync_state=(
                            "waiting" if fetched.continue_after is not None else "ready"
                        ),
                        retry_count=0,
                        last_error=None,
                        last_successful_sync=success.isoformat(),
                        next_attempt=(success + timedelta(seconds=continue_delay)).isoformat(),
                    )
                    self._state.setdefault("devices", {})[sensor_id] = committed
                    state = committed
                    await self._save()
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - physical devices are untrusted I/O
            state = self._device(sensor_id)
            retries = min(8, int(state.get("retry_count") or 0) + 1)
            state.update(sync_state="retrying", retry_count=retries)
            delay = min(MAX_ERROR_RETRY, ERROR_RETRY_BASE * (2 ** min(retries - 1, 3)))
            _LOGGER.warning(
                "%s direct history sync failed for %s: %s: %s",
                self.adapter_id,
                sensor_id,
                type(err).__name__,
                str(err)[:300],
            )
            await self._schedule_retry(
                sensor_id,
                state,
                delay=delay,
                error=f"{type(err).__name__}: {str(err)}",
            )
            return
        finally:
            if client is not None:
                await self.provider._async_disconnect_client(
                    client, reason=f"{self.adapter_id} history cleanup"
                )

        due = self._parse_dt(state.get("next_attempt"))
        if due is not None:
            self._schedule_after_current(
                sensor_id,
                max(1.0, (due - datetime.now(timezone.utc)).total_seconds()),
                force=True,
            )
