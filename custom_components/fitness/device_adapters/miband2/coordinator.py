"""Bounded retained-health synchronization for Xiaomi Mi Band 2."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from ...const import DOMAIN
from ...device_user_action import clear_device_user_action, request_device_user_action
from ..history import DeviceHistoryBatch, DeviceMetricPoint
from ..history_coordinator import DeviceHistoryFetch, DirectHistoryCoordinator
from .protocol import (
    AUTH_REQUEST_RANDOM,
    AUTH_SEND_ENCRYPTED_PREFIX,
    FETCH_START,
    LEGACY_AUTH_KEY,
    MIBAND2_ACTIVITY_UUID,
    MIBAND2_AUTH_UUID,
    MIBAND2_BATTERY_UUID,
    MIBAND2_FETCH_UUID,
    MIBAND2_REALTIME_STEPS_UUID,
    build_fetch_request,
    parse_activity_packet,
    parse_auth_notification,
    parse_battery_level,
    parse_fetch_start,
    parse_realtime_steps,
)

AUTH_TIMEOUT = 7.0
FETCH_START_TIMEOUT = 7.0
PACKET_IDLE_TIMEOUT = 3.0
MAX_MINUTES_PER_SYNC = 640
MAX_SEEN = 4096
CONTINUE_AFTER = 30.0
FIRST_SYNC_LOOKBACK = timedelta(days=14)
OVERLAP = timedelta(minutes=8)


class MiBand2AuthenticationRequired(RuntimeError):
    """Raised when the legacy app-layer key is not accepted."""


def _signature(stamp: datetime, category: int, acceleration: int, steps: int, heart_rate: int | None) -> str:
    raw = f"{stamp.replace(second=0, microsecond=0).isoformat()}:{category}:{acceleration}:{steps}:{heart_rate}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class MiBand2Coordinator(DirectHistoryCoordinator):
    adapter_id = "xiaomi_miband2"
    sync_unique_suffix = "sync_miband2_full"
    sync_translation_key = "sync_device_data"
    sync_icon = "mdi:watch-import"

    def _timezone(self):
        try:
            return ZoneInfo(str(self.hass.config.time_zone or "UTC"))
        except (ZoneInfoNotFoundError, ValueError):
            return timezone.utc

    def _report_auth_required(self, sensor_id: str) -> None:
        # request_device_user_action also emits fitness_device_user_action_required event.
        canonical = self.runtime.resolve_sensor_id(sensor_id)
        sensor = self.runtime.sensors.get(canonical)
        device = sensor.label() if sensor is not None else "Xiaomi Mi Band 2"
        request_device_user_action(
            self.hass,
            adapter_id=self.adapter_id,
            sensor_id=canonical,
            device=device,
            action="authentication_required",
            reason="The Mi Band 2 did not accept its non-destructive legacy authentication session.",
            instructions=(
                "Make sure the Mi Band 2 is not actively connected to another Bluetooth host.",
                "If it has never been initialized, pair it once with Zepp Life / Mi Fit, then fully close that app.",
                "Do not factory-reset or unbind a working phone pairing just for Home Assistant.",
                "Submit this Repair after the band is free. Fitness will retry the full read-only sync immediately.",
            ),
        )

    async def _read_optional(self, client, uuid: str) -> bytes | None:
        try:
            return bytes(await client.read_gatt_char(uuid))
        except Exception:  # noqa: BLE001 - optional characteristics vary by firmware
            return None

    async def _authenticate(self, client) -> None:
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=8)

        def notify(_sender, data) -> None:
            raw = bytes(data)
            if raw and not queue.full():
                queue.put_nowait(raw)

        await client.start_notify(MIBAND2_AUTH_UUID, notify)
        try:
            # Authentication only: do not send the key-init command here. That
            # command can replace an existing app pairing, so Fitness never
            # performs it as an unattended hourly side effect.
            await client.write_gatt_char(MIBAND2_AUTH_UUID, AUTH_REQUEST_RANDOM, response=True)
            async with asyncio.timeout(AUTH_TIMEOUT):
                status, challenge = parse_auth_notification(await queue.get())
            if status != "challenge" or challenge is None:
                raise MiBand2AuthenticationRequired(f"Mi Band 2 auth challenge failed ({status})")
            encryptor = Cipher(algorithms.AES(LEGACY_AUTH_KEY), modes.ECB()).encryptor()
            encrypted = encryptor.update(challenge) + encryptor.finalize()
            await client.write_gatt_char(
                MIBAND2_AUTH_UUID,
                AUTH_SEND_ENCRYPTED_PREFIX + encrypted,
                response=True,
            )
            async with asyncio.timeout(AUTH_TIMEOUT):
                status, _ = parse_auth_notification(await queue.get())
            if status != "authenticated":
                raise MiBand2AuthenticationRequired(f"Mi Band 2 authentication failed ({status})")
        finally:
            try:
                await client.stop_notify(MIBAND2_AUTH_UUID)
            except Exception:
                pass
        clear_device_user_action(
            self.hass,
            adapter_id=self.adapter_id,
            sensor_id=self.runtime.resolve_sensor_id(sensor_id),
            action="authentication_required",
        )

    async def async_fetch_history(
        self, client, state: dict[str, Any], *, sensor_id: str
    ) -> DeviceHistoryFetch:
        source_type = "direct_xiaomi_miband2"
        now = datetime.now(timezone.utc)
        tz = self._timezone()
        try:
            await self._authenticate(client)
        except MiBand2AuthenticationRequired:
            self._report_auth_required(sensor_id)
            raise
        points: list[DeviceMetricPoint] = []
        battery_raw = await self._read_optional(client, MIBAND2_BATTERY_UUID)
        if battery_raw is not None:
            try:
                level = parse_battery_level(battery_raw)
            except ValueError:
                pass
            else:
                points.append(DeviceMetricPoint("battery", float(level), now.isoformat(), source_type, sensor_id, (sensor_id,)))

        realtime_raw = await self._read_optional(client, MIBAND2_REALTIME_STEPS_UUID)
        if realtime_raw is not None:
            try:
                total_steps = parse_realtime_steps(realtime_raw)
            except ValueError:
                pass
            else:
                points.append(
                    DeviceMetricPoint(
                        "steps",
                        float(total_steps),
                        now.isoformat(),
                        "direct_xiaomi_miband2_current",
                        sensor_id,
                        (sensor_id,),
                        (("measurement_context", "current_total"),),
                    )
                )

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
            await client.start_notify(MIBAND2_FETCH_UUID, fetch_notify)
            fetch_notifying = True
            await client.start_notify(MIBAND2_ACTIVITY_UUID, activity_notify)
            activity_notifying = True
            await client.write_gatt_char(MIBAND2_FETCH_UUID, build_fetch_request(requested_local), response=True)

            async with asyncio.timeout(FETCH_START_TIMEOUT):
                transfer_start_local = parse_fetch_start(await fetch_queue.get())
            await client.write_gatt_char(MIBAND2_FETCH_UUID, FETCH_START, response=True)

            while accepted < MAX_MINUTES_PER_SYNC:
                try:
                    async with asyncio.timeout(PACKET_IDLE_TIMEOUT):
                        raw = await activity_queue.get()
                except TimeoutError:
                    break
                if len(raw) != 17:
                    # Fetch-status notifications belong to the other queue; do
                    # not try to resynchronize malformed activity bytes.
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
                    await client.stop_notify(MIBAND2_ACTIVITY_UUID)
                except Exception:
                    pass
            if fetch_notifying:
                try:
                    await client.stop_notify(MIBAND2_FETCH_UUID)
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
