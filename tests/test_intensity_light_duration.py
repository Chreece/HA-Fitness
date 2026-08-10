from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def _intensity_block():
    start = MANAGER.index("async def _async_live_intensity_feedback")
    end = MANAGER.index("def _available_live_source_names", start)
    return MANAGER[start:end]


def test_intensity_is_single_three_second_color_cue():
    block = _intensity_block()
    assert "await asyncio.sleep(3.0)" in block
    assert "last_feedback_pulse_count = 1" in block
    assert "last_feedback_pulse_interval = 3.0" in block


def test_intensity_feedback_no_longer_blinks():
    block = _intensity_block()
    assert "for pulse_number" not in block
    assert "colour_seconds" not in block
    assert "original_seconds" not in block
    assert "60.0 / bpm" not in block


def test_intensity_restores_original_light_state():
    block = _intensity_block()
    assert "_async_snapshot_feedback_lights" in block
    assert "_async_restore_feedback_lights" in block
    assert "clear_snapshot=True" in block
