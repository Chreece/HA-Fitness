from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def test_all_fitness_tts_is_serialized():
    assert "self._tts_playback_lock = asyncio.Lock()" in MANAGER

    start = MANAGER.index("async def _async_speak")
    end = MANAGER.index("async def _async_notify", start)
    block = MANAGER[start:end]
    assert "async with self._tts_playback_lock:" in block


def test_tts_waits_for_actual_media_player_playback():
    start = MANAGER.index("async def _async_wait_for_tts_playback")
    end = MANAGER.index("async def _async_speak", start)
    block = MANAGER[start:end]

    assert 'state.state == "playing"' in block
    assert "saw_playing" in block
    assert "start_timeout: float = 5.0" in block
    assert "finish_timeout: float = 120.0" in block


def test_same_announcement_is_sent_to_all_players_before_waiting():
    start = MANAGER.index("async def _async_speak")
    end = MANAGER.index("async def _async_notify", start)
    block = MANAGER[start:end]

    loop_pos = block.index("for media_player in media_players:")
    wait_pos = block.index(
        "await self._async_wait_for_tts_playback(successful_players)"
    )
    assert loop_pos < wait_pos


def test_next_announcement_waits_until_current_speech_finishes():
    start = MANAGER.index("async def _async_speak")
    end = MANAGER.index("async def _async_notify", start)
    block = MANAGER[start:end]

    lock_pos = block.index("async with self._tts_playback_lock:")
    service_pos = block.index("await self.hass.services.async_call(")
    playback_pos = block.index(
        "await self._async_wait_for_tts_playback(successful_players)"
    )
    assert lock_pos < service_pos < playback_pos


def test_playback_wait_has_safety_timeouts():
    start = MANAGER.index("async def _async_wait_for_tts_playback")
    end = MANAGER.index("async def _async_speak", start)
    block = MANAGER[start:end]

    assert "start_deadline" in block
    assert "finish_deadline" in block
    assert "await asyncio.sleep(0.1)" in block
