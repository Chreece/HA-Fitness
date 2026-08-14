"""Fitness-specific Home Assistant event-loop stall diagnostics."""
from __future__ import annotations

import logging
import sys
import threading
import time
import traceback
from typing import Any

_LOGGER = logging.getLogger(__name__)


class FitnessEventLoopWatchdog:
    """Capture Python stacks from a helper thread while HA's loop is stalled."""

    HEARTBEAT_SECONDS = 0.25
    STALL_SECONDS = 1.5
    DUMP_COOLDOWN_SECONDS = 20.0

    def __init__(self, hass: Any) -> None:
        self.hass = hass
        self._heartbeat = time.monotonic()
        self._loop_thread_id: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._heartbeat_handle = None
        self._last_dump = 0.0

    def start(self) -> None:
        """Start once from Home Assistant's event-loop thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._loop_thread_id = threading.get_ident()
        self._heartbeat = time.monotonic()
        self._stop.clear()
        self._schedule_heartbeat()
        self._thread = threading.Thread(
            target=self._run,
            name="fitness-event-loop-watchdog",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop without waiting on the helper thread."""
        self._stop.set()
        handle = self._heartbeat_handle
        self._heartbeat_handle = None
        if handle is not None:
            try:
                handle.cancel()
            except Exception:
                pass

    def _schedule_heartbeat(self) -> None:
        if self._stop.is_set():
            return
        self._heartbeat = time.monotonic()
        self._heartbeat_handle = self.hass.loop.call_later(
            self.HEARTBEAT_SECONDS, self._schedule_heartbeat
        )

    @staticmethod
    def _format_frame(frame) -> str:
        if frame is None:
            return "<no Python frame available>"
        return "".join(traceback.format_stack(frame)).rstrip()

    def _run(self) -> None:
        while not self._stop.wait(0.25):
            now = time.monotonic()
            age = now - self._heartbeat
            if age < self.STALL_SECONDS or now - self._last_dump < self.DUMP_COOLDOWN_SECONDS:
                continue
            self._last_dump = now
            frames = sys._current_frames()
            main_frame = frames.get(self._loop_thread_id) if self._loop_thread_id else None
            _LOGGER.error(
                "FITNESS_STALL_DETECTED event_loop_heartbeat_age=%.3fs\n"
                "FITNESS_STALL_MAINTHREAD_STACK_BEGIN\n%s\n"
                "FITNESS_STALL_MAINTHREAD_STACK_END",
                age,
                self._format_frame(main_frame),
            )
            # ANT/Fitness helper stacks are often the other half of a lock/GIL stall.
            for thread in threading.enumerate():
                if thread.ident is None or thread.ident == self._loop_thread_id:
                    continue
                name = thread.name.lower()
                if "fitness" not in name and "antplus" not in name and "ant+" not in name:
                    continue
                _LOGGER.error(
                    "FITNESS_STALL_WORKER_STACK name=%s ident=%s\n%s",
                    thread.name,
                    thread.ident,
                    self._format_frame(frames.get(thread.ident)),
                )
