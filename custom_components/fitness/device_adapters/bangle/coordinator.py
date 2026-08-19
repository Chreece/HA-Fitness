"""Bounded read-only Bangle.js Health + Recorder synchronization over NUS."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from ..history import DeviceHistoryBatch
from ..history_coordinator import DeviceHistoryFetch, DirectHistoryCoordinator
from .protocol import (
    MAX_HEALTH_ROWS,
    MAX_WORKOUTS,
    NUS_RX_UUID,
    NUS_TX_UUID,
    RESULT_PREFIX,
    health_batch,
    workout_from_recorder_csv,
)

RX_QUEUE_LIMIT = 512
EVAL_TIMEOUT = 18.0
MAX_RESULT_BYTES = 512 * 1024
WRITE_CHUNK = 20

# The watch executes only read operations. Health is the official module and
# Recorder files are the official recorder.log*.csv storage files.
_HEALTH_EXPR = r'''(function(){var o=[],h=require("health");h.readFullDatabase(function(r){if(o.length<2048)o.push({t:r.date.getTime(),steps:r.steps,bpm:r.bpm,bpmMin:r.bpmMin,bpmMax:r.bpmMax,battery:r.battery,charging:r.isCharging,temperature:r.temperature,altitude:r.altitude,activity:r.activity});});return o;})()'''
_LIST_RECORDER_EXPR = r'''require("Storage").list(/^recorder\.log.*\.csv$/,{sf:1}).slice(-32)'''


def _read_file_expr(filename: str) -> str:
    encoded = json.dumps(str(filename))
    return f'''(function(fn){{var s=require("Storage").read(fn);return s===undefined?null:s;}})({encoded})'''


class BangleJsCoordinator(DirectHistoryCoordinator):
    adapter_id = "bangle_js"
    sync_unique_suffix = "sync_banglejs_full"
    sync_translation_key = "sync_device_data"
    sync_icon = "mdi:watch-import-variant"

    async def _eval_json(self, client, expression: str) -> Any:
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=RX_QUEUE_LIMIT)
        buffer = bytearray()

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

        await client.start_notify(NUS_TX_UUID, _notify)
        command = f'print("{RESULT_PREFIX}"+JSON.stringify({expression}))\n'.encode()
        try:
            for offset in range(0, len(command), WRITE_CHUNK):
                await client.write_gatt_char(NUS_RX_UUID, command[offset:offset + WRITE_CHUNK], response=False)
                await asyncio.sleep(0)
            async with asyncio.timeout(EVAL_TIMEOUT):
                while True:
                    chunk = await queue.get()
                    buffer.extend(chunk)
                    if len(buffer) > MAX_RESULT_BYTES:
                        raise ValueError("Bangle.js response exceeds safe limit")
                    text = buffer.decode("utf-8", errors="ignore")
                    marker = text.find(RESULT_PREFIX)
                    if marker < 0:
                        continue
                    tail = text[marker + len(RESULT_PREFIX):]
                    line = tail.split("\n", 1)[0].strip().rstrip("\r")
                    if not line:
                        continue
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
        finally:
            try:
                await client.stop_notify(NUS_TX_UUID)
            except Exception:
                pass

    async def async_fetch_history(self, client, state: dict[str, Any], *, sensor_id: str) -> DeviceHistoryFetch:
        raw_health = await self._eval_json(client, _HEALTH_EXPR)
        rows = raw_health if isinstance(raw_health, list) else []
        batch = health_batch(rows[:MAX_HEALTH_ROWS], sensor_id=sensor_id)

        raw_files = await self._eval_json(client, _LIST_RECORDER_EXPR)
        filenames = [str(v) for v in raw_files if isinstance(v, str)][-MAX_WORKOUTS:] if isinstance(raw_files, list) else []
        seen = {str(v) for v in (state.get("recorder_files") or []) if isinstance(v, str)}
        workouts = []
        for filename in filenames:
            if filename in seen:
                continue
            raw_csv = await self._eval_json(client, _read_file_expr(filename))
            if not isinstance(raw_csv, str):
                continue
            workout = workout_from_recorder_csv(raw_csv, sensor_id=sensor_id, filename=filename)
            if workout is not None:
                workouts.append(workout)
            seen.add(filename)

        working = dict(state)
        working["recorder_files"] = sorted(seen)[-128:]
        working["health_rows"] = len(rows)
        working["recorder_files_seen"] = len(filenames)
        return DeviceHistoryFetch(batch, working, workouts=tuple(workouts))
