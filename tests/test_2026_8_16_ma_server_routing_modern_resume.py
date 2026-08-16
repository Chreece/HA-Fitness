from pathlib import Path

ROOT = Path(__file__).parents[1]
MUSIC = ROOT / "custom_components/fitness/music"
MA = (MUSIC / "music_assistant.py").read_text()
CATALOG = (MUSIC / "provider_catalog.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
README = (ROOT / "README.md").read_text()


def test_music_assistant_setup_targets_selected_server_not_ha_integration_page():
    assert 'MUSIC_ASSISTANT_MUSIC_PATH = "/#/music"' in MA
    assert 'MUSIC_ASSISTANT_PROVIDER_PATH = "/#/settings/providers?types=music"' in MA
    assert 'MUSIC_ASSISTANT_ADD_PROVIDER_PATH = "/#/settings/addprovider/{provider_id}"' in MA
    assert 'MUSIC_ASSISTANT_EDIT_PROVIDER_PATH = "/#/settings/editprovider/{instance_id}"' in MA
    assert 'data.get("url") or data.get("server_url")' in MA
    assert "music_assistant_music_url(selected)" in MA
    assert "music_assistant_provider_url(selected)" in MA
    assert "if music_assistant_is_addon(entry):" in MA
    assert 'return f"{MUSIC_ASSISTANT_ADDON_INGRESS}{route}"' in MA
    assert 'await sender("providers/manifests")' in MA
    assert "MUSIC_ASSISTANT_ADDON_INGRESS" in MA
    assert "/config/integrations/integration/music_assistant" not in MA
    assert "selected_account_id" in MA


def test_music_assistant_catalog_deep_links_existing_and_new_provider_instances():
    assert "get_provider_configs" in MA
    assert "music_assistant_edit_provider_url(entry, instance_ids[0])" in CATALOG
    assert "music_assistant_add_provider_url(entry, provider_id)" in CATALOG
    assert "provider_destination or ma_path" in CATALOG
    assert "if not ma_installed or not ma_path:" in CATALOG
    assert "return rows" in CATALOG


def test_external_music_provider_destinations_only_open_new_tab():
    assert "const _fitnessOpenExternal = (target) =>" in FRONTEND
    assert 'anchor.target = "_blank"' in FRONTEND
    assert 'anchor.rel = "noopener noreferrer"' in FRONTEND
    assert 'window.open(target, "_blank", "noopener,noreferrer")' not in FRONTEND
    assert FRONTEND.count('if (_fitnessOpenExternal(target)) return;') >= 2


def test_route_away_suspends_shared_media_and_resume_position_is_reused():
    assert "_suspendMusicForNavigation()" in FRONTEND
    assert 'void this._syncMediaState({media_content_id:mediaContentId, playing:false' in FRONTEND
    assert 'position:selectedMetadata.position || resolvedMetadata.position || 0' in FRONTEND
    assert 'async _resumeHtmlAudio(position)' in FRONTEND
    assert 'await this._resumeHtmlAudio(resumePosition)' in FRONTEND
    assert 'this._pendingHtmlAudioResumePosition = resumePosition;' in FRONTEND
    assert 'if (resumePosition > 0) playerVars.start = Math.floor(resumePosition)' in FRONTEND
    assert 'widget.seekTo?.(resumePosition * 1000)' in FRONTEND
    assert "async _resumeRuntimeConnection()" in FRONTEND
    assert "await this._subscribeTvMedia();" in FRONTEND


def test_fitness_tv_surfaces_use_modern_consistent_rounding():
    for phrase in (
        '.tv-toolbar{border-radius:24px',
        '.tv-card-slot{border-radius:22px',
        '.modal-card{border-radius:28px',
        'backdrop-filter:blur(8px)',
        '.profile-row{display:grid',
        'border-radius:22px',
    ):
        assert phrase in FRONTEND


def test_native_music_provider_policy_is_provider_specific_not_wholesale_copy():
    assert "does not by itself grant permission" in CATALOG
    assert "does **not** wholesale vendor every implementation" in README
    assert "Native Fitness adapters are therefore added provider-by-provider" in README


def test_frontend_revision_is_55():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert '?v=unreleased-82' in DASHBOARD
