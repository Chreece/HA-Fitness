from pathlib import Path
import sys

from conftest import load_module

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")

feedback = load_module(
    "fitness_test_feedback_session",
    "feedback.py",
)


def test_static_start_messages_have_english_fallback():
    waiting = feedback.static_session_message("xx", "waiting_live")
    assert "Waiting for live sensor data" in waiting

    started = feedback.static_session_message(
        "en",
        "started_with_live",
        sensors=["Heart Rate", "Power"],
    )
    assert "Heart Rate" in started
    assert "Power" in started
    assert "timer has started" in started


def test_static_recovery_checkpoint_is_truthful():
    collected = feedback.static_session_message(
        "en",
        "recovery_checkpoint",
        seconds=30,
        remaining=90,
    )
    missing = feedback.static_session_message(
        "en",
        "recovery_checkpoint_missing",
        seconds=30,
        remaining=90,
    )
    assert "30-second" in collected
    assert "90 seconds remaining" in collected
    assert "No heart-rate value" in missing


def test_greek_session_guidance_exists():
    text = feedback.static_session_message(
        "el",
        "recovery_checkpoint",
        seconds=60,
        remaining=60,
    )
    assert "60" in text
    assert "Απομένουν" in text


def test_start_immediately_uses_existing_live_data_or_waits():
    assert "if self._has_valid_live_workout_data():" in MANAGER
    assert 'announcement_event="started_with_live"' in MANAGER
    assert 'self._queue_session_guidance("waiting_live")' in MANAGER


def test_first_later_live_data_announces_timer_start():
    assert 'announcement_event: str = "live_available"' in MANAGER
    assert "self._available_live_source_names()" in MANAGER


def test_recovery_checkpoints_are_spoken_and_nonblocking():
    start = MANAGER.index("async def _async_collect_heart_rate_recovery")
    end = MANAGER.index("def session_duration", start)
    recovery = MANAGER[start:end]

    # Recovery timing remains non-blocking: checkpoint speech is queued rather
    # than awaited inside the measurement loop.
    assert 'self._queue_session_guidance(' in recovery
    assert '"recovery_checkpoint"' in recovery
    assert "seconds=seconds" in recovery
    assert "remaining=remaining" in recovery
    assert "collected=(hr is not None)" in recovery

    # All four checkpoints remain present.
    assert '(10, "hrr_10s")' in recovery
    assert '(30, "hrr_30s")' in recovery
    assert '(60, "hrr_60s")' in recovery
    assert '(120, "hrr_120s")' in recovery

    # Completion is deliberately awaited after the 120-second collection so it
    # is heard before the final workout summary and cannot reorder behind it.
    assert 'await self._async_announce_session_guidance(' in recovery
    assert '"recovery_complete"' in recovery

def test_recovery_milestones_remain_for_collection_and_lights():
    assert '(10, "hrr_10s")' in MANAGER
    assert '(30, "hrr_30s")' in MANAGER
    assert '(60, "hrr_60s")' in MANAGER
    assert '(120, "hrr_120s")' in MANAGER
    assert "recovery_complete" in MANAGER


def test_workout_summary_is_deferred_until_recovery_finishes():
    assert "if not self.recovery_active and (" in MANAGER
    final = MANAGER.index(
        "# The completed workout evaluation/summary now sees all available"
    )
    assert "_async_handle_new_workout(latest)" in MANAGER[final:]


def test_external_provider_announcements_suppressed_during_recovery():
    start = MANAGER.index("def _schedule_external_workout_recheck")
    block = MANAGER[start:start+600]
    assert "if self.recovery_active:" in block
