from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_session_ai_has_fast_static_fallback():
    start = MANAGER.index("async def _async_session_guidance_message")
    end = MANAGER.index("async def _async_announce_session_guidance", start)
    block = MANAGER[start:end]

    assert "asyncio.wait_for(" in block
    assert "timeout=2.5" in block
    assert "return fallback" in block
