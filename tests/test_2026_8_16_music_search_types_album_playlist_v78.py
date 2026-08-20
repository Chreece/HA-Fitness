from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUSIC = ROOT / "custom_components/fitness/music"
BASE = (MUSIC / "base.py").read_text(encoding="utf-8")
REGISTRY = (MUSIC / "registry.py").read_text(encoding="utf-8")
MA = (MUSIC / "music_assistant.py").read_text(encoding="utf-8")
RADIO = (MUSIC / "radio_browser.py").read_text(encoding="utf-8")
YTDLP = (MUSIC / "yt_dlp.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_music_search_has_persisted_multi_select_result_type_filters():
    for media_type in ("track", "album", "playlist", "artist", "radio", "podcast", "audiobook"):
        assert f'"{media_type}"' in BASE
    assert "MUSIC_SEARCH_MEDIA_TYPES" in REGISTRY
    assert "media_types: list[str] | None = None" in REGISTRY
    assert "media_types=selected_media_types" in REGISTRY
    assert '"media_types": selected_media_types' in REGISTRY
    assert '"music_search_types"' in TV
    assert 'vol.Optional("music_search_types"): [str]' in TV
    assert 'vol.Optional("media_types"): [str]' in TV
    assert "FITNESS_MUSIC_SEARCH_TYPES" in FRONTEND
    assert 'data-music-type=' in FRONTEND
    assert "music_search_types:types" in FRONTEND
    assert "media_types:types" in FRONTEND


def test_music_assistant_album_playlist_artist_results_are_native_playable_items():
    assert '("albums", "album")' in MA
    assert '("playlists", "playlist")' in MA
    assert '("artists", "artist")' in MA
    assert '"track", "album", "playlist", "artist"' in MA
    assert '"album": "mdi:album"' in MA
    assert '"playlist": "mdi:playlist-music"' in MA
    assert '"artist": "mdi:account-music"' in MA
    assert 'f"{FITNESS_MA_PREFIX}{quote(uri, safe=\'\')}"' in MA
    assert '"player_queues/play_media"' in MA


def test_ma_search_interleaves_media_type_groups_so_tracks_do_not_hide_collections():
    assert "grouped_rows: list[list[dict[str, Any]]] = []" in MA
    assert "grouped_rows.append(type_rows)" in MA
    assert "while len(rows) < limit and any(grouped_rows):" in MA
    assert "for group in grouped_rows:" in MA


def test_non_ma_adapters_respect_result_type_filter():
    assert '"radio" not in {str(item).strip().lower() for item in media_types}' in RADIO
    assert 'want_tracks = "track" in requested' in YTDLP
    assert 'want_playlists = "playlist" in requested' in YTDLP
    assert 'if not want_tracks and not want_playlists:' in YTDLP
    assert '"media_class": kind' in YTDLP
    assert '"media_class": "radio"' in TV


def test_search_type_labels_are_available_and_frontend_revision_bumped():
    for label in (
        "music_search_types",
        "music_type_tracks",
        "music_type_albums",
        "music_type_playlists",
        "music_type_artists",
        "music_type_radio",
        "music_type_podcasts",
        "music_type_audiobooks",
        "music_search_select_type",
    ):
        assert label in DASHBOARD
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-110"' in DASHBOARD
