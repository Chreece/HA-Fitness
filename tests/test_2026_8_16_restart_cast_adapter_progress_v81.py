from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
MA = (ROOT / "custom_components/fitness/music/music_assistant.py").read_text(encoding="utf-8")
INIT = (ROOT / "custom_components/fitness/__init__.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_ma_queue_is_released_before_profile_unload_and_stale_relay_reuse():
    assert "async def async_stop_music_assistant_player" in MA
    assert 'await sender("player_queues/stop", queue_id=player_id)' in MA
    assert "async def async_release_profile_music" in TV
    assert "await async_stop_music_assistant_player(entry, player_id)" in TV
    assert "await hub.async_release_profile_music(" in INIT
    sendspin = TV[TV.index("async def websocket_tv_music_ma_sendspin"):TV.index("async def websocket_tv_music_ma_play")]
    assert "hub.is_audio_owner(profile_entry_id, client_id)" in sendspin
    assert "await async_stop_music_assistant_player(entry, client_id)" in sendspin


def test_cast_sessions_rearm_after_ha_backend_restart_instead_of_needing_manual_stop():
    assert 'vol.Required("type"): "fitness/tv/cast/rearm"' in TV
    assert "hub.expect_cast(profile_entry_id, entity_id)" in TV
    assert "hub.arm_cast_receiver(profile_entry_id)" in TV
    assert '_rearmExistingCastAfterReconnect(result = {}, previousTarget = "")' in FRONTEND
    assert 'type:"fitness/tv/cast/rearm"' in FRONTEND
    assert 'this._armLocalCastHandoff("ha_backend_reconnected")' in FRONTEND
    assert 'this._armLocalCastHandoff("ha_backend_reconnected")' in FRONTEND
    assert 'if (this._canControlProfile) setTimeout(() => void this._heartbeat(), 0);' in FRONTEND


def test_progress_clock_is_provider_specific_and_ytdlp_youtube_is_polled():
    assert '_mediaProgressSnapshot(mediaContentId = this._currentMediaContentId)' in FRONTEND
    assert 'source:"music_assistant"' in FRONTEND
    assert 'source:"html_audio"' in FRONTEND
    assert 'source:this._embeddedProvider' in FRONTEND
    assert '_startYouTubeProgressSync(player = this._embeddedController)' in FRONTEND
    assert 'this._embeddedProgressTimer = setInterval(sync, 500)' in FRONTEND
    assert 'this._mediaSeconds(player.getCurrentTime?.()' in FRONTEND
    assert 'this._mediaSeconds(player.getDuration?.()' in FRONTEND
    assert 'this._startYouTubeProgressSync(player);' in FRONTEND


def test_v81_revision_contract():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
