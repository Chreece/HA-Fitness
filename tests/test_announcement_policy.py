from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_only_allowed_session_lifecycle_events_can_generate_speech():
    start = MANAGER.index("async def _async_session_guidance_message")
    end = MANAGER.index("async def _async_announce_session_guidance", start)
    block = MANAGER[start:end]

    for event in (
        "waiting_live",
        "started_with_live",
        "live_available",
        "stopped_without_live",
        "recovery_wait",
        "no_recovery",
    ):
        assert f'"{event}"' in block

    # Recovery milestones are visual-only.
    assert '"recovery_checkpoint",' in block.split("if event not in", 1)[1].split("}:", 1)[0]
    assert '"recovery_complete",' in block.split("if event not in", 1)[1].split("}:", 1)[0]


def test_recovery_loop_does_not_queue_checkpoint_or_final_tts():
    start = MANAGER.index("async def _async_collect_heart_rate_recovery")
    end = MANAGER.index("def session_duration", start)
    block = MANAGER[start:end]

    assert "recovery_complete" in block
    assert '"recovery_checkpoint"' in block
    assert "_queue_session_status_cue(" in block


def test_periodic_announcements_remain_supported():
    assert "async def _async_periodic_live_announcements" in MANAGER
    assert "CONF_PERIODIC_LIVE_ANNOUNCEMENTS" in MANAGER
