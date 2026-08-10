from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_live_and_workout_provider_callbacks_are_separate():
    assert "def _async_live_source_change" in MANAGER
    assert "def _async_workout_source_change" in MANAGER
    assert "_async_source_change" not in MANAGER

    live_start = MANAGER.index("def _async_live_source_change")
    live_end = MANAGER.index("def _async_workout_source_change", live_start)
    live = MANAGER[live_start:live_end]

    assert "_schedule_external_workout_recheck" not in live
    assert "latest_workout()" not in live
    assert "evaluation()" not in live


def test_live_source_mapping_is_cached():
    assert "self._live_sources_cache" in MANAGER
    assert "self._live_candidates_cache" in MANAGER
    start = MANAGER.index("def live_values")
    end = MANAGER.index("def live_sources", start)
    block = MANAGER[start:end]
    assert "self._live_candidates_cache" in block
    assert "_switch_live_source_if_needed(metric)" in block


def test_live_samples_are_capped_at_one_hz():
    start = MANAGER.index("def _capture_sample")
    end = MANAGER.index("def _antplus_capture_switches", start)
    block = MANAGER[start:end]

    assert "loop_now - self._last_sample_monotonic < 1.0" in block
    assert "force: bool = False" in block
    assert "self._capture_sample(force=True)" in MANAGER


def test_live_entity_notifications_are_throttled():
    start = MANAGER.index("def _notify_live_throttled")
    end = MANAGER.index("def _async_live_source_change", start)
    block = MANAGER[start:end]

    assert "< 0.5" in block
    assert "_notify_live_throttled()" in MANAGER


def test_intensity_hot_path_does_not_run_full_evaluation():
    start = MANAGER.index("def _current_live_intensity")
    end = MANAGER.index("def _check_live_intensity_feedback", start)
    block = MANAGER[start:end]

    assert "self.evaluation()" not in block
    assert "self._session_intensity_max_hr" in block
    assert "self._session_intensity_resting_hr" in block
