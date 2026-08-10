from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_periodic_coaching_is_anchored_to_workout_clock():
    start = MANAGER.index("async def _async_periodic_live_announcements")
    end = MANAGER.index("def _tts_language_for_entity", start)
    block = MANAGER[start:end]
    assert "next_due = loop.time() + interval" in block
    assert "next_due += interval" in block
    assert "while next_due <= loop.time():" in block


def test_periodic_coaching_refreshes_latest_stats_before_ai():
    start = MANAGER.index("async def _async_periodic_live_announcements")
    end = MANAGER.index("def _tts_language_for_entity", start)
    block = MANAGER[start:end]
    calc = block.index("_compute_live_calculation_snapshot()")
    message = block.index("_async_periodic_live_message()")
    assert calc < message
