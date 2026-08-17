from pathlib import Path

ROOT = Path(__file__).parents[1]
MUSIC = ROOT / "custom_components/fitness/music"
FACADE = (ROOT / "custom_components/fitness/music_adapters.py").read_text()
BASE = (MUSIC / "base.py").read_text()
REGISTRY = (MUSIC / "registry.py").read_text()
MA = (MUSIC / "music_assistant.py").read_text()
SPOTIFY = (MUSIC / "spotify.py").read_text()
YTDLP_ADAPTER = (MUSIC / "yt_dlp.py").read_text()
YOUTUBE = (MUSIC / "youtube.py").read_text()
YTDLP = (ROOT / "custom_components/fitness/music_ytdlp.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
STRINGS = (ROOT / "custom_components/fitness/strings.json").read_text()


def test_music_adapters_are_split_into_independent_files_and_facade_is_thin():
    expected = {
        "base.py", "registry.py", "radio_browser.py", "yt_dlp.py",
        "music_assistant.py", "spotify.py", "youtube.py", "soundcloud.py",
        "direct_url.py", "legacy_spotify.py", "provider_catalog.py",
    }
    assert expected <= {path.name for path in MUSIC.glob("*.py")}
    assert "class MusicAdapterInfo" in BASE
    assert "class MusicAssistantMusicAdapter" in MA
    assert "class SpotifyMusicAdapter" in SPOTIFY
    assert "class YTDLPMusicAdapter" in YTDLP_ADAPTER
    assert "class HomeAssistantMediaSourceAdapter" not in FACADE
    assert "from .music import" in FACADE


def test_active_adapter_registry_does_not_import_every_ha_media_source():
    assert "MusicAssistantMusicAdapter.async_create" in REGISTRY
    assert "SpotifyMusicAdapter.async_create" not in REGISTRY
    assert "RadioBrowserMusicAdapter" in REGISTRY
    assert "adapter for adapter in created if adapter is not None" in REGISTRY
    assert "HomeAssistantMediaSourceAdapter" not in REGISTRY
    assert 'if ytdlp_enabled and YTDLPMusicAdapter.available()' in REGISTRY
    assert "async_provider_catalog" in REGISTRY


def test_music_assistant_is_one_adapter_and_ha_spotify_is_not_a_false_browser_audio_adapter():
    assert 'adapter_id="music_assistant"' in MA
    assert "never one row per MA source" in MA
    assert 'hass.config_entries.async_entries("spotify")' in SPOTIFY
    assert 'adapter_id="spotify"' in SPOTIFY
    assert "SpotifyMusicAdapter.async_create" not in REGISTRY
    assert "account_options=account_options" in MA
    assert "account_options=account_options" in SPOTIFY
    assert "selected_account_id=selected" in MA
    assert "selected_account_id=selected" in SPOTIFY


def test_music_search_limit_is_profile_configurable_and_applied_to_ytdlp():
    assert "DEFAULT_MUSIC_SEARCH_LIMIT = 50" in BASE
    assert "MIN_MUSIC_SEARCH_LIMIT = 10" in BASE
    assert "MAX_MUSIC_SEARCH_LIMIT = 100" in BASE
    assert '"music_search_limit"' in TV
    assert 'vol.Optional("music_search_limit")' in TV
    assert 'limit=prefs.get("music_search_limit", DEFAULT_MUSIC_SEARCH_LIMIT)' in TV
    assert 'id="cfg-search-limit"' in FRONTEND
    assert 'min="10" max="100" step="10"' in FRONTEND
    assert 'f"ytsearch{limit}:{query}"' in YTDLP


def test_music_search_can_target_one_many_or_all_enabled_adapters():
    assert "async def async_search_music" in REGISTRY
    assert "asyncio.gather" in REGISTRY
    assert '"searched_adapters"' in REGISTRY
    assert 'vol.Required("type"): "fitness/tv/music/adapters"' in TV
    assert 'vol.Required("type"): "fitness/tv/music/search"' in TV
    assert 'vol.Optional("adapters", default=["all"]): [str]' in TV
    assert 'if "all" in requested_adapters:' in TV
    assert 'type:"fitness/tv/music/adapters"' in FRONTEND
    assert 'type:"fitness/tv/music/search"' in FRONTEND
    assert 'adapter?.can_search && adapter?.available !== false && adapter?.profile_enabled' in FRONTEND


def test_search_ui_has_visible_busy_state_scroll_and_adapter_selector():
    assert "_openMusicSearch()" in FRONTEND
    assert "_runMusicSearch(root)" in FRONTEND
    assert "music-search-working" in FRONTEND
    assert "l.music_search_working" in FRONTEND
    assert 'icon="mdi:loading" class="spin"' in FRONTEND
    assert "music_all_adapters" in FRONTEND
    assert "music-adapter-picker" in FRONTEND
    assert ".modal-card.music-search-modal" in FRONTEND
    assert ".modal-card.music-search-modal .music-search-form" in FRONTEND
    assert "overflow-y:auto!important" in FRONTEND
    assert ".modal-card.music-search-modal .music-adapter-picker{flex:0 0 auto" in FRONTEND


def test_direct_link_youtube_stays_normal_and_ytdlp_has_own_namespace():
    assert 'FITNESS_YTDLP_PREFIX = "fitness-ytdlp://"' in YTDLP_ADAPTER
    assert 'media_content_id.startswith(FITNESS_YTDLP_PREFIX)' in YTDLP_ADAPTER
    assert 'FITNESS_YOUTUBE_PREFIX = "fitness-youtube://"' in YOUTUBE
    assert 'media_content_id.startswith(FITNESS_YOUTUBE_PREFIX)' in YOUTUBE
    assert '"kind": "youtube"' in YOUTUBE
    assert 'FITNESS_MUSIC_PREFIXES.youtube' in FRONTEND
    assert "l.music_add_link_hint_v2" in FRONTEND


def test_seek_is_verified_for_html_audio_and_embedded_players():
    assert "async _seekHtmlAudio(requestedPosition)" in FRONTEND
    assert "audio.seekable?.length" in FRONTEND
    assert 'typeof audio.fastSeek === "function"' in FRONTEND
    assert 'throw new Error("This stream did not accept the seek request")' in FRONTEND
    assert "async _seekEmbeddedMedia(provider, requestedPosition)" in FRONTEND
    assert "controller.getCurrentTime" in FRONTEND
    assert "controller.getPosition" in FRONTEND
    assert 'setTimeout(() => this._sendMediaCommand("seek", {position:value}), 220)' in FRONTEND
    assert 'request.headers.get("Range")' in TV
    assert '"Accept-Encoding": "identity"' in TV
    assert '"Content-Range"' in TV
    assert '"Accept-Ranges"' in TV


def test_adapter_selection_account_choice_and_result_limit_are_per_fitness_profile():
    assert '"music_adapters"' in TV
    assert '"music_adapter_options"' in TV
    assert '"music_search_limit"' in TV
    assert "_sanitize_music_adapter_options" in TV
    assert 'data-config-music-adapter' in FRONTEND
    assert 'data-config-music-account' in FRONTEND
    assert 'music_adapter_options:musicAdapterOptions' in FRONTEND
    assert "Fitness stores no provider passwords or tokens" in DASHBOARD


def test_only_installed_active_adapters_and_separate_add_provider_catalog_are_rendered():
    assert 'result.adapters.filter((adapter) => adapter?.available !== false)' in FRONTEND
    assert 'musicAdapters.filter((adapter) => adapter?.available !== false' in FRONTEND
    assert "provider_catalog" in TV
    assert "_openMusicProviderCatalog" in FRONTEND
    assert "music_no_adapters" in FRONTEND


def test_fitness_tv_has_fullscreen_button_and_real_fullscreen_api():
    assert 'id="fullscreen"' in FRONTEND
    assert "requestFullscreen" in FRONTEND
    assert "document.exitFullscreen" in FRONTEND
    assert 'icon", active ? "mdi:fullscreen-exit" : "mdi:fullscreen"' in FRONTEND
    assert 'document.addEventListener("fullscreenchange"' in FRONTEND


def test_ytdlp_acknowledgement_is_strong_but_does_not_claim_impossible_absolute_immunity():
    for phrase in (
        "solely responsible",
        "applicable law",
        "service terms",
        "copyright/licensing",
        "maximum extent permitted by applicable law",
        "not legal advice",
    ):
        assert phrase in STRINGS
    assert "guaranteed immunity" not in STRINGS.lower()


def test_frontend_revision_is_53():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert '?v=unreleased-82' in DASHBOARD
