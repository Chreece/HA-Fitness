"""Fitness-specific Home Assistant event-loop stall diagnostics."""
from __future__ import annotations

import logging
import sys
import threading
import time
import traceback
from typing import Any

from homeassistant.core import CoreState

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

    def _home_assistant_is_running(self) -> bool:
        """Return whether runtime stall diagnostics should be emitted."""
        return getattr(self.hass, "state", None) is CoreState.running

    @staticmethod
    def _stack_is_fitness_owned(stack: str) -> bool:
        """Return whether the blocked MainThread is executing Fitness code."""
        normalized = stack.replace("\\", "/")
        return "/custom_components/fitness/" in normalized

    @staticmethod
    def _stack_is_home_assistant_shutdown(stack: str) -> bool:
        """Return whether the captured MainThread is in HA shutdown."""
        normalized = stack.replace("\\", "/")
        return (
            "/homeassistant/core.py" in normalized
            and (" in async_stop\n" in normalized or "EVENT_HOMEASSISTANT_STOP" in normalized)
        )

    def _run(self) -> None:
        while not self._stop.wait(0.25):
            now = time.monotonic()
            age = now - self._heartbeat
            if age < self.STALL_SECONDS or now - self._last_dump < self.DUMP_COOLDOWN_SECONDS:
                continue
            # During startup/shutdown Home Assistant legitimately spends time in
            # integration lifecycle callbacks.  The watchdog exists to diagnose
            # runtime Fitness stalls, and must not make a different integration's
            # blocking shutdown look like a Fitness ERROR.
            if not self._home_assistant_is_running():
                continue

            self._last_dump = now
            frames = sys._current_frames()
            main_frame = frames.get(self._loop_thread_id) if self._loop_thread_id else None
            main_stack = self._format_frame(main_frame)

            # Be defensive even if HA has not changed CoreState yet: a blocking
            # EVENT_HOMEASSISTANT_STOP listener belongs to shutdown diagnostics,
            # not Fitness runtime diagnostics.
            if self._stack_is_home_assistant_shutdown(main_stack):
                continue

            if not self._stack_is_fitness_owned(main_stack):
                _LOGGER.warning(
                    "FITNESS_STALL_OBSERVED_EXTERNAL event_loop_heartbeat_age=%.3fs; "
                    "MainThread is not executing Fitness code\n"
                    "FITNESS_STALL_EXTERNAL_MAINTHREAD_STACK_BEGIN\n%s\n"
                    "FITNESS_STALL_EXTERNAL_MAINTHREAD_STACK_END",
                    age,
                    main_stack,
                )
                continue

            _LOGGER.error(
                "FITNESS_STALL_DETECTED event_loop_heartbeat_age=%.3fs\n"
                "FITNESS_STALL_MAINTHREAD_STACK_BEGIN\n%s\n"
                "FITNESS_STALL_MAINTHREAD_STACK_END",
                age,
                main_stack,
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
