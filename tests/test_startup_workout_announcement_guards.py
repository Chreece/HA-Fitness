from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_startup_workouts_are_baseline_only():
    assert "_external_workout_announcements_armed = False" in MANAGER
    assert "_async_arm_external_workout_announcements" in MANAGER
    assert "await asyncio.sleep(30)" in MANAGER


def test_provider_workouts_are_debounced():
    assert "_schedule_external_workout_recheck()" in MANAGER
    assert "_async_process_external_workout_after_settle" in MANAGER
    assert "await asyncio.sleep(8)" in MANAGER


def test_incomplete_workouts_cannot_reach_announcement_handler():
    start = MANAGER.index("async def _async_handle_new_workout")
    end = MANAGER.index("def age(", start)
    handler = MANAGER[start:end]
    assert "if not self._workout_has_real_information(workout):" in handler


def test_incomplete_workouts_cannot_reach_ai_prompt():
    start = MANAGER.index("def _workout_ai_prompt")
    end = MANAGER.index("async def _call_ai", start)
    prompt = MANAGER[start:end]
    assert "if not self._workout_has_real_information(workout):" in prompt


def test_external_debounce_is_cancelled_on_shutdown():
    assert "self._external_workout_debounce_task.cancel()" in MANAGER


def test_external_baseline_task_is_owned_and_cancelled_on_shutdown():
    assert "self._external_workout_baseline_task: asyncio.Task | None = None" in MANAGER
    assert "self._external_workout_baseline_task = self.hass.async_create_task(" in MANAGER
    shutdown_start = MANAGER.index("    async def async_shutdown")
    shutdown_end = MANAGER.index("    def add_listener", shutdown_start)
    shutdown = MANAGER[shutdown_start:shutdown_end]
    assert "self._external_workout_baseline_task.cancel()" in shutdown
