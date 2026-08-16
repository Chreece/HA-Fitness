from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
MA = (ROOT / "custom_components/fitness/music/music_assistant.py").read_text(encoding="utf-8")
YTDLP = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_music_search_supports_multi_selection_and_bulk_playlist_actions():
    assert "this._musicResultSelection = new Set()" in FRONTEND
    assert 'class="music-selection-bar"' in FRONTEND
    assert "music-selection-add" in FRONTEND
    assert "music-selection-play" in FRONTEND
    assert "media_content_ids:selected.map" in FRONTEND
    assert 'vol.Optional("media_content_ids", default=[]): [str]' in TV
    assert "async_play_music_assistant_uris" in TV
    assert 'media=uris' in MA


def test_fitness_user_playlists_are_profile_preferences_and_editable():
    assert '"user_playlists": self._sanitize_user_playlists' in TV
    assert 'vol.Optional("user_playlists"): [dict]' in TV
    assert "_saveUserPlaylists(playlists = this._userPlaylists || [])" in FRONTEND
    assert "_openUserPlaylists()" in FRONTEND
    assert "_editUserPlaylist(id = \"\")" in FRONTEND
    assert "playlist-up" in FRONTEND
    assert "playlist-down" in FRONTEND
    assert "playlist-delete" in FRONTEND


def test_playlist_transport_and_provider_browser_are_native_ma_queue_controls():
    assert 'f"player_queues/{action}"' in MA
    for command in (
        '"player_queues/shuffle"',
        '"player_queues/repeat"',
        '"music/playlists/playlist_tracks"',
        '"music/playlists/remove_playlist_tracks"',
    ):
        assert command in MA
    assert 'type:"fitness/tv/music/ma/queue"' in FRONTEND
    assert 'type:"fitness/tv/music/ma/playlist"' in FRONTEND
    assert 'type:"fitness/tv/music/ma/playlist/remove"' in FRONTEND
    for control in ("playlist-prev", "playlist-next", "playlist-shuffle", "playlist-repeat", "playlist-open"):
        assert control in FRONTEND


def test_all_search_adapters_preserve_or_resolve_thumbnails():
    # RadioBrowser uses each station favicon.
    assert '"thumbnail": str(raw.get("favicon") or "").strip()' in TV
    # yt-dlp returns provider thumbnails from search and resolve.
    assert '"thumbnail": str(row.get("thumbnail") or "").strip()' in YTDLP
    assert '"thumbnail": resolved.thumbnail' in YTDLP
    # MA consumes MediaItemImage/ItemMapping artwork, including the server-provided
    # opaque proxy_id used by Spotify mappings.
    assert 'proxy_id = str(_ma_value(image, "proxy_id", "") or "").strip()' in MA
    assert '/imageproxy/{quote(proxy_id, safe=\'\')}?size={size}&fmt=jpg' in MA
    assert '"thumbnail": _ma_image_url(entry, mass, item)' in MA


def test_playlist_labels_exist_for_english_and_greek_ui():
    for key in (
        "music_playlists",
        "music_new_playlist",
        "music_edit_playlist",
        "music_add_to_playlist",
        "music_open_playlist",
        "play_selected",
    ):
        assert DASH.count(f'"{key}"') >= 2
