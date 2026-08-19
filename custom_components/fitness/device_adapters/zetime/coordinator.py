"""Read-only direct history synchronization for MyKronoz ZeTime."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from ...providers.sleep import SleepRecord
from ..history import DeviceHistoryBatch, DeviceMetricPoint
from ..history_coordinator import DeviceHistoryFetch, DirectHistoryCoordinator
from .protocol import (
    SLEEP_AWAKE,
    SLEEP_AWAKE_BEGIN,
    SLEEP_BEGIN,
    SLEEP_DEEP,
    SLEEP_END,
    SLEEP_LIGHT,
    SUBJECT_ACTIVITY,
    SUBJECT_AVAILABILITY,
    SUBJECT_HEART_RATE,
    SUBJECT_SLEEP,
    TYPE_RESPONSE,
    ZETIME_PHONE_TO_WATCH_UUID,
    ZETIME_VALIDATE_NOTIFY_UUID,
    ZeTimeFrame,
    ZeTimeFrameBuffer,
    build_history_request,
    parse_activity,
    parse_availability,
    parse_heart_rate,
    parse_sleep,
)

MAX_ACTIVITY_PACKETS = 16
MAX_SLEEP_PACKETS = 32
MAX_HEART_PACKETS = 16
MAX_SEEN_SIGNATURES = 512
REQUEST_TIMEOUT = 5.0
ATT_CHUNK = 20


def _valid_epoch(value: int) -> datetime | None:
    if 946_684_800 <= int(value) <= 4_102_444_800:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    return None


class ZeTimeCoordinator(DirectHistoryCoordinator):
    adapter_id = "mykronoz_zetime"
    sync_unique_suffix = "sync_zetime_health_history"
    sync_translation_key = "sync_device_data"
    sync_icon = "mdi:watch"

    async def _send_frame(self, client, frame: bytes) -> None:
        for offset in range(0, len(frame), ATT_CHUNK):
            await client.write_gatt_char(
                ZETIME_PHONE_TO_WATCH_UUID,
                frame[offset : offset + ATT_CHUNK],
                response=False,
            )
        # ZeTime validates the staged message by writing 0x03 to 0x8002.
        await client.write_gatt_char(
            ZETIME_VALIDATE_NOTIFY_UUID, b"\x03", response=False
        )

    async def _request(
        self,
        client,
        queue: asyncio.Queue[ZeTimeFrame],
        subject: int,
        packet: int | None = None,
    ) -> ZeTimeFrame:
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        await self._send_frame(client, build_history_request(subject, packet))
        async with asyncio.timeout(REQUEST_TIMEOUT):
            while True:
                frame = await queue.get()
                if frame.subject != subject or frame.message_type != TYPE_RESPONSE:
                    continue
                if packet is not None and subject != SUBJECT_AVAILABILITY:
                    if len(frame.payload) < 2 or int.from_bytes(frame.payload[:2], "little") != int(packet):
                        continue
                return frame

    @staticmethod
    def _sleep_records(events, sensor_id: str) -> list[SleepRecord]:
        events = sorted(
            (event for event in events if _valid_epoch(event.timestamp) is not None),
            key=lambda event: (event.timestamp, event.packet),
        )
        records: list[SleepRecord] = []
        current = None
        stages: list[Any] = []
        for event in events:
            if event.sleep_type == SLEEP_BEGIN:
                current = event
                stages = []
                continue
            if current is None:
                continue
            if event.sleep_type == SLEEP_END:
                start_dt = _valid_epoch(current.timestamp)
                end_dt = _valid_epoch(event.timestamp)
                if start_dt is None or end_dt is None or end_dt <= start_dt:
                    current = None
                    stages = []
                    continue
                deep = light = awake = 0.0
                timeline = [item for item in stages if current.timestamp <= item.timestamp <= event.timestamp]
                for idx, item in enumerate(timeline):
                    next_ts = timeline[idx + 1].timestamp if idx + 1 < len(timeline) else event.timestamp
                    seconds = max(0.0, float(next_ts - item.timestamp))
                    if item.sleep_type == SLEEP_DEEP:
                        deep += seconds
                    elif item.sleep_type == SLEEP_LIGHT:
                        light += seconds
                    elif item.sleep_type in {SLEEP_AWAKE, SLEEP_AWAKE_BEGIN}:
                        awake += seconds
                duration = (end_dt - start_dt).total_seconds()
                records.append(
                    SleepRecord(
                        source="MyKronoz ZeTime",
                        provider_domain="direct_mykronoz_zetime",
                        start=start_dt.isoformat(),
                        end=end_dt.isoformat(),
                        observed_at=end_dt.isoformat(),
                        duration_s=duration,
                        time_in_bed_s=duration,
                        awake_s=awake if awake else None,
                        light_sleep_s=light if light else None,
                        deep_sleep_s=deep if deep else None,
                        in_bed=False,
                        sources=[sensor_id],
                        provider_domains=["direct_mykronoz_zetime"],
                        field_sources={
                            "start": sensor_id,
                            "end": sensor_id,
                            "deep_sleep_s": sensor_id,
                            "light_sleep_s": sensor_id,
                            "awake_s": sensor_id,
                        },
                    )
                )
                current = None
                stages = []
                continue
            if event.sleep_type in {SLEEP_DEEP, SLEEP_LIGHT, SLEEP_AWAKE, SLEEP_AWAKE_BEGIN}:
                stages.append(event)
        return records

    async def async_fetch_history(self, client, state: dict[str, Any], *, sensor_id: str) -> DeviceHistoryFetch:
        queue: asyncio.Queue[ZeTimeFrame] = asyncio.Queue(maxsize=32)
        buffer = ZeTimeFrameBuffer()

        def _notify(_sender, data) -> None:
            try:
                frames = buffer.feed(bytes(data))
            except ValueError:
                return
            for frame in frames:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    queue.put_nowait(frame)
                except asyncio.QueueFull:
                    pass

        await client.start_notify(ZETIME_VALIDATE_NOTIFY_UUID, _notify)
        activity_count, sleep_count, heart_count = parse_availability(
            await self._request(client, queue, SUBJECT_AVAILABILITY)
        )

        # Fetch only the newest bounded window.  The packet number echoed by the
        # response must match the request, so unsupported firmware fails safely.
        ranges = (
            (SUBJECT_ACTIVITY, activity_count, MAX_ACTIVITY_PACKETS),
            (SUBJECT_SLEEP, sleep_count, MAX_SLEEP_PACKETS),
            (SUBJECT_HEART_RATE, heart_count, MAX_HEART_PACKETS),
        )
        existing_seen = [
            str(value) for value in (state.get("seen") or [])[-MAX_SEEN_SIGNATURES:]
        ]
        seen = set(existing_seen)
        activities = []
        sleep_events = []
        heart = []
        new_seen = list(existing_seen)
        for subject, count, limit in ranges:
            count = max(0, min(int(count), 4096))
            start = max(0, count - limit)
            for packet in range(start, count):
                frame = await self._request(client, queue, subject, packet)
                if subject == SUBJECT_ACTIVITY:
                    item = parse_activity(frame)
                elif subject == SUBJECT_SLEEP:
                    item = parse_sleep(frame)
                else:
                    item = parse_heart_rate(frame)
                signature = f"{subject:02x}:{item.packet}:{item.timestamp}"
                already_seen = signature in seen
                if not already_seen:
                    seen.add(signature)
                    new_seen.append(signature)
                # Sleep reconstruction needs the entire bounded recent timeline,
                # including an already-seen BEGIN preceding a newly-seen END.
                if subject == SUBJECT_SLEEP:
                    sleep_events.append(item)
                elif already_seen:
                    continue
                elif subject == SUBJECT_ACTIVITY:
                    activities.append(item)
                else:
                    heart.append(item)

        points: list[DeviceMetricPoint] = []
        source_type = "direct_mykronoz_zetime"
        for item in activities:
            timestamp = _valid_epoch(item.timestamp)
            if timestamp is None:
                continue
            stamp = timestamp.isoformat()
            for metric, value in (
                ("steps", item.steps),
                ("calories", item.calories),
                ("distance_m", item.distance_m),
                ("activity_minutes", item.activity_minutes),
            ):
                points.append(DeviceMetricPoint(metric, float(value), stamp, source_type, sensor_id, (sensor_id,)))

        by_day: dict[str, list[int]] = {}
        for item in heart:
            timestamp = _valid_epoch(item.timestamp)
            if timestamp is None or not 20 <= item.heart_rate <= 260:
                continue
            by_day.setdefault(timestamp.date().isoformat(), []).append(item.heart_rate)
        for day, values in by_day.items():
            stamp = f"{day}T12:00:00+00:00"
            points.extend(
                (
                    DeviceMetricPoint("heart_rate", mean(values), stamp, source_type, sensor_id, (sensor_id,)),
                    DeviceMetricPoint("min_hr", min(values), stamp, source_type, sensor_id, (sensor_id,)),
                    DeviceMetricPoint("max_hr", max(values), stamp, source_type, sensor_id, (sensor_id,)),
                )
            )

        working = dict(state)
        working["seen"] = new_seen[-MAX_SEEN_SIGNATURES:]
        working["available_counts"] = {
            "activity": activity_count,
            "sleep": sleep_count,
            "heart_rate": heart_count,
        }
        sleeps = self._sleep_records(sleep_events, sensor_id)
        return DeviceHistoryFetch(
            DeviceHistoryBatch.bounded(metric_points=points, sleep_records=sleeps),
            working,
        )
