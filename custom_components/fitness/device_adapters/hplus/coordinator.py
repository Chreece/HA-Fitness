"""Read-only direct daily-history synchronization for HPlus wearables."""
from __future__ import annotations

import asyncio
from datetime import datetime, time, timezone
from typing import Any

from ..history import DeviceHistoryBatch, DeviceMetricPoint
from ..history_coordinator import DeviceHistoryFetch, DirectHistoryCoordinator
from .protocol import (
    DATA_DAY_SUMMARY,
    DATA_DAY_SUMMARY_ALT,
    DAY_SUMMARY_LENGTH,
    HPLUS_CONTROL_UUID,
    HPLUS_MEASURE_UUID,
    build_day_history_request,
    parse_day_summary,
)

NOTIFY_QUEUE_LIMIT = 256
DAY_HISTORY_TIMEOUT = 8.0
DAY_HISTORY_IDLE_TIMEOUT = 1.25
MAX_DAY_PACKETS_PER_SESSION = 256
MAX_IMPORTED_DAYS = 64


class HPlusHistoryCoordinator(DirectHistoryCoordinator):
    """Fetch bounded daily summaries without changing HPlus device settings."""

    adapter_id = "hplus_history"
    sync_unique_suffix = "sync_hplus_health_history"
    sync_translation_key = "sync_device_health_history"
    sync_icon = "mdi:watch"

    async def async_fetch_history(
        self, client, state: dict[str, Any], *, sensor_id: str
    ) -> DeviceHistoryFetch:
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=NOTIFY_QUEUE_LIMIT)

        def _notify(_sender, data) -> None:
            payload = bytes(data)
            if len(payload) != DAY_SUMMARY_LENGTH or payload[0] not in {
                DATA_DAY_SUMMARY,
                DATA_DAY_SUMMARY_ALT,
            }:
                return
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

        await client.start_notify(HPLUS_MEASURE_UUID, _notify)
        await client.write_gatt_char(
            HPLUS_CONTROL_UUID,
            build_day_history_request(),
            response=False,
        )

        raw_packets: list[bytes] = []
        loop = asyncio.get_running_loop()
        hard_deadline = loop.time() + DAY_HISTORY_TIMEOUT
        first = True
        while len(raw_packets) < MAX_DAY_PACKETS_PER_SESSION:
            remaining = hard_deadline - loop.time()
            if remaining <= 0:
                break
            timeout = remaining if first else min(remaining, DAY_HISTORY_IDLE_TIMEOUT)
            try:
                async with asyncio.timeout(timeout):
                    payload = await queue.get()
            except TimeoutError:
                if first:
                    raise
                break
            first = False
            raw_packets.append(payload)

        # Multiple IDs can represent the same day. Keep the last packet for a
        # date, then select the newest bounded set irrespective of wire order.
        by_day = {}
        for payload in raw_packets:
            try:
                summary = parse_day_summary(payload)
            except ValueError:
                continue
            by_day[summary.day] = summary
        summaries = [by_day[key] for key in sorted(by_day)[-MAX_IMPORTED_DAYS:]]

        points: list[DeviceMetricPoint] = []
        source_type = "direct_hplus"
        now = datetime.now(timezone.utc)
        for summary in summaries:
            if summary.day == now.date():
                stamp = now.isoformat()
            else:
                stamp = datetime.combine(
                    summary.day, time(hour=12), tzinfo=timezone.utc
                ).isoformat()
            values = (
                ("steps", summary.steps),
                ("distance_m", summary.distance_m),
                ("calories", summary.calories),
                ("activity_minutes", summary.activity_minutes),
            )
            for metric, value in values:
                points.append(
                    DeviceMetricPoint(
                        metric,
                        float(value),
                        stamp,
                        source_type,
                        sensor_id,
                        (sensor_id,),
                    )
                )
            if 20 <= summary.max_heart_rate <= 260:
                points.append(
                    DeviceMetricPoint(
                        "max_hr",
                        float(summary.max_heart_rate),
                        stamp,
                        source_type,
                        sensor_id,
                        (sensor_id,),
                    )
                )
            if 20 <= summary.min_heart_rate <= 260:
                points.append(
                    DeviceMetricPoint(
                        "min_hr",
                        float(summary.min_heart_rate),
                        stamp,
                        source_type,
                        sensor_id,
                        (sensor_id,),
                    )
                )

        working = dict(state)
        working["reported_days"] = len(by_day)
        working["newest_reported_day"] = (
            summaries[-1].day.isoformat() if summaries else None
        )
        return DeviceHistoryFetch(
            DeviceHistoryBatch.bounded(metric_points=points),
            working,
        )
