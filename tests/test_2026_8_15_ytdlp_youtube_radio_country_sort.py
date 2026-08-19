from pathlib import Path

ROOT = Path(__file__).parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
YTDLP = (ROOT / "custom_components/fitness/music_ytdlp.py").read_text()
ADAPTERS = (ROOT / "custom_components/fitness/music_adapters.py").read_text()
BASE = (ROOT / "custom_components/fitness/music/base.py").read_text()
YTDLP_ADAPTER = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text()
YOUTUBE_ADAPTER = (ROOT / "custom_components/fitness/music/youtube.py").read_text()
CONFIG_FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
MANIFEST = (ROOT / "custom_components/fitness/manifest.json").read_text()
STRINGS = (ROOT / "custom_components/fitness/strings.json").read_text()
LEGACY_SPOTIFY = (ROOT / "custom_components/fitness/music/legacy_spotify.py").read_text()


def test_ytdlp_is_explicit_opt_in_with_strong_disclaimer_and_default_dependencies():
    assert 'CONF_TV_YTDLP_ENABLED = "tv_dashboard_ytdlp_enabled"' in (
        ROOT / "custom_components/fitness/const.py"
    ).read_text()
    assert 'vol.Optional(CONF_TV_YTDLP_ENABLED, default=False): bool' not in CONFIG_FLOW
    assert '"tv_dashboard_ytdlp_enabled": "Enable yt-dlp music adapter (experimental)"' in STRINGS
    assert "solely responsible" in STRINGS
    assert "maximum extent permitted by applicable law" in STRINGS
    assert "not legal advice" in STRINGS
    assert '"yt-dlp[default]==2026.7.4"' in MANIFEST


def test_ytdlp_is_a_music_adapter_and_search_returns_up_to_fifty_results():
    assert "YTDLP_SEARCH_LIMIT = 50" in YTDLP
    assert 'f"ytsearch{limit}:{query}"' in YTDLP
    assert "DEFAULT_MUSIC_SEARCH_LIMIT = 50" in BASE
    assert 'FITNESS_YTDLP_PREFIX = "fitness-ytdlp://"' in YTDLP_ADAPTER
    assert "class YTDLPMusicAdapter" in YTDLP_ADAPTER
    assert 'adapter_id="yt_dlp"' in YTDLP_ADAPTER
    assert "quote(f'{marker}|{target}', safe='')" in YTDLP_ADAPTER
    assert 'vol.Required("type"): "fitness/tv/music/search"' in TV
    assert 'type:"fitness/tv/music/search"' in FRONTEND
    assert 'data-source="search"' in FRONTEND
    assert "l.music_search_working" in FRONTEND


def test_ytdlp_search_results_use_real_audio_resolution_without_changing_direct_youtube_links():
    assert "resolve_youtube_audio" in YTDLP_ADAPTER
    assert 'media_content_id.startswith(FITNESS_YTDLP_PREFIX)' in YTDLP_ADAPTER
    assert 'hub._music_proxy_url(resolved.url, headers=resolved.headers)' in YTDLP_ADAPTER
    assert '"provider": "yt_dlp"' in YTDLP_ADAPTER
    assert "YOUTUBE_HOSTS = frozenset" in YTDLP
    assert "Only YouTube and YouTube Music URLs are accepted" in YTDLP
    assert 'key.lower() not in {"cookie", "authorization"}' in YTDLP

    assert 'media_content_id.startswith(FITNESS_YOUTUBE_PREFIX)' in YOUTUBE_ADAPTER
    assert '"kind": "youtube"' in YOUTUBE_ADAPTER
    assert '"provider": "youtube"' in YOUTUBE_ADAPTER
    assert 'FITNESS_MUSIC_PREFIXES.youtube' in FRONTEND


def test_spotify_link_no_longer_claims_direct_playback():
    assert "Spotify links are not directly playable by Fitness TV" in LEGACY_SPOTIFY
    assert "music_spotify_requires_provider" in FRONTEND
    assert 'lower.startsWith("spotify:") || lower.includes("open.spotify.com/")' in FRONTEND
    assert "Spotify-capable Home Assistant media adapter" in DASHBOARD


def test_profile_payload_and_inline_settings_expose_ytdlp_opt_in_and_adapter_selection():
    assert '"ytdlp_enabled": bool(manager.config.get(CONF_TV_YTDLP_ENABLED, False))' in DASHBOARD
    assert 'id="cfg-ytdlp"' not in FRONTEND
    assert 'data-ytdlp-toggle' in FRONTEND
    assert 'fitness/tv/music/ytdlp' in FRONTEND
    assert 'ytdlp_enabled:ytdlpEnabled' not in FRONTEND
    assert 'ytdlp_enabled:Boolean(settings.ytdlp_enabled)' not in FRONTEND
    assert 'adapter?.id !== "yt_dlp"' not in FRONTEND
    assert 'if (ytdlpEnabled && !musicAdapters.includes("yt_dlp"))' not in FRONTEND
    assert 'music_adapters:' in FRONTEND
    assert 'data-config-music-adapter' in FRONTEND


def test_radio_country_picker_sorts_localized_names_not_iso_codes():
    assert "_sortedRadioCountries()" in FRONTEND
    assert "new Intl.Collator([language]" in FRONTEND
    assert "display_name:this._radioCountryName(country.code)" in FRONTEND
    assert "this._sortedRadioCountries().map((country)" in FRONTEND
    assert "country.display_name || country.code" in FRONTEND


def test_frontend_cache_revision_bumped_for_adapter_music_ui():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-89"' in FRONTEND
    assert '?v=unreleased-89' in DASHBOARD
