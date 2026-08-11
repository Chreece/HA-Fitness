from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
BUTTON = (ROOT / "custom_components/fitness/button.py").read_text()


def test_pause_resume_controls_exist_and_stop_remains_separate():
    assert "class PauseWorkoutButton" in BUTTON
    assert "class ResumeWorkoutButton" in BUTTON
    assert "class StopWorkoutButton" in BUTTON
    assert "async_pause_session" in BUTTON
    assert "async_resume_session" in BUTTON
    assert "async_stop_session" in BUTTON


def test_pause_excludes_sampling_and_calculated_live_state():
    assert "if self.session_paused:\n            return False" in MANAGER
    assert "self.session_active and not self.session_paused" in MANAGER
    assert "if self.session_paused:\n                    continue" in MANAGER


def test_active_duration_subtracts_pause_time():
    assert "self._session_paused_seconds" in MANAGER
    assert "(current - self._session_pause_started).total_seconds()" in MANAGER
    assert "(current - self.session_started).total_seconds() - paused" in MANAGER
    assert "duration = self.session_duration(now=stop_time)" in MANAGER


def test_pause_distance_and_segment_boundaries_are_excluded():
    assert "self._session_distance_excluded" in MANAGER
    assert "resumed_distance - self._pause_distance_raw" in MANAGER
    assert '"_segment": self._session_segment' in MANAGER
    assert "if a_segment == b_segment" in MANAGER


def test_pause_keeps_raw_live_publish_path():
    assert "Raw live sensors deliberately keep publishing while paused" in MANAGER
    assert "self._notify_live_throttled()" in MANAGER
