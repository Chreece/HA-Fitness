"""Bounded read-only Mi Band 1/1A/1S activity and sleep synchronization."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...providers.sleep import SleepRecord
from ..history import DeviceHistoryBatch, DeviceMetricPoint
from ..history_coordinator import DeviceHistoryFetch, DirectHistoryCoordinator
from .protocol import (
    ACTIVITY_TYPE_DEEP_SLEEP,
    ACTIVITY_TYPE_LIGHT_SLEEP,
    ACTIVITY_TYPE_NOT_WORN,
    CMD_FETCH_ACTIVITY,
    CMD_STOP_SYNC,
    MIBAND1_ACTIVITY_UUID,
    MIBAND1_BATTERY_UUID,
    MIBAND1_CONTROL_UUID,
    MIBAND1_REALTIME_STEPS_UUID,
    MiBand1ActivitySample,
    build_activity_ack,
    parse_activity_header,
    parse_activity_records,
    parse_battery_state,
    parse_realtime_steps,
)

PACKET_TIMEOUT = 7.0
MAX_MINUTES_PER_SYNC = 640
MAX_SEEN = 4096
CONTINUE_AFTER = 30.0


def _minute_signature(sample: MiBand1ActivitySample) -> str:
    stamp = sample.timestamp.replace(second=0, microsecond=0).isoformat()
    return f"{stamp}:{sample.activity_type}:{sample.intensity}:{sample.steps}"


def _sleep_records(samples: list[MiBand1ActivitySample], sensor_id: str) -> list[SleepRecord]:
    """Build sleep records from only the stages the legacy band actually reports."""
    sleep = sorted(
        (sample for sample in samples if sample.activity_type in {ACTIVITY_TYPE_LIGHT_SLEEP, ACTIVITY_TYPE_DEEP_SLEEP}),
        key=lambda sample: sample.timestamp,
    )
    if not sleep:
        return []

    records: list[SleepRecord] = []
    group: list[MiBand1ActivitySample] = []

    def flush() -> None:
        if not group:
            return
        start = group[0].timestamp.replace(second=0, microsecond=0)
        end = group[-1].timestamp.replace(second=0, microsecond=0) + timedelta(minutes=1)
        light = sum(60.0 for item in group if item.activity_type == ACTIVITY_TYPE_LIGHT_SLEEP)
        deep = sum(60.0 for item in group if item.activity_type == ACTIVITY_TYPE_DEEP_SLEEP)
        classified = light + deep
        if classified < 5 * 60:
            group.clear()
            return
        records.append(
            SleepRecord(
                source=f"miband1:{sensor_id}:{start.isoformat()}",
                provider_domain="direct_xiaomi_miband1",
                start=start.isoformat(),
                end=end.isoformat(),
                observed_at=end.isoformat(),
                duration_s=classified,
                time_in_bed_s=(end - start).total_seconds(),
                light_sleep_s=light or None,
                deep_sleep_s=deep or None,
                in_bed=False,
                sources=[sensor_id],
                provider_domains=["direct_xiaomi_miband1"],
                field_sources={
                    "start": sensor_id,
                    "end": sensor_id,
                    "light_sleep_s": sensor_id,
                    "deep_sleep_s": sensor_id,
                },
            )
        )
        group.clear()

    # Missing/non-sleep minutes should not split a night immediately.  A 30-min
    # gap is enough to bridge occasional sparse records without joining a nap to
    # the main night.  We count only explicitly classified sleep as duration.
    for sample in sleep:
        if group and sample.timestamp - group[-1].timestamp > timedelta(minutes=30):
            flush()
        group.append(sample)
    flush()
    return records


class MiBand1Coordinator(DirectHistoryCoordinator):
    adapter_id = "xiaomi_miband1"
    sync_unique_suffix = "sync_miband1_full"
    sync_translation_key = "sync_device_data"
    sync_icon = "mdi:watch-import"

    def _timezone(self):
        try:
            return ZoneInfo(str(self.hass.config.time_zone or "UTC"))
        except (ZoneInfoNotFoundError, ValueError):
            return timezone.utc

    async def _read_optional(self, client, uuid: str) -> bytes | None:
        try:
            return bytes(await client.read_gatt_char(uuid))
        except Exception:  # noqa: BLE001 - optional legacy characteristics vary by firmware
            return None

    async def async_fetch_history(
        self, client, state: dict[str, Any], *, sensor_id: str
    ) -> DeviceHistoryFetch:
        source_type = "direct_xiaomi_miband1"
        now = datetime.now(timezone.utc)
        points: list[DeviceMetricPoint] = []
        context_state: dict[str, Any] = {}

        battery_raw = await self._read_optional(client, MIBAND1_BATTERY_UUID)
        if battery_raw is not None:
            try:
                battery = parse_battery_state(battery_raw)
            except ValueError:
                battery = None
            if battery is not None:
                context_state.update(
                    charge_cycles=battery.charge_cycles,
                    battery_status=battery.status,
                    last_charge_local=(battery.last_charge_local.isoformat() if battery.last_charge_local else None),
                )
                context = tuple((key, value) for key, value in context_state.items() if value is not None)
                if battery.battery is not None:
                    points.append(DeviceMetricPoint("battery", float(battery.battery), now.isoformat(), source_type, sensor_id, (sensor_id,), context))
                if battery.charging is not None:
                    points.append(DeviceMetricPoint("charging", 1.0 if battery.charging else 0.0, now.isoformat(), source_type, sensor_id, (sensor_id,), context))

        realtime_raw = await self._read_optional(client, MIBAND1_REALTIME_STEPS_UUID)
        if realtime_raw is not None:
            try:
                current_steps = parse_realtime_steps(realtime_raw)
            except ValueError:
                current_steps = None
            if current_steps is not None:
                points.append(
                    DeviceMetricPoint(
                        "steps",
                        float(current_steps),
                        now.isoformat(),
                        "direct_xiaomi_miband1_current",
                        sensor_id,
                        (sensor_id,),
                        (("measurement_context", "current_total"),),
                    )
                )
                context_state["current_steps"] = current_steps

        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=256)

        def _notify(_sender, data) -> None:
            raw = bytes(data)
            if not raw:
                return
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(raw)
            except asyncio.QueueFull:
                pass

        existing_seen = [str(value) for value in (state.get("seen") or [])[-MAX_SEEN:]]
        seen = set(existing_seen)
        new_seen = list(existing_seen)
        accepted_samples: list[MiBand1ActivitySample] = []
        processed_minutes = 0
        more_pending = False
        timezone_info = self._timezone()
        notifying = False

        try:
            await client.start_notify(MIBAND1_ACTIVITY_UUID, _notify)
            notifying = True
            await client.write_gatt_char(MIBAND1_CONTROL_UUID, CMD_FETCH_ACTIVITY, response=False)

            while processed_minutes < MAX_MINUTES_PER_SYNC:
                async with asyncio.timeout(PACKET_TIMEOUT):
                    raw_header = await queue.get()
                # Some stacks can concatenate notifications; an activity header
                # is exactly 11 bytes. Reject ambiguity instead of shifting data.
                header = parse_activity_header(raw_header)
                if header.block_records == 0:
                    await client.write_gatt_char(
                        MIBAND1_CONTROL_UUID, build_activity_ack(header, 0), response=False
                    )
                    break

                block = bytearray()
                while len(block) < header.block_bytes:
                    async with asyncio.timeout(PACKET_TIMEOUT):
                        chunk = await queue.get()
                    remaining = header.block_bytes - len(block)
                    if len(chunk) > remaining:
                        raise ValueError("Mi Band 1 activity chunk exceeds declared block")
                    block.extend(chunk)
                samples = parse_activity_records(
                    bytes(block), start=header.start_local, timezone_info=timezone_info
                )

                # Never ACK a block that we cannot retain. Legacy bands may remove
                # acknowledged activity from their circular history, so a bounded
                # sync must stop *before* acknowledging the next complete block.
                if processed_minutes and processed_minutes + len(samples) > MAX_MINUTES_PER_SYNC:
                    more_pending = True
                    break
                if not processed_minutes and len(samples) > MAX_MINUTES_PER_SYNC:
                    raise ValueError("Mi Band 1 activity block exceeds bounded sync window")

                await client.write_gatt_char(
                    MIBAND1_CONTROL_UUID,
                    build_activity_ack(header, len(block)),
                    response=False,
                )

                processed_minutes += len(samples)
                for sample in samples:
                    signature = _minute_signature(sample)
                    if signature in seen:
                        continue
                    seen.add(signature)
                    new_seen.append(signature)
                    accepted_samples.append(sample)

                if processed_minutes >= MAX_MINUTES_PER_SYNC:
                    more_pending = True
                    break
        except TimeoutError:
            # A silent device after returning some complete blocks is a bounded
            # partial success; with no records at all it is a real sync failure.
            if processed_minutes == 0:
                raise
            more_pending = True
        finally:
            try:
                await client.write_gatt_char(MIBAND1_CONTROL_UUID, CMD_STOP_SYNC, response=False)
            except Exception:
                pass
            if notifying:
                try:
                    await client.stop_notify(MIBAND1_ACTIVITY_UUID)
                except Exception:
                    pass

        previous_worn: float | None = None
        for sample in accepted_samples:
            stamp = sample.timestamp.replace(second=0, microsecond=0).isoformat()
            context = (
                ("measurement_context", "minute_activity"),
                ("activity_type", sample.activity_name),
                ("activity_type_code", sample.activity_type),
                ("intensity", sample.intensity),
            )
            # Historical `steps` is the number recorded for that minute, unlike
            # the optional current-total characteristic above. Preserve the
            # distinction explicitly in context rather than pretending they are
            # interchangeable.
            points.append(DeviceMetricPoint("steps", float(sample.steps), stamp, source_type, sensor_id, (sensor_id,), context))
            points.append(DeviceMetricPoint("activity_level", float(sample.intensity), stamp, source_type, sensor_id, (sensor_id,), context))
            worn = 0.0 if sample.activity_type == ACTIVITY_TYPE_NOT_WORN else 1.0
            # Wear state changes slowly; retaining transitions preserves the
            # information without tripling every minute-history batch.
            if previous_worn is None or worn != previous_worn:
                points.append(DeviceMetricPoint("wear_state", worn, stamp, source_type, sensor_id, (sensor_id,), context))
                previous_worn = worn

        working = dict(state)
        working["seen"] = new_seen[-MAX_SEEN:]
        working["last_minutes_received"] = processed_minutes
        working["legacy_state"] = context_state
        batch = DeviceHistoryBatch.bounded(
            metric_points=points,
            sleep_records=_sleep_records(accepted_samples, sensor_id),
        )
        return DeviceHistoryFetch(
            batch,
            working,
            continue_after=CONTINUE_AFTER if more_pending else None,
        )
