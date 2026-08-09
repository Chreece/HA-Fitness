from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_lifecycle_color_mapping():
    for color, intensity in {
        "red": "near_maximal",
        "orange": "vigorous",
        "yellow": "moderate",
        "blue": "very_light",
        "green": "light",
    }.items():
        assert f'"{color}": "{intensity}"' in MANAGER


def test_no_live_data_holds_red_until_live_arrives():
    assert "def _queue_session_status_waiting_red" in MANAGER
    assert "Keep the original snapshot alive. Green-on-live will restore it." in MANAGER
    assert 'self._queue_session_status_waiting_red()' in MANAGER
    assert 'finish_waiting=(announcement_event == "live_available")' in MANAGER


def test_live_data_start_is_green_for_three_seconds_and_restores():
    assert "seconds=3.0" in MANAGER
    assert 'self._queue_session_status_cue(' in MANAGER
    assert '"green"' in MANAGER
    assert "await self._async_restore_feedback_lights(" in MANAGER


def test_lifecycle_feedback_suspends_intensity_pulses():
    start = MANAGER.index("def _check_live_intensity_feedback")
    block = MANAGER[start:start+500]
    assert "if self._session_status_light_active:" in block

    assert "self._feedback_generation += 1" in MANAGER
    assert "self._live_feedback_task.cancel()" in MANAGER


def test_intensity_feedback_resumes_after_start_green():
    assert "resume_intensity=True" in MANAGER
    assert "self._last_live_intensity = None" in MANAGER
    assert "self._check_live_intensity_feedback()" in MANAGER


def test_stop_and_recovery_colors():
    # Workout stop.
    assert 'self._queue_session_status_cue("red")' in MANAGER

    # Post-exercise checkpoints.
    for seconds, color in (
        (10, "orange"),
        (30, "yellow"),
        (60, "blue"),
        (120, "green"),
    ):
        assert f'{seconds}: "{color}"' in MANAGER


def test_recovery_cues_are_three_seconds_and_nonblocking():
    # The recovery measurement loop queues, rather than awaits, the light cue.
    start = MANAGER.index("async def _async_collect_heart_rate_recovery")
    end = MANAGER.index("def session_duration", start)
    recovery = MANAGER[start:end]

    assert "_queue_session_status_cue(" in recovery
    assert "await self._async_session_status_cue" not in recovery
    assert "seconds=3.0" in MANAGER


def test_feedback_uses_existing_available_color_capable_light_resolver():
    assert "light_ids = self._feedback_light_ids()" in MANAGER
