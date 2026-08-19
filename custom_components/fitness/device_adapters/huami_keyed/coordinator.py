"""Bounded history sync for keyed legacy Huami / Xiaomi bands."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ...device_credentials import async_get_device_credential_store
from ...device_user_action import clear_device_user_action, request_device_user_action
from ..history import DeviceHistoryBatch, DeviceMetricPoint
from ..history_coordinator import DeviceHistoryFetch, DirectHistoryCoordinator
from .protocol import (
    ACTIVITY_UUID,
    AUTH_REQUEST_RANDOM,
    AUTH_SEND_ENCRYPTED_PREFIX,
    AUTH_UUID,
    FETCH_START,
    FETCH_UUID,
    build_fetch_request,
    normalize_auth_key,
    parse_activity_packet,
    parse_auth_notification,
    parse_fetch_start,
)

AUTH_TIMEOUT = 7.0
FETCH_START_TIMEOUT = 7.0
PACKET_IDLE_TIMEOUT = 3.0
MAX_MINUTES_PER_SYNC = 640
MAX_SEEN = 4096
CONTINUE_AFTER = 30.0
FIRST_SYNC_LOOKBACK = timedelta(days=14)
OVERLAP = timedelta(minutes=8)
ACTION_AUTH_KEY = "authentication_key_required"


class HuamiCredentialRequired(RuntimeError):
    """The device cannot be authenticated without user-supplied credentials."""


def _signature(stamp: datetime, category: int, acceleration: int, steps: int, heart_rate: int | None) -> str:
    raw = f"{stamp.replace(second=0, microsecond=0).isoformat()}:{category}:{acceleration}:{steps}:{heart_rate}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class HuamiKeyedCoordinator(DirectHistoryCoordinator):
    """Common read-only FEE1 history implementation for Mi Band 3-7."""

    model_name = "Xiaomi fitness band"
    sync_unique_suffix = "sync_xiaomi_band_full"
    sync_translation_key = "sync_device_health_history"
    sync_icon = "mdi:watch-import"

    def _timezone(self):
        try:
            return ZoneInfo(str(self.hass.config.time_zone or "UTC"))
        except (ZoneInfoNotFoundError, ValueError):
            return timezone.utc

    def _device_label(self, sensor_id: str) -> str:
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        return sensor.label() if sensor is not None else self.model_name

    def _report_auth_key_required(self, sensor_id: str, *, invalid: bool = False) -> None:
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        device = self._device_label(canonical)
        request_device_user_action(
            self.hass,
            adapter_id=self.adapter_id,
            sensor_id=canonical,
            device=device,
            action=ACTION_AUTH_KEY,
            reason=(
                "The saved authentication key was rejected by the band."
                if invalid
                else "This Xiaomi band requires its 16-byte authentication key."
            ),
            instructions=(
                "Keep the band paired to its current phone/vendor account; do not factory-reset or unbind it.",
                "Obtain the device authentication key from the existing Xiaomi/Zepp pairing using a method appropriate for your phone/app version.",
                "Enter the 32 hexadecimal characters in the Authentication key field below.",
                "Fully close the vendor app or otherwise make sure it is not actively connected to the band.",
                "Submit this repair. Fitness will immediately retry a full read-only sync.",
            ),
            fields=("auth_key",),
        )

    async def _authentication_key(self, sensor_id: str) -> bytes:
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        store = async_get_device_credential_store(self.hass)
        values = await store.async_get(canonical, self.adapter_id)
        value = values.get("auth_key")
        if not value:
            self._report_auth_key_required(canonical)
            raise HuamiCredentialRequired("authentication key required")
        try:
            return normalize_auth_key(value)
        except ValueError as err:
            self._report_auth_key_required(canonical, invalid=True)
            raise HuamiCredentialRequired(str(err)) from err

    async def _authenticate(self, client, sensor_id: str) -> None:
        key = await self._authentication_key(sensor_id)
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=8)

        def notify(_sender, data) -> None:
            raw = bytes(data)
            if raw and not queue.full():
                queue.put_nowait(raw)

        await client.start_notify(AUTH_UUID, notify)
        try:
            # Read-only/non-destructive login. We intentionally never send the
            # key-install command that writes/replaces device pairing state.
            await client.write_gatt_char(AUTH_UUID, AUTH_REQUEST_RANDOM, response=True)
            async with asyncio.timeout(AUTH_TIMEOUT):
                status, challenge = parse_auth_notification(await queue.get())
            if status != "challenge" or challenge is None:
                self._report_auth_key_required(sensor_id, invalid=True)
                raise HuamiCredentialRequired(f"authentication challenge failed ({status})")
            encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
            encrypted = encryptor.update(challenge) + encryptor.finalize()
            await client.write_gatt_char(
                AUTH_UUID, AUTH_SEND_ENCRYPTED_PREFIX + encrypted, response=True
            )
            async with asyncio.timeout(AUTH_TIMEOUT):
                status, _ = parse_auth_notification(await queue.get())
            if status != "authenticated":
                self._report_auth_key_required(sensor_id, invalid=True)
                raise HuamiCredentialRequired(f"authentication failed ({status})")
        finally:
            try:
                await client.stop_notify(AUTH_UUID)
            except Exception:
                pass
        clear_device_user_action(
            self.hass,
            adapter_id=self.adapter_id,
            sensor_id=self.runtime.resolve_sensor_id(sensor_id),
            action=ACTION_AUTH_KEY,
        )

    async def async_fetch_history(
        self, client, state: dict[str, Any], *, sensor_id: str
    ) -> DeviceHistoryFetch:
        await self._authenticate(client, sensor_id)
        source_type = f"direct_{self.adapter_id}"
        now = datetime.now(timezone.utc)
        tz = self._timezone()
        points: list[DeviceMetricPoint] = []

        previous = self._parse_dt(state.get("last_history_timestamp"))
        requested_utc = (previous - OVERLAP) if previous is not None else (now - FIRST_SYNC_LOOKBACK)
        requested_local = requested_utc.astimezone(tz).replace(tzinfo=None)

        fetch_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=32)
        activity_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=256)

        def fetch_notify(_sender, data) -> None:
            raw = bytes(data)
            if raw and not fetch_queue.full():
                fetch_queue.put_nowait(raw)

        def activity_notify(_sender, data) -> None:
            raw = bytes(data)
            if not raw:
                return
            if activity_queue.full():
                try:
                    activity_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            if not activity_queue.full():
                activity_queue.put_nowait(raw)

        existing_seen = [str(value) for value in (state.get("seen") or [])[-MAX_SEEN:]]
        seen = set(existing_seen)
        new_seen = list(existing_seen)
        max_stamp: datetime | None = previous
        accepted = 0
        packet_rollovers = 0
        last_wire_index: int | None = None
        more_pending = False
        fetch_notifying = activity_notifying = False

        try:
            await client.start_notify(FETCH_UUID, fetch_notify)
            fetch_notifying = True
            await client.start_notify(ACTIVITY_UUID, activity_notify)
            activity_notifying = True
            await client.write_gatt_char(FETCH_UUID, build_fetch_request(requested_local), response=True)
            async with asyncio.timeout(FETCH_START_TIMEOUT):
                transfer_start_local = parse_fetch_start(await fetch_queue.get())
            await client.write_gatt_char(FETCH_UUID, FETCH_START, response=True)

            while accepted < MAX_MINUTES_PER_SYNC:
                try:
                    async with asyncio.timeout(PACKET_IDLE_TIMEOUT):
                        raw = await activity_queue.get()
                except TimeoutError:
                    break
                if len(raw) != 17:
                    continue
                wire_index = int(raw[0])
                if last_wire_index is not None and wire_index < last_wire_index and last_wire_index - wire_index > 128:
                    packet_rollovers += 1
                packet_number = packet_rollovers * 256 + wire_index
                last_wire_index = wire_index
                samples = parse_activity_packet(
                    raw,
                    transfer_start_local=transfer_start_local,
                    packet_number=packet_number,
                    timezone_info=tz,
                )
                if accepted + len(samples) > MAX_MINUTES_PER_SYNC:
                    more_pending = True
                    break
                for sample in samples:
                    signature = _signature(sample.timestamp, sample.category, sample.acceleration, sample.steps, sample.heart_rate)
                    if signature in seen:
                        continue
                    seen.add(signature)
                    new_seen.append(signature)
                    accepted += 1
                    stamp = sample.timestamp.isoformat()
                    context = (
                        ("measurement_context", "minute_activity"),
                        ("activity_category", sample.category),
                        ("acceleration_raw", sample.acceleration),
                    )
                    points.append(DeviceMetricPoint("steps", float(sample.steps), stamp, source_type, sensor_id, (sensor_id,), context))
                    points.append(DeviceMetricPoint("activity_level", sample.activity_level, stamp, source_type, sensor_id, (sensor_id,), context))
                    if sample.heart_rate is not None:
                        points.append(DeviceMetricPoint("heart_rate", float(sample.heart_rate), stamp, source_type, sensor_id, (sensor_id,), context))
                    if max_stamp is None or sample.timestamp > max_stamp:
                        max_stamp = sample.timestamp
                if accepted >= MAX_MINUTES_PER_SYNC:
                    more_pending = True
                    break
        finally:
            if activity_notifying:
                try:
                    await client.stop_notify(ACTIVITY_UUID)
                except Exception:
                    pass
            if fetch_notifying:
                try:
                    await client.stop_notify(FETCH_UUID)
                except Exception:
                    pass

        working = dict(state)
        working["seen"] = new_seen[-MAX_SEEN:]
        working["last_minutes_received"] = accepted
        if max_stamp is not None:
            working["last_history_timestamp"] = (max_stamp + timedelta(minutes=1)).isoformat()
        return DeviceHistoryFetch(
            DeviceHistoryBatch.bounded(metric_points=points),
            working,
            continue_after=CONTINUE_AFTER if more_pending else None,
        )
