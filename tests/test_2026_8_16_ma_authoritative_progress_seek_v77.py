from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
MA = (ROOT / "custom_components/fitness/music/music_assistant.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_ma_queue_is_the_authoritative_progress_source():
    assert "def music_assistant_queue_state(entry: Any, player_id: str)" in MA
    assert 'corrected = getattr(queue, "corrected_elapsed_time")' in MA
    assert 'duration = float(getattr(current_item, "duration", 0) or 0)' in MA
    assert '"position": position' in MA
    assert '"duration": duration' in MA
    assert '"seekable": bool(active and duration > 0)' in MA


def test_ma_seek_uses_native_player_queue_seek():
    assert "async def async_seek_music_assistant(" in MA
    assert "await seeker(player_id, int(requested))" in MA
    assert 'await sender("player_queues/seek", queue_id=player_id, position=int(requested))' in MA


def test_ma_progress_and_seek_have_dedicated_authorized_websocket_routes():
    assert 'vol.Required("type"): "fitness/tv/music/ma/state"' in TV
    assert 'vol.Required("type"): "fitness/tv/music/ma/seek"' in TV
    assert 'music_assistant_queue_state(entry, player_id)' in TV
    assert 'async_seek_music_assistant(entry, player_id, msg.get("position", 0))' in TV
    assert 'async_register_command(hass, websocket_tv_music_ma_state)' in TV
    assert 'async_register_command(hass, websocket_tv_music_ma_seek)' in TV


def test_frontend_tracks_real_ma_queue_progress_and_seeks_ma():
    assert 'type:"fitness/tv/music/ma/state"' in FRONTEND
    assert 'type:"fitness/tv/music/ma/seek"' in FRONTEND
    assert '_startMAProgressSync()' in FRONTEND
    assert 'this._maProgressTimer = setInterval' in FRONTEND
    assert '_mediaProgressSnapshot(mediaContentId = this._currentMediaContentId)' in FRONTEND
    assert 'id.startsWith(FITNESS_MUSIC_PREFIXES.music_assistant)' in FRONTEND
    assert 'source:"music_assistant"' in FRONTEND
    assert 'if (!this._mediaProgressScrubbing) progress.value' in FRONTEND
    assert 'this._mediaProgressScrubbing = true' in FRONTEND


def test_frontend_revision_is_v77():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-138"' in DASHBOARD
