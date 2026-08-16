from pathlib import Path

ROOT = Path(__file__).parents[1]
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
MA = (ROOT / "custom_components/fitness/music/music_assistant.py").read_text()
CATALOG = (ROOT / "custom_components/fitness/music/provider_catalog.py").read_text()
REGISTRY = (ROOT / "custom_components/fitness/music/registry.py").read_text()


def test_heartbeat_restores_persisted_last_media_before_reply_after_ha_restart():
    assert "state = await hub.async_restore_last_media(profile_entry_id)" in TV
    assert '"playing": False' in TV
    assert '"last_media"' in TV


def test_returning_to_same_lovelace_card_recreates_runtime_subscriptions():
    assert "else if (this._hass && this._loaded && !this._loading) void this._resumeRuntimeConnection();" in FRONTEND
    assert "async _resumeRuntimeConnection()" in FRONTEND
    assert "await this._subscribeTvAudio();" in FRONTEND
    assert "await this._subscribeTvMedia();" in FRONTEND
    assert "await this._subscribeTvSettings();" in FRONTEND


def test_music_assistant_uses_real_hash_routes_and_live_provider_manifests():
    assert 'MUSIC_ASSISTANT_MUSIC_PATH = "/#/music"' in MA
    assert 'MUSIC_ASSISTANT_ADD_PROVIDER_PATH = "/#/settings/addprovider/{provider_id}"' in MA
    assert 'MUSIC_ASSISTANT_EDIT_PROVIDER_PATH = "/#/settings/editprovider/{instance_id}"' in MA
    assert 'await sender("providers/manifests")' in MA
    assert "music_assistant_music_provider_manifests(selected_entry)" in CATALOG


def test_ha_media_rows_have_visible_image_or_mdi_fallbacks():
    assert "_mediaItemVisual(item = {})" in FRONTEND
    assert "media-source-icon" in FRONTEND
    assert "_mediaItemIcon(item = {})" in FRONTEND


def test_ha_spotify_is_not_advertised_as_local_fitness_browser_audio():
    assert "SpotifyMusicAdapter.async_create" not in REGISTRY
    assert '"Spotify (Home Assistant)"' not in CATALOG
