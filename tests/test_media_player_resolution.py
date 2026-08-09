from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (
    ROOT / "custom_components/fitness/manager.py"
).read_text(encoding="utf-8")


def _resolver_block():
    start = MANAGER.index("def _feedback_media_player_ids")
    end = MANAGER.index("async def _async_speak", start)
    return MANAGER[start:end]


def test_configured_media_players_are_authoritative():
    block = _resolver_block()
    assert "configured = {" in block
    assert "candidates.add(entity_id)" in block
    assert "needs_room_replacement = False" in block


def test_area_less_configured_player_is_kept():
    block = _resolver_block()
    assert "if area_id is None or area_id == selected:" in block


def test_same_area_configured_player_is_kept_without_extra_room_players():
    block = _resolver_block()
    assert "if selected and needs_room_replacement:" in block
    # Room players are not added unconditionally.
    assert block.index("if selected and needs_room_replacement:") < block.index(
        'self._entities_in_selected_area("media_player")'
    )


def test_different_area_configured_player_triggers_room_replacement():
    block = _resolver_block()
    assert "needs_room_replacement = True" in block
    assert 'self._entities_in_selected_area("media_player")' in block


def test_media_player_still_requires_media_play():
    block = _resolver_block()
    assert "self._media_player_supports_media_play(state)" in block


def test_tts_service_call_is_blocking_until_accepted():
    start = MANAGER.index("async def _async_speak")
    end = MANAGER.index("async def _async_notify", start)
    block = MANAGER[start:end]
    assert '"tts",' in block
    assert '"speak",' in block
    assert "blocking=True" in block
