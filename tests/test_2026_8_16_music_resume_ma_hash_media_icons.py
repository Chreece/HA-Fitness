from pathlib import Path

ROOT = Path(__file__).parents[1]
MA = (ROOT / "custom_components/fitness/music/music_assistant.py").read_text()
CATALOG = (ROOT / "custom_components/fitness/music/provider_catalog.py").read_text()
BASE = (ROOT / "custom_components/fitness/music/base.py").read_text()
YTDLP = (ROOT / "custom_components/fitness/music/yt_dlp.py").read_text()
YTDLP_CORE = (ROOT / "custom_components/fitness/music_ytdlp.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_music_assistant_uses_real_hash_routes_and_direct_provider_setup():
    assert 'MUSIC_ASSISTANT_MUSIC_PATH = "/#/music"' in MA
    assert 'MUSIC_ASSISTANT_PROVIDER_PATH = "/#/settings/providers?types=music"' in MA
    assert 'MUSIC_ASSISTANT_ADD_PROVIDER_PATH = "/#/settings/addprovider/{provider_id}"' in MA
    assert 'MUSIC_ASSISTANT_EDIT_PROVIDER_PATH = "/#/settings/editprovider/{instance_id}"' in MA
    assert "music_assistant_add_provider_url(entry, provider_id)" in CATALOG
    assert "music_assistant_edit_provider_url(entry, instance_ids[0])" in CATALOG
    assert '"setup_path": ma_settings_path if ma_installed' in CATALOG


def test_external_provider_navigation_never_falls_back_into_fitness_tab():
    assert "const _fitnessOpenExternal = (target) =>" in FRONTEND
    assert 'anchor.target = "_blank"' in FRONTEND
    assert 'anchor.rel = "noopener noreferrer"' in FRONTEND
    assert 'window.location.href = target' not in FRONTEND[FRONTEND.index("const _fitnessOpenExternal"):FRONTEND.index("const FITNESS_READINESS_TEXT")]
    assert 'window.open(target, "_blank", "noopener,noreferrer")' not in FRONTEND


def test_route_reattach_restores_runtime_subscriptions_for_all_music_types():
    assert "async _resumeRuntimeConnection()" in FRONTEND
    assert "else if (this._hass && this._loaded && !this._loading) void this._resumeRuntimeConnection();" in FRONTEND
    for phrase in ("await this._subscribeTvAudio();", "await this._subscribeTvMedia();", "await this._subscribeTvSettings();", "this._startHeartbeat();"):
        assert phrase in FRONTEND
    assert "_suspendMusicForNavigation()" in FRONTEND


def test_last_media_resume_point_is_persisted_only_when_paused():
    assert 'position = float(last_media.get("position") or 0)' in TV
    assert 'provided.get("playing") is False' in TV
    assert '"position": hub._media_seconds(provided.get("position"))' in TV
    assert 'position:this._mediaSeconds(this._lastMediaSnapshot.position)' in FRONTEND


def test_music_assistant_search_uses_authenticated_runtime_client():
    assert 'searcher = getattr(getattr(self._mass, "music", None), "search", None)' in MA
    assert 'providers=requested_scopes or None' in MA
    assert "\"media_content_id\": f\"{FITNESS_MA_PREFIX}{quote(uri, safe='')}\"" in MA
    assert '"can_play": media_type in {' in MA
    for media_type in ("track", "album", "playlist", "artist", "radio", "podcast", "audiobook"):
        assert f'"{media_type}"' in MA
    assert '"provider_instance": provider' in MA


def test_home_assistant_media_keeps_icons_and_has_media_class_fallbacks():
    assert '"icon": str(raw.get("icon") or "").strip()' in BASE
    assert '"media_class": str(raw.get("media_class") or "").strip()' in BASE
    assert "_mediaItemIcon(item = {})" in FRONTEND
    assert 'album:"mdi:album"' in FRONTEND
    assert 'playlist:"mdi:playlist-music"' in FRONTEND
    assert "media-external" in FRONTEND


def test_ytdlp_avoids_segmented_streams_and_falls_back_to_normal_youtube():
    assert 'bestaudio[protocol=https][ext=m4a]' in YTDLP_CORE
    assert 'any(token in protocol for token in ("m3u8", "dash", "ism"))' in YTDLP_CORE
    assert '"fallback_kind": "youtube"' in YTDLP
    assert '"fallback_url": target' in YTDLP
    assert 'String(resolved?.fallback_kind || "") === "youtube"' in FRONTEND
