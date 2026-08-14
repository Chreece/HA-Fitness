from pathlib import Path

M = Path("custom_components/fitness/manager.py").read_text()


def test_one_shot_started_listener_is_not_removed_twice():
    block = M[M.index("if self.hass.is_running:"):M.index("async def _async_post_start_setup")]
    assert "started_unsub = None" in block
    assert "self.remove_listeners.remove(started_unsub)" in block
    assert "async_create_background_task" in block
