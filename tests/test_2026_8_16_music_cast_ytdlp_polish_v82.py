from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
CONFIG_FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
YTDLP = (ROOT / "custom_components/fitness/music_ytdlp.py").read_text(encoding="utf-8")
YTDLP_ADAPTER = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text(encoding="utf-8")
MA = (ROOT / "custom_components/fitness/music/music_assistant.py").read_text(encoding="utf-8")
CATALOG = (ROOT / "custom_components/fitness/music/provider_catalog.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_playlist_controls_do_not_squash_now_playing_progress_grid():
    assert '<div class="music-button-strip">${musicTools}</div>' in FRONTEND
    assert '.music-controls{display:grid;grid-template-columns:auto minmax(280px,1fr)' in FRONTEND
    assert '.music-button-strip{display:flex;align-items:center' in FRONTEND
    assert 'width:min(420px,100%);max-width:420px' in FRONTEND
    assert 'width:min(300px,100%);max-width:300px' in FRONTEND


def test_music_assistant_configure_link_goes_to_root_settings_page():
    assert 'MUSIC_ASSISTANT_SETTINGS_PATH = "/#/settings"' in MA
    assert 'def music_assistant_settings_url' in MA
    assert 'setup_path=music_assistant_settings_url(entry)' in MA
    assert 'music_assistant_settings_url(selected_entry)' in CATALOG


def test_ytdlp_is_provider_managed_not_backend_tv_setting():
    assert 'vol.Optional(CONF_TV_YTDLP_ENABLED, default=False): bool' not in CONFIG_FLOW
    profile_configure = TV[TV.index('vol.Required("type"): "fitness/tv/profile/configure"'):TV.index('vol.Required("type"): "fitness/tv/music/ytdlp"')]
    assert 'vol.Optional("ytdlp_enabled"' not in profile_configure
    assert 'adapter?.id !== "yt_dlp"' not in FRONTEND
    assert 'if (ytdlpEnabled && !musicAdapters.includes("yt_dlp"))' not in FRONTEND
    assert 'data-ytdlp-toggle' in FRONTEND
    assert 'type:"fitness/tv/music/ytdlp"' in FRONTEND


def test_stop_cast_is_visible_only_for_the_cast_mode_that_is_actually_active():
    assert 'id="stop-cast" title="${_fitnessEscape(l.cast_stop)}" hidden' in FRONTEND
    assert 'id="cast-stop" hidden' in FRONTEND
    assert 'const castConnected = this._castState === "connected";' in FRONTEND
    assert 'const castPending = this._castState === "connecting";' in FRONTEND
    assert 'if (stopCast) { stopCast.hidden = true; stopCast.disabled = true; }' in FRONTEND
    assert 'if (modalHaStop) { modalHaStop.hidden = true; modalHaStop.disabled = true; }' in FRONTEND
    assert 'modalHaStart.disabled = castPending || (!castConnected' in FRONTEND
    assert 'startLabel.textContent = castConnected ? l.cast_stop' in FRONTEND


def test_ytdlp_playlist_search_uses_youtube_playlist_filter_and_is_playable():
    assert 'def search_youtube_playlists' in YTDLP
    assert 'sp=EgIQAw%253D%253D' in YTDLP
    assert '"noplaylist": False' in YTDLP
    assert 'want_playlists = "playlist" in requested' in YTDLP_ADAPTER
    assert 'marker = "playlist" if kind == "playlist" else "track"' in YTDLP_ADAPTER
    assert 'list_youtube_playlist_entries, target, 8' in YTDLP_ADAPTER
    assert 'resolve_youtube_audio, entry_target' in YTDLP_ADAPTER
    assert 'playable: list[tuple[dict[str, Any], Any]] = []' in YTDLP_ADAPTER
    assert 'if isinstance(resolved_item, Exception):' in YTDLP_ADAPTER
    assert '"playlist_items": playlist_items' in YTDLP_ADAPTER

def test_ytdlp_live_is_not_exposed_when_the_browser_audio_path_cannot_play_it():
    assert 'live_status == "is_live"' in YTDLP
    assert 'class FitnessYTDLPLiveStream' in YTDLP
    assert 'except (FitnessYTDLPError, FitnessYTDLPLiveStream):' in YTDLP_ADAPTER
    assert 'if is_upcoming:' in YTDLP
    assert 'if bool(row.get("is_live")):' in YTDLP_ADAPTER
    assert 'marker = "playlist" if kind == "playlist" else "track"' in YTDLP_ADAPTER
    assert 'if marker == "live":' in YTDLP_ADAPTER
    assert 'Live YouTube results are not exposed by the browser-playable yt-dlp adapter' in YTDLP_ADAPTER

def test_v82_revision_contract():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
