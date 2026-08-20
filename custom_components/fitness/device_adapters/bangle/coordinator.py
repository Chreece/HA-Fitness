"""Bounded Bangle.js Health/Recorder sync and user-triggered workout delivery over NUS."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from homeassistant.components import bluetooth

from ..history import DeviceHistoryBatch
from ..history_coordinator import (
    CONNECT_TIMEOUT,
    SESSION_TIMEOUT,
    DeviceHistoryFetch,
    DirectHistoryCoordinator,
)
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
WORKOUT_FILE_CHUNK = 240
MAX_WORKOUT_FILE_BYTES = 48 * 1024
WORKOUT_FILE = "hafit.workout.json"
WORKOUT_APP_FILE = "hafit.app.js"
WORKOUT_INFO_FILE = "hafit.info"

# Normal synchronization executes only read operations. A workout write is a
# separate explicit user action and is bounded to the three HA-Fitness-owned
# files above. Health is the official module and Recorder files are the official
# recorder.log*.csv storage files.
_HEALTH_EXPR = r'''(function(){var o=[],h=require("health");h.readFullDatabase(function(r){if(o.length<2048)o.push({t:r.date.getTime(),steps:r.steps,bpm:r.bpm,bpmMin:r.bpmMin,bpmMax:r.bpmMax,battery:r.battery,charging:r.isCharging,temperature:r.temperature,altitude:r.altitude,activity:r.activity});});return o;})()'''
_LIST_RECORDER_EXPR = r'''require("Storage").list(/^recorder\.log.*\.csv$/,{sf:1}).slice(-32)'''

_WORKOUT_APP = r'''(function(){
var S=require("Storage"),w=S.readJSON("hafit.workout.json",1)||{},a=w.steps||[],i=0,r=0,run=0,t;
function sec(v){v=0|v;return v>0?(v>=3600?((v/3600)|0)+":"+(("0"+((v/60|0)%60)).substr(-2))+":"+(("0"+(v%60)).substr(-2)):((v/60)|0)+":"+(("0"+(v%60)).substr(-2))):"OPEN";}
function step(){return a[i]||{};}
function target(x){var q=x.target||{};return q.label||q.effort||q.zone||q.metric||"";}
function draw(){var x=step(),W=g.getWidth(),H=g.getHeight(),y=5;g.clear(1);g.setColor(g.theme.fg);g.setFontAlign(0,-1);g.setFont("6x8",1);g.drawString((w.sport||"FITNESS").toUpperCase()+"  "+(a.length?(i+1)+"/"+a.length:"0/0"),W/2,y);y+=15;g.setFont("6x8",2);var n=g.wrapString(x.name||w.name||"Workout",W-10).slice(0,2);g.drawString(n.join("\n"),W/2,y);y+=n.length*17+5;g.setFont("6x8",1);var d=g.wrapString(x.instruction||"No instruction",W-12).slice(0,5);g.drawString(d.join("\n"),W/2,y);y+=d.length*9+5;var tg=target(x);if(tg){g.setColor(g.theme.fg2);g.drawString("Target: "+tg,W/2,y);y+=11;g.setColor(g.theme.fg);}if(x.repetitions>1){g.drawString("Repeat x"+x.repetitions,W/2,y);y+=11;}g.setFont("Vector",Math.max(24,Math.min(42,(H-y-15)|0)));g.drawString(sec(r),W/2,Math.min(H-48,y+4));g.setFont("6x8",1);g.setColor(g.theme.fg2);g.drawString(run?"SWIPE step | PRESS pause":"SWIPE step | PRESS start",W/2,H-12);}
function load(n){if(!a.length){draw();return;}i=(n+a.length)%a.length;run=0;r=Math.max(0,0|step().duration_seconds);draw();}
function tick(){if(!run||r<=0)return;r--;draw();if(r<=0){run=0;Bangle.buzz(250);if(i<a.length-1)setTimeout(function(){load(i+1);},400);}}
t=setInterval(tick,1000);Bangle.setUI({mode:"leftright",remove:function(){if(t)clearInterval(t);}},function(d){if(d===undefined||d===0){if(r<=0&&step().duration_seconds)r=0|step().duration_seconds;run=!run;draw();return;}load(i+d);});load(0);
})()'''


def _bangle_workout_payload(prescription: dict[str, Any]) -> dict[str, Any]:
    """Keep only display/execution fields the watch app needs."""
    steps: list[dict[str, Any]] = []
    for item in list(prescription.get("steps") or [])[:64]:
        if not isinstance(item, dict):
            continue
        target = item.get("target") if isinstance(item.get("target"), dict) else {}
        target_label = ""
        for key in ("label", "effort", "zone", "metric", "value"):
            value = target.get(key)
            if value not in (None, "") and isinstance(value, (str, int, float)):
                target_label = str(value)[:64]
                break
        duration = item.get("duration_seconds")
        repetitions = item.get("repetitions")
        recovery = item.get("recovery_seconds")
        steps.append({
            "name": str(item.get("name") or "Step")[:120],
            "instruction": str(item.get("instruction") or "")[:300],
            "duration_seconds": max(0, min(86400, int(duration))) if isinstance(duration, (int, float)) else 0,
            "repetitions": max(1, min(100, int(repetitions))) if isinstance(repetitions, (int, float)) else 1,
            "recovery_seconds": max(0, min(86400, int(recovery))) if isinstance(recovery, (int, float)) else 0,
            "target": {"label": target_label} if target_label else {},
        })
    if not steps:
        raise ValueError("Workout has no executable steps")
    return {
        "schema_version": 1,
        "name": str(prescription.get("name") or "Fitness workout")[:160],
        "sport": str(prescription.get("sport") or "other")[:64],
        "steps": steps,
    }


def _read_file_expr(filename: str) -> str:
    encoded = json.dumps(str(filename))
    return f'''(function(fn){{var s=require("Storage").read(fn);return s===undefined?null:s;}})({encoded})'''


class BangleJsCoordinator(DirectHistoryCoordinator):
    adapter_id = "bangle_js"
    sync_unique_suffix = "sync_banglejs_full"
    sync_translation_key = "sync_device_data"
    sync_icon = "mdi:watch-import-variant"

    @staticmethod
    def _response_queue():
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=RX_QUEUE_LIMIT)

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

        return queue, _notify

    async def _eval_json_connected(self, client, queue: asyncio.Queue[bytes], expression: str) -> Any:
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        buffer = bytearray()
        command = f'print("{RESULT_PREFIX}"+JSON.stringify({expression}))\n'.encode()
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

    async def _eval_json(self, client, expression: str) -> Any:
        queue, notify = self._response_queue()
        await client.start_notify(NUS_TX_UUID, notify)
        try:
            return await self._eval_json_connected(client, queue, expression)
        finally:
            try:
                await client.stop_notify(NUS_TX_UUID)
            except Exception:
                pass

    async def _write_storage_file(self, client, queue: asyncio.Queue[bytes], filename: str, data: str) -> None:
        encoded = data.encode("ascii")
        if len(encoded) > MAX_WORKOUT_FILE_BYTES:
            raise ValueError("Bangle.js Fitness file exceeds safe size limit")
        if not encoded:
            raise ValueError("Bangle.js Fitness file is empty")
        for offset in range(0, len(data), WORKOUT_FILE_CHUNK):
            chunk = data[offset:offset + WORKOUT_FILE_CHUNK]
            name_js = json.dumps(filename)
            chunk_js = json.dumps(chunk)
            if offset == 0:
                expression = f'require("Storage").write({name_js},{chunk_js},0,{len(data)})'
            else:
                expression = f'require("Storage").write({name_js},{chunk_js},{offset})'
            if await self._eval_json_connected(client, queue, expression) is not True:
                raise RuntimeError(f"Bangle.js refused write to {filename}")

    async def async_write_workout(self, sensor_id: str, prescription: dict[str, Any]) -> dict[str, Any]:
        """Install one bounded Fitness workout locally on an assigned Bangle.js."""
        sensor_id = self.runtime.resolve_sensor_id(sensor_id)
        if not self._eligible(sensor_id):
            raise ValueError("Bangle.js is not accepted and assigned")
        if self.provider.sensor_connected(sensor_id) or self.provider.sensor_users(sensor_id):
            raise ValueError("Bangle.js is busy with another Fitness session")
        sensor = self.runtime.sensors.get(sensor_id)
        endpoint = sensor.endpoints.get("bluetooth") if sensor is not None else None
        if sensor is None or endpoint is None:
            raise ValueError("Bangle.js Bluetooth route is unavailable")
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, endpoint.address, connectable=True
        )
        if ble_device is None:
            raise ValueError("Bangle.js is not reachable through a connectable Bluetooth route")
        payload = _bangle_workout_payload(prescription)
        workout_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        info_json = json.dumps({
            "id": "hafit", "name": "HA Fitness", "type": "app",
            "src": WORKOUT_APP_FILE, "sortorder": 25,
        }, separators=(",", ":"))
        client = None
        lock = self.provider._connect_lock(sensor_id)
        try:
            async with asyncio.timeout(SESSION_TIMEOUT):
                async with lock:
                    if self.provider.sensor_connected(sensor_id) or self.provider.sensor_users(sensor_id):
                        raise ValueError("Bangle.js became busy before workout delivery")
                    async with asyncio.timeout(CONNECT_TIMEOUT):
                        client = await self.provider.establish_connection(
                            ble_device, sensor.name or endpoint.address, max_attempts=2
                        )
                    queue, notify = self._response_queue()
                    await client.start_notify(NUS_TX_UUID, notify)
                    try:
                        await self._write_storage_file(client, queue, WORKOUT_APP_FILE, _WORKOUT_APP)
                        await self._write_storage_file(client, queue, WORKOUT_INFO_FILE, info_json)
                        await self._write_storage_file(client, queue, WORKOUT_FILE, workout_json)
                        verify = await self._eval_json_connected(
                            client, queue,
                            f'(function(){{var S=require("Storage"),w=S.readJSON({json.dumps(WORKOUT_FILE)},1);return !!(w&&w.steps&&w.steps.length=={len(payload["steps"])});}})()'
                        )
                        if verify is not True:
                            raise RuntimeError("Bangle.js workout verification failed")
                    finally:
                        try:
                            await client.stop_notify(NUS_TX_UUID)
                        except Exception:
                            pass
        finally:
            if client is not None:
                await self.provider._async_disconnect_client(
                    client, reason="bangle_js workout delivery cleanup"
                )
        return {
            "device": "Bangle.js",
            "transport": "local_bluetooth",
            "workout_name": payload["name"],
            "steps": len(payload["steps"]),
            "launch": "Open HA Fitness from the Bangle.js launcher",
        }

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
