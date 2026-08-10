from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_zone_must_remain_stable_for_ten_seconds():
    start = MANAGER.index("def _check_live_intensity_feedback")
    end = MANAGER.index("def _session_status_intensity", start)
    block = MANAGER[start:end]

    assert "self._candidate_live_intensity" in block
    assert "self._candidate_live_intensity_since" in block
    assert "< 10.0" in block


def test_zone_feedback_is_optical_only():
    start = MANAGER.index("async def _async_live_intensity_feedback")
    end = MANAGER.index("def _available_live_source_names", start)
    block = MANAGER[start:end]

    assert "_async_set_feedback_color" in block
    assert "await asyncio.sleep(3.0)" in block
    assert "_async_speak" not in block
    assert "_call_ai" not in block
    assert "_async_intensity_message" not in MANAGER


def test_diagnostics_publish_stability_values():
    assert '"intensity_zone_stability_seconds": 10' in MANAGER
    assert '"live_sample_max_hz": 1' in MANAGER
    assert '"live_entity_publish_max_hz": 2' in MANAGER
