from pathlib import Path

ROOT = Path(__file__).parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
YTDLP = (ROOT / "custom_components/fitness/music_ytdlp.py").read_text()
YTDLP_ADAPTER = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
MANIFEST = (ROOT / "custom_components/fitness/manifest.json").read_text()


def test_now_playing_has_artwork_metadata_elapsed_duration_and_seek_slider():
    assert 'id="media-thumb"' in FRONTEND
    assert 'id="media-title"' in FRONTEND
    assert 'id="media-artist"' in FRONTEND
    assert 'id="media-current"' in FRONTEND
    assert 'id="media-progress"' in FRONTEND
    assert 'id="media-remaining"' in FRONTEND
    assert '_sendMediaCommand("seek"' in FRONTEND
    assert 'this._musicAudio.addEventListener("timeupdate"' in FRONTEND
    assert '_captureLocalMediaProgress' in FRONTEND
    assert 'remaining.textContent = hasSelection && duration > 0' in FRONTEND
    assert '? this._formatMediaTime(duration)' in FRONTEND


def test_shared_media_state_carries_metadata_and_progress_across_clients():
    for field in ('"artist"', '"thumbnail"', '"details"', '"position"', '"duration"'):
        assert field in TV
    assert 'position=state.get("position")' in TV
    assert 'duration=state.get("duration")' in TV
    assert 'artist=state.get("artist")' in TV
    assert 'thumbnail=state.get("thumbnail")' in TV


def test_sources_preserve_the_richest_metadata_available():
    assert 'resolved.artist' in YTDLP_ADAPTER
    assert 'resolved.thumbnail' in YTDLP_ADAPTER
    assert 'resolved.duration' in YTDLP_ADAPTER
    assert 'raw.get("favicon")' in TV
    assert 'getCurrentSound' in FRONTEND
    assert 'PLAY_PROGRESS' in FRONTEND
    assert 'media_artist' in FRONTEND
    assert 'media_duration' in FRONTEND


def test_settings_dialog_has_a_bounded_scroll_body_and_reachable_save_action():
    assert 'height:min(860px,calc(100dvh - 32px))' in FRONTEND
    assert '.configure-modal .profile-settings{min-height:0;overflow-y:auto' in FRONTEND
    assert 'scrollbar-gutter:stable' in FRONTEND
    assert '.configure-modal .settings-actions{position:sticky;bottom:0' in FRONTEND


def test_home_assistant_manages_a_musl_compatible_node_fallback_for_ytdlp():
    assert '"nodejs-wheel==24.16.0"' in MANIFEST
    assert '"deno==2.9.5"' not in MANIFEST
    assert 'importlib.import_module("deno")' in YTDLP
    assert 'find_deno_bin' in YTDLP
    assert '"managed": runtime in {"deno_managed", "node_managed"}' in YTDLP
    assert 'importlib.import_module("nodejs_wheel")' in YTDLP
    assert '"node": {"path": path}' in YTDLP
    assert 'nodejs-wheel==24.16.0' in MANIFEST


def test_frontend_revision_bumped_for_now_playing_and_scroll_fix():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert '?v=unreleased-82' in DASHBOARD
