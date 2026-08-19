"""Read-only direct history synchronization for Ultrahuman Ring AIR."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import math
from statistics import mean
from typing import Any

from ..history import DeviceHistoryBatch, DeviceMetricPoint
from ..history_coordinator import DeviceHistoryFetch, DirectHistoryCoordinator
from .protocol import (
    OP_EARLIEST,
    OP_LATEST,
    OP_RECORDINGS,
    RESULT_NO_DATA,
    ULTRAHUMAN_COMMAND_NOTIFY_UUID,
    ULTRAHUMAN_COMMAND_WRITE_UUID,
    ULTRAHUMAN_STATE_CHAR_UUID,
    build_index_command,
    build_recordings_command,
    circular_distance,
    next_available_index,
    measurement_context,
    parse_device_state,
    parse_index_response,
    parse_recordings_response,
)

MAX_RECORDS_PER_SESSION = 256
NOTIFY_QUEUE_LIMIT = 64
COMMAND_TIMEOUT = 8.0
RECORDING_IDLE_TIMEOUT = 1.25
BACKLOG_CONTINUE_DELAY = 2 * 60.0
MAX_DAILY_AGGREGATES = 120


class UltrahumanAirCoordinator(DirectHistoryCoordinator):
    adapter_id = "ultrahuman_air"
    sync_unique_suffix = "sync_ultrahuman_health_history"
    sync_translation_key = "sync_device_health_history"
    sync_icon = "mdi:ring"

    async def _command_response(self, client, queue: asyncio.Queue[bytes], command: bytes, opcode: int) -> bytes:
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        await client.write_gatt_char(ULTRAHUMAN_COMMAND_WRITE_UUID, command, response=False)
        async with asyncio.timeout(COMMAND_TIMEOUT):
            while True:
                payload = await queue.get()
                if payload and payload[0] == opcode:
                    return payload

    @staticmethod
    def _update_daily(daily: dict[str, Any], record) -> str | None:
        timestamp = record.primary_timestamp
        if timestamp is None:
            return None
        key = timestamp.date().isoformat()
        agg = daily.setdefault(
            key,
            {
                "updated_at": timestamp.isoformat(),
                "steps": 0.0,
                "heart_rate_sum": 0.0,
                "heart_rate_count": 0,
                "hrv_ms_sum": 0.0,
                "hrv_ms_count": 0,
                "spo2_sum": 0.0,
                "spo2_count": 0,
                "skin_temperature_sum": 0.0,
                "skin_temperature_count": 0,
                "stress_sum": 0.0,
                "stress_count": 0,
                "activity_level_sum": 0.0,
                "activity_level_count": 0,
            },
        )
        agg["updated_at"] = max(str(agg.get("updated_at") or ""), timestamp.isoformat())
        if 0 <= record.steps <= 65535:
            agg["steps"] = float(agg.get("steps") or 0.0) + float(record.steps)
        for field, value, low, high in (
            ("heart_rate", record.heart_rate, 20, 260),
            ("hrv_ms", record.hrv_ms, 1, 1000),
            ("spo2", record.spo2, 50, 100),
            ("stress", record.stress, 1, 255),
            ("activity_level", record.activity_level, 1, 255),
        ):
            if low <= float(value) <= high:
                agg[f"{field}_sum"] = float(agg.get(f"{field}_sum") or 0.0) + float(value)
                agg[f"{field}_count"] = int(agg.get(f"{field}_count") or 0) + 1
        temperatures = [
            float(value)
            for value in (record.skin_temperature_min, record.skin_temperature_max)
            if math.isfinite(float(value)) and 10.0 <= float(value) <= 55.0
        ]
        if temperatures:
            agg["skin_temperature_sum"] = float(agg.get("skin_temperature_sum") or 0.0) + mean(temperatures)
            agg["skin_temperature_count"] = int(agg.get("skin_temperature_count") or 0) + 1
        return key

    @staticmethod
    def _record_points(records, sensor_id: str) -> list[DeviceMetricPoint]:
        """Preserve bounded timestamped Ring recordings instead of daily-only loss."""
        points: list[DeviceMetricPoint] = []
        source_type = "direct_ultrahuman_ring"
        for record in records:
            timestamp = record.primary_timestamp
            if timestamp is None:
                continue
            stamp = timestamp.isoformat()
            context_name = measurement_context(record.measurement_type)
            context = (("measurement_context", context_name), ("wear_state", "not_worn" if record.measurement_type == 100 else "worn"))
            values = []
            if 20 <= record.heart_rate <= 260:
                values.append(("heart_rate", record.heart_rate))
            if 1 <= record.hrv_ms <= 1000:
                values.append(("hrv_ms", record.hrv_ms))
            if 50 <= record.spo2 <= 100:
                values.append(("spo2", record.spo2))
            if 0 <= record.steps <= 65535:
                values.append(("steps", record.steps))
            if 1 <= record.activity_level <= 255:
                values.append(("activity_level", record.activity_level))
            if 1 <= record.stress <= 255:
                values.append(("stress", record.stress))
            temperatures = [
                float(value) for value in (record.skin_temperature_min, record.skin_temperature_max)
                if math.isfinite(float(value)) and 10.0 <= float(value) <= 55.0
            ]
            if temperatures:
                values.extend((
                    ("skin_temperature", mean(temperatures)),
                    ("skin_temperature_min", min(temperatures)),
                    ("skin_temperature_max", max(temperatures)),
                ))
            for metric, value in values:
                points.append(DeviceMetricPoint(metric, float(value), stamp, source_type, sensor_id, (sensor_id,), context))
        return points

    @staticmethod
    def _device_state_points(device_state, sensor_id: str) -> list[DeviceMetricPoint]:
        stamp = datetime.now(timezone.utc).isoformat()
        context = (("charging", device_state.charging),) if device_state.charging is not None else ()
        points: list[DeviceMetricPoint] = []
        if device_state.battery is not None:
            points.append(DeviceMetricPoint("battery", float(device_state.battery), stamp, "direct_ultrahuman_state", sensor_id, (sensor_id,), context))
        if device_state.device_temperature is not None:
            points.append(DeviceMetricPoint("device_temperature", float(device_state.device_temperature), stamp, "direct_ultrahuman_state", sensor_id, (sensor_id,), context))
        return points

    async def async_fetch_history(self, client, state: dict[str, Any], *, sensor_id: str) -> DeviceHistoryFetch:
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=NOTIFY_QUEUE_LIMIT)

        def _notify(_sender, data) -> None:
            payload = bytes(data)
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

        await client.start_notify(ULTRAHUMAN_COMMAND_NOTIFY_UUID, _notify)
        state_points: list[DeviceMetricPoint] = []
        try:
            device_state = parse_device_state(await client.read_gatt_char(ULTRAHUMAN_STATE_CHAR_UUID))
            state_points = self._device_state_points(device_state, sensor_id)
        except Exception:  # device-state read is optional; history must still sync
            device_state = None
        earliest_payload = await self._command_response(
            client, queue, build_index_command(OP_EARLIEST), OP_EARLIEST
        )
        result, earliest = parse_index_response(earliest_payload, OP_EARLIEST)
        if result == RESULT_NO_DATA or earliest is None:
            return DeviceHistoryFetch(DeviceHistoryBatch.bounded(metric_points=state_points), state)
        latest_payload = await self._command_response(
            client, queue, build_index_command(OP_LATEST), OP_LATEST
        )
        result, latest = parse_index_response(latest_payload, OP_LATEST)
        if result == RESULT_NO_DATA or latest is None:
            return DeviceHistoryFetch(DeviceHistoryBatch.bounded(metric_points=state_points), state)

        checkpoint = state.get("last_record_index")
        try:
            checkpoint = int(checkpoint) if checkpoint is not None else None
        except (TypeError, ValueError):
            checkpoint = None
        first = next_available_index(earliest, latest, checkpoint)
        if first is None:
            return DeviceHistoryFetch(DeviceHistoryBatch.bounded(metric_points=state_points), state)

        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        await client.write_gatt_char(
            ULTRAHUMAN_COMMAND_WRITE_UUID,
            build_recordings_command(first),
            response=False,
        )

        records = []
        seen: set[int] = set()
        reached_latest = False
        first_response = True
        while len(records) < MAX_RECORDS_PER_SESSION and not reached_latest:
            try:
                timeout = COMMAND_TIMEOUT if first_response else RECORDING_IDLE_TIMEOUT
                async with asyncio.timeout(timeout):
                    payload = await queue.get()
            except TimeoutError:
                if first_response:
                    raise
                break
            if not payload or payload[0] != OP_RECORDINGS:
                continue
            first_response = False
            result, batch = parse_recordings_response(payload)
            if result == RESULT_NO_DATA:
                break
            for record in batch:
                if record.index in seen:
                    continue
                # Ignore a response that predates the requested circular range.
                if circular_distance(first, record.index) > circular_distance(first, latest):
                    continue
                seen.add(record.index)
                records.append(record)
                if record.index == latest:
                    reached_latest = True
                    break
                if len(records) >= MAX_RECORDS_PER_SESSION:
                    break

        if not records:
            return DeviceHistoryFetch(DeviceHistoryBatch.bounded(metric_points=state_points), state)

        working = deepcopy(state)
        daily = deepcopy(working.get("daily")) if isinstance(working.get("daily"), dict) else {}
        touched: set[str] = set()
        for record in records:
            day = self._update_daily(daily, record)
            if day:
                touched.add(day)
        # Keep compact daily summaries in coordinator state; raw observations are imported through the bounded profile history.
        for day in sorted(daily)[:-MAX_DAILY_AGGREGATES]:
            daily.pop(day, None)
        working["daily"] = daily
        working["last_record_index"] = records[-1].index
        working["available_earliest_index"] = earliest
        working["available_latest_index"] = latest
        if device_state is not None:
            working["device_state"] = {
                "battery": device_state.battery,
                "charging": device_state.charging,
                "device_temperature": device_state.device_temperature,
            }
        points = self._record_points(records, sensor_id) + state_points
        has_more = records[-1].index != latest
        return DeviceHistoryFetch(
            DeviceHistoryBatch.bounded(metric_points=points),
            working,
            continue_after=BACKLOG_CONTINUE_DELAY if has_more else None,
        )
