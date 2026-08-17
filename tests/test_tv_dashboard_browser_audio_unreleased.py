"""Fitness TV dashboard/browser-audio contracts."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components/fitness"
CONST = (BASE / "const.py").read_text(encoding="utf-8")
CONFIG = (BASE / "config_flow.py").read_text(encoding="utf-8")
DASHBOARD = (BASE / "dashboard.py").read_text(encoding="utf-8")
FRONTEND = (BASE / "frontend/fitness-dashboard.js").read_text(encoding="utf-8")
MANAGER = (BASE / "manager.py").read_text(encoding="utf-8")
TV = (BASE / "tv_dashboard.py").read_text(encoding="utf-8")
INIT = (BASE / "__init__.py").read_text(encoding="utf-8")
SERVICES = (BASE / "services.yaml").read_text(encoding="utf-8")
MUSIC = BASE / "music"
RADIO_ADAPTER = (MUSIC / "radio_browser.py").read_text(encoding="utf-8")
DIRECT_ADAPTER = (MUSIC / "direct_url.py").read_text(encoding="utf-8")
LEGACY_SPOTIFY_ADAPTER = (MUSIC / "legacy_spotify.py").read_text(encoding="utf-8")
SOUNDCLOUD_ADAPTER = (MUSIC / "soundcloud.py").read_text(encoding="utf-8")
YOUTUBE_ADAPTER = (MUSIC / "youtube.py").read_text(encoding="utf-8")
MUSIC_REGISTRY = (MUSIC / "registry.py").read_text(encoding="utf-8")


def _translation_files():
    return [BASE / "strings.json", *sorted((BASE / "translations").glob("*.json"))]


def test_tv_dashboard_is_opt_in_and_cast_target_is_native_cast_selector():
    assert 'CONF_TV_DASHBOARD_ENABLED = "tv_dashboard_enabled"' in CONST
    assert 'CONF_TV_MEDIA_PLAYER_ID = "tv_dashboard_media_player_id"' in CONST
    assert 'CONF_TV_DUCKING_PERCENT = "tv_dashboard_ducking_percent"' in CONST
    assert 'TV_DASHBOARD_PATH = "fitness-tv"' in CONST
    assert 'integration="cast"' in CONFIG
    assert 'domain="media_player"' in CONFIG
    assert 'return await self.async_step_tv_dashboard()' in CONFIG
    assert '"tv_dashboard"]' in CONFIG


def test_fitness_creates_sidebar_fullscreen_cast_dashboard_with_profile_specific_views():
    assert "async def async_ensure_tv_dashboard" in DASHBOARD
    assert 'CONF_SHOW_IN_SIDEBAR: True' in DASHBOARD
    assert 'expected_config = _tv_dashboard_expected_config(hass)' in DASHBOARD
    assert '"type": "sections"' not in DASHBOARD[DASHBOARD.index('def _tv_dashboard_view('):DASHBOARD.index('def _tv_dashboard_expected_config')]
    assert '_tv_dashboard_view_card(' in DASHBOARD
    assert 'profile_wrapper=profile_wrapper' in DASHBOARD
    assert '"grid_options"' not in DASHBOARD[DASHBOARD.index('def _tv_dashboard_view_card'):DASHBOARD.index('def _tv_dashboard_view(')]
    assert 'view["subview"] = True' in DASHBOARD
    assert 'path=f"profile-{entry.entry_id}"' in DASHBOARD
    assert 'profile_entry_id=entry.entry_id' in DASHBOARD
    assert '"custom:fitness-tv-dashboard-card"' in DASHBOARD
    assert 'strategy_type in {"custom:fitness-tv", "fitness-tv"}' in DASHBOARD
    assert 'current != expected_config' in DASHBOARD
    assert '"cast", "show_lovelace_view", cast_data, blocking=True' in DASHBOARD
    assert '"dashboard_path": TV_DASHBOARD_PATH' in DASHBOARD
    assert '"view_path": f"cast-{entry.entry_id}"' in DASHBOARD
    strategy_profile = FRONTEND[FRONTEND.index('for (const profile of profiles) {', FRONTEND.index('class FitnessTvDashboardStrategy')):FRONTEND.index('return {title, views};', FRONTEND.index('class FitnessTvDashboardStrategy'))]
    assert 'panel:true' not in strategy_profile
    assert 'FITNESS_TV_CAST_RECEIVER' in FRONTEND
    assert 'host === "cast.home-assistant.io"' in FRONTEND
    assert ':host([fitness-cast-receiver])' in FRONTEND
    assert 'position:fixed;inset:0' in FRONTEND
    assert 'height:100vh' in FRONTEND
    assert 'sidebar_icon="mdi:television-play"' in DASHBOARD
    assert 'update=frontend.async_panel_exists(hass, TV_DASHBOARD_PATH)' in DASHBOARD


def test_card_selection_is_per_profile_and_persisted_server_side():
    assert 'TV_STORE_KEY = "fitness.tv_dashboard"' in TV
    assert 'self._data["profiles"][profile_entry_id] = updated' in TV
    assert 'await self._store.async_save(self._data)' in TV
    assert 'type:"fitness/tv/preferences"' in FRONTEND
    assert 'type:"fitness/tv/preferences/save"' in FRONTEND
    assert 'profile_entry_id:this._profile.entry_id' in FRONTEND
    assert 'FITNESS_TV_CARD_CATALOG' in FRONTEND
    assert 'class="tv-profile-identity"' in FRONTEND
    assert 'id="cards"' in FRONTEND
    assert 'configuredProfile = String(this.config?.profile_entry_id || "")' in FRONTEND



def test_tv_dashboard_cast_button_lists_native_cast_targets_and_casts_selected_profile():
    assert 'def _tv_cast_targets' in DASHBOARD
    assert 'registry_entry.platform != "cast"' in DASHBOARD
    assert '"cast_targets": _tv_cast_targets(hass, registry)' in DASHBOARD
    assert 'this._castTargets = Array.isArray(data?.cast_targets)' in FRONTEND
    assert 'id="cast"' in FRONTEND
    assert 'id="cast-target"' in FRONTEND
    assert 'id="cast-now"' in FRONTEND
    assert 'this._hass.callService("fitness", "cast_tv_dashboard"' in FRONTEND
    assert 'config_entry_id:this._profile.entry_id' in FRONTEND
    assert 'entity_id:entityId' in FRONTEND
    assert 'media_player_override' in DASHBOARD
    assert 'CAST_APP_ID_HOMEASSISTANT_LOVELACE' in DASHBOARD
    assert 'for attempt in range(1, 4)' in DASHBOARD
    assert '_async_cast_receiver_is_stable' in DASHBOARD
    assert 'state is None or state.state == "unavailable"' not in DASHBOARD
    assert 'state is None or state.state in {"off", "standby", "unknown", "unavailable"}' in DASHBOARD
    assert 'Fitness TV cast requested for profile %s to %s' in DASHBOARD
    assert 'Fitness TV cast attempt %d/3 to %s failed' in DASHBOARD
    assert 'async _openCastPicker()' in FRONTEND
    assert 'if (Array.isArray(data?.cast_targets)) this._castTargets = data.cast_targets' in FRONTEND
    assert 'target.available === false ? "disabled"' in FRONTEND
    for label in (
        "cast_dashboard", "cast_dashboard_title", "cast_to", "cast_now",
        "cast_default", "cast_unavailable", "cast_no_targets",
        "cast_connecting", "cast_sent", "cast_failed",
    ):
        assert f'"{label}":' in DASHBOARD

def test_music_uses_home_assistant_media_source_inside_dashboard_browser():
    assert 'type:"media_source/browse_media"' in FRONTEND
    assert 'type:"media_source/resolve_media"' in FRONTEND
    assert 'this._musicAudio = new Audio()' in FRONTEND
    assert 'this._ttsAudio = new Audio()' in FRONTEND
    assert 'id="play"' in FRONTEND
    assert 'id="pause"' in FRONTEND
    assert 'id="browse"' in FRONTEND
    assert 'await this._musicAudio.play()' in FRONTEND
    assert 'this._hardStopMusic()' in FRONTEND
    assert 'audio.removeAttribute("src")' in FRONTEND
    assert 'audio.load()' in FRONTEND


def test_tv_tts_ducks_music_and_never_uses_cast_player_as_direct_tts_target():
    assert 'generate_media_source_id' in TV
    assert 'TV_AUDIO_EVENT = "fitness_tv_audio"' in TV
    assert 'ducking_percent' in TV
    assert 'await this._rampMusicVolume(originalVolume * duck, 300)' in FRONTEND
    assert 'await this._rampMusicVolume(originalVolume, 500)' in FRONTEND
    assert 'await this._ttsAudio.play()' in FRONTEND
    assert 'type:"fitness/tv/ack"' in FRONTEND

    # Protect the dashboard receiver even if room replacement discovers it.
    assert 'configured.discard(protected_tv_target)' in MANAGER
    assert 'if protected_tv_target and entity_id == protected_tv_target:' in MANAGER
    assert 'hub.async_speak(' in MANAGER


def test_workout_start_casts_without_blocking_workout_startup():
    start = MANAGER.index("async def async_start_session")
    body = MANAGER[start : start + 5000]
    assert 'self.hass.async_create_task(self.async_cast_tv_dashboard())' in body
    assert 'await self.async_cast_tv_dashboard()' not in body


def test_manual_cast_action_is_registered_and_translated():
    assert 'SERVICE_CAST_TV_DASHBOARD = "cast_tv_dashboard"' in CONST
    assert 'SERVICE_STOP_TV_DASHBOARD = "stop_tv_dashboard"' in CONST
    assert 'SERVICE_CAST_TV_DASHBOARD' in INIT
    assert 'SERVICE_STOP_TV_DASHBOARD' in INIT
    assert 'cast_tv_dashboard:' in SERVICES
    assert 'stop_tv_dashboard:' in SERVICES
    assert 'vol.Optional("entity_id")' in INIT
    assert 'manager.async_cast_tv_dashboard(' in INIT
    assert 'manager.async_stop_tv_dashboard(' in INIT
    assert 'this._hass.callService("fitness", "stop_tv_dashboard"' in FRONTEND
    assert 'id="cast-stop"' in FRONTEND
    assert '_async_stop_existing_ha_cast_receiver' in DASHBOARD
    assert '"media_player", "turn_off"' in DASHBOARD
    for path in _translation_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        service = data["services"]["cast_tv_dashboard"]
        assert service["name"]
        assert service["description"]
        assert service["fields"]["config_entry_id"]["name"]
        assert service["fields"]["config_entry_id"]["description"]
        assert service["fields"]["entity_id"]["name"]
        stop_service = data["services"]["stop_tv_dashboard"]
        assert stop_service["name"]
        assert stop_service["description"]
        assert stop_service["fields"]["config_entry_id"]["name"]
        assert stop_service["fields"]["entity_id"]["name"]


def test_tv_setup_and_dashboard_strings_are_localized_everywhere():
    required_labels = {
        "tv_dashboard",
        "tv_profile",
        "add_cards",
        "card_picker",
        "play",
        "pause",
        "media_browser",
        "now_playing",
        "nothing_playing",
        "tv_no_profiles",
    }
    for path in _translation_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ("config", "options"):
            step = data[section]["step"]["tv_dashboard"]
            assert step["title"]
            assert step["description"]
            for key in (
                "tv_dashboard_enabled",
                "tv_dashboard_media_player_id",
                "tv_dashboard_ducking_percent",
            ):
                assert step["data"][key]
                assert step["data_description"][key]

    # Runtime dashboard labels are bundled for every language supported by Fitness.
    for lang in ("en", "el", "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "uk", "tr", "zh", "ja", "ko"):
        marker = f'    "{lang}": {{"tv_dashboard"'
        assert marker in DASHBOARD
    for label in required_labels:
        assert f'"{label}":' in DASHBOARD


def test_tv_audio_core_has_no_required_extra_ha_integration_and_dashboard_revision_is_current():
    runtime = "\n".join(
        (BASE / name).read_text(encoding="utf-8")
        for name in ("__init__.py", "config_flow.py", "dashboard.py", "manager.py", "tv_dashboard.py")
    ) + "\n" + FRONTEND
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert '?v=unreleased-82' in DASHBOARD
    assert 'fitness/tv/music/browse' in runtime
    assert 'FITNESS_RADIO_PREFIX = "fitness-radio://"' in RADIO_ADAPTER
    # SoundCloud/YouTube helpers are loaded only when selected; account-backed
    # providers are imported through Home Assistant media adapters instead.
    assert 'async _spotifyApi()' not in FRONTEND
    assert 'open.spotify.com/embed/iframe-api/v1' not in FRONTEND
    assert 'async _soundCloudApi()' in FRONTEND
    assert 'async _youtubeApi()' in FRONTEND
    assert 'fitness/tv/music/adapters' in runtime
    assert 'fitness/tv/music/search' in runtime


def test_tv_frontend_resource_is_cross_origin_safe_for_home_assistant_cast():
    assert 'class FitnessDashboardResourceView(HomeAssistantView):' in DASHBOARD
    assert 'requires_auth = False' in DASHBOARD
    assert 'cors_allowed = True' in DASHBOARD
    assert '"Cross-Origin-Resource-Policy": "cross-origin"' in DASHBOARD
    assert '_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"' in DASHBOARD
    assert 'FitnessDashboardResourceView(frontend_path / "fitness-dashboard.js")' in DASHBOARD
    assert 'await asyncio.to_thread(self._frontend_file.read_bytes)' in DASHBOARD
    resource_class = DASHBOARD.split('class FitnessDashboardResourceView(HomeAssistantView):', 1)[1].split('_PACE_TEXT', 1)[0]
    assert 'async def options(' not in resource_class
    assert 'source.read_bytes()' not in resource_class


def test_cast_launch_does_not_loop_after_receiver_has_started():
    assert 'async def _async_wait_for_cast_receiver_launch(' in DASHBOARD
    assert 'Do not continuously tear down/relaunch a receiver that has already started.' in DASHBOARD
    assert 'Fitness TV Cast receiver active on %s for profile %s (%s)' in DASHBOARD


def test_toolbar_exposes_direct_stop_cast_control():
    assert 'id="stop-cast"' in FRONTEND
    assert 'mdi:cast-off' in FRONTEND
    assert 'const activeTarget = String(this._activeCastTarget || "")' in FRONTEND
    assert 'this._stopCastDashboard(activeTarget)' in FRONTEND


def test_tv_music_commands_prefer_cast_receiver_and_profiles_are_independent():
    assert 'TV_MEDIA_EVENT = "fitness_tv_media"' in TV
    assert 'TV_MEDIA_STATE_EVENT = "fitness_tv_media_state"' in TV
    assert 'vol.Required("type"): "fitness/tv/media_command"' in TV
    assert 'vol.Required("type"): "fitness/tv/media_state"' in TV
    assert 'is_cast_receiver = bool(msg.get("is_cast_receiver", False))' in TV
    assert 'def active_cast_client(' in TV
    assert 'self._expected_cast: dict[str, str] = {}' in TV
    assert 'self._expected_cast[profile_entry_id] = media_player' in TV
    assert 'expect_cast = self.has_cast_expectation(profile_entry_id)' in TV
    assert 'hub.expect_cast(entry.entry_id, media_player)' in DASHBOARD
    assert 'await hub.async_mark_cast_inactive(' in DASHBOARD
    assert 'is_cast_receiver:FITNESS_TV_CAST_RECEIVER' in FRONTEND
    assert 'type:"fitness/tv/media_command"' in FRONTEND
    assert 'payload.client_id !== FITNESS_TV_CLIENT_ID' in FRONTEND


def test_tv_music_uses_absolute_home_assistant_media_urls_on_cast_receiver():
    assert '_resolvedMediaUrl(url)' in FRONTEND
    assert 'typeof this._hass?.hassUrl === "function"' in FRONTEND
    assert 'const mediaUrl = this._resolvedMediaUrl(resolved?.url);' in FRONTEND
    assert 'this._musicAudio.src = mediaUrl;' in FRONTEND
    assert 'const ttsUrl = this._resolvedMediaUrl(resolved?.url);' in FRONTEND
    assert 'this._ttsAudio.src = ttsUrl;' in FRONTEND


def test_tv_modals_anchor_under_toolbar_and_cards_pack_without_row_gaps():
    assert 'toolbar?.scrollIntoView?.({block:"nearest"})' in FRONTEND
    assert 'const top = Math.max(6, Math.round((toolbarRect?.bottom || 64) + 4));' in FRONTEND
    assert 'top:var(--modal-top,68px);left:0;right:0;bottom:0' in FRONTEND
    assert '.tv-toolbar{position:sticky;top:0' in FRONTEND
    assert ':host{display:block;width:100%;max-width:none;min-height:0' in FRONTEND
    dashboard = FRONTEND[FRONTEND.index('class FitnessTvDashboardCard'):FRONTEND.index('class FitnessTvDashboardStrategy')]
    layout_before_tooltip = dashboard[:dashboard.index('.cast-focus-tooltip[hidden]')]
    assert 'transform:translateX(-50%)' not in layout_before_tooltip
    assert '.tv-grid{--tv-columns:4;--tv-row:4px;display:grid' in FRONTEND
    assert 'grid-auto-flow:dense' in FRONTEND
    assert 'new ResizeObserver((entries) =>' in FRONTEND
    assert 'wrapper.style.gridRowEnd = `span ${Math.max(1, Math.ceil((visualHeight + gap) / rowHeight))}`' in FRONTEND
    assert 'Number(this._tvScalePercent || 70) / 100' in FRONTEND
    assert '@media(max-width:1500px){:host(:not([fitness-cast-receiver])) .tv-grid{--tv-columns:3}' in FRONTEND
    assert ':host([fitness-cast-receiver]) .tv-grid{--tv-columns:3;column-gap:6px' in FRONTEND
    assert 'transform:scale(var(--fitness-tv-card-scale,.70))' in FRONTEND
    assert 'zoom:.82' not in FRONTEND
    assert ':host([fitness-cast-receiver]) .tv-toolbar{grid-template-columns:auto minmax(76px,120px) auto minmax(180px,1fr)' in FRONTEND


def test_browser_profile_views_are_full_width_panels_and_cast_uses_separate_safe_views():
    assert 'title="Fitness TV", path="main", panel=True, setup=True' in DASHBOARD
    assert 'view["panel"] = True' in DASHBOARD
    profile_block = DASHBOARD[DASHBOARD.index('for entry in entries:'):DASHBOARD.index('return {"title": "Fitness TV", "views": views}')]
    assert 'path=f"profile-{entry.entry_id}"' in profile_block
    assert 'panel=True' in profile_block
    assert 'path=f"cast-{entry.entry_id}"' in profile_block
    cast_view = profile_block[profile_block.index('path=f"cast-{entry.entry_id}"'): ]
    assert 'panel=True' not in cast_view
    assert '"view_path": f"cast-{entry.entry_id}"' in DASHBOARD
    assert 'path.startswith("cast-")' in DASHBOARD


def test_tv_cards_keep_saved_order_and_support_rearranging():
    assert 'for (const cardId of selectedIds)' in FRONTEND
    assert 'wrapper.draggable = this._layoutEditing' in FRONTEND
    assert 'this._reorderCard(sourceId, cardId, after)' in FRONTEND
    assert 'type:"fitness/tv/preferences/save"' in FRONTEND
    assert 'arrange_cards' in DASHBOARD


def test_tv_layout_uses_dense_measured_grid_instead_of_css_columns():
    tv_frontend = FRONTEND[FRONTEND.index('class FitnessTvDashboardCard'):FRONTEND.index('class FitnessTvDashboardStrategy')]
    assert 'grid-auto-flow:dense' in tv_frontend
    assert 'grid-template-columns:repeat(var(--tv-columns),minmax(0,1fr))' in tv_frontend
    assert 'column-count:' not in tv_frontend
    assert '_syncCardGridSpan(card, wrapper)' in tv_frontend
    assert ':host([fitness-cast-receiver]) .tv-grid{--tv-columns:3' in tv_frontend


def test_tv_setup_page_and_per_profile_reconfigure_are_first_class():
    assert 'custom:fitness-tv-setup-card' in DASHBOARD
    assert 'class FitnessTvSetupCard extends HTMLElement' in FRONTEND
    assert '[FITNESS_TV_SETUP_CARD_TAG, "fitness-tv-setup-card", "fitness-tv-setup-card-v70"' in FRONTEND
    assert 'customElements.define(tag, class extends BaseClass {});' in FRONTEND
    assert 'id="add-profile"' in FRONTEND
    assert 'class="tool configure-profile"' in FRONTEND
    assert 'id="configure"' in FRONTEND
    assert 'type:"fitness/tv/profile/configure"' in FRONTEND
    assert 'vol.Required("type"): "fitness/tv/profile/configure"' in TV
    assert 'CONF_TV_MEDIA_PLAYER_ID: target' in TV
    assert 'CONF_TV_DUCKING_PERCENT: int(' in TV
    assert 'hass.config_entries.async_update_entry(entry, options=options)' in TV


def test_each_tv_profile_has_independent_cast_music_tts_and_display_preferences():
    assert 'self._clients: dict[str, dict[str, dict[str, Any]]] = {}' in TV
    assert 'self._media_state: dict[str, dict[str, Any]] = {}' in TV
    assert 'self._expected_cast: dict[str, str] = {}' in TV
    assert 'profile_entry_id' in TV
    assert 'tv_scale_percent' in TV
    assert 'oled_protection' in TV
    assert 'cast_media_player_id' in FRONTEND
    assert 'ducking_percent' in FRONTEND


def test_oled_protection_and_tv_density_controls_are_available_and_translatable():
    assert 'DEFAULT_TV_SCALE_PERCENT = 70' in TV
    assert 'DEFAULT_TV_OLED_PROTECTION = False' in TV
    assert 'id="cfg-scale"' in FRONTEND
    assert 'id="cfg-oled"' in FRONTEND
    assert '_startOledProtection()' in FRONTEND
    assert '--fitness-oled-x' in FRONTEND
    assert ':host([oled-idle][fitness-cast-receiver]) .tv-toolbar{opacity:.34}' in FRONTEND
    assert ':host([fitness-cast-receiver]) .tv-toolbar button>span{display:none!important}' in FRONTEND
    for label in (
        'tv_setup','add_tv_profile','reconfigure_profile','default_tv','tts_ducking',
        'tv_scale','oled_protection','save'
    ):
        assert f'"{label}":' in DASHBOARD



def test_tv_media_browser_search_favorites_and_single_audio_owner():
    assert 'media_search' in DASHBOARD
    assert 'media_favorites' in DASHBOARD
    assert 'favorites' in TV
    assert '_sanitize_favorites' in TV
    assert '_openMediaFavorites' in FRONTEND
    assert 'id="media-search"' in FRONTEND
    assert 'mdi:star-outline' in FRONTEND
    assert 'source_client_id:FITNESS_TV_CLIENT_ID' in FRONTEND
    assert 'self._audio_owner: dict[str, str] = {}' in TV
    assert '_ignored_cast_clients' in TV
    assert '"command": "stop"' in TV
    assert '"reason": "new_media_selected"' in TV
    assert 'command === "stop"' in FRONTEND
    assert 'this._hardStopMusic();' in FRONTEND
    assert 'this._hardStopAudio(this._ttsAudio);' in FRONTEND
    assert 'Route changes remove this Lovelace card from the DOM.' in FRONTEND
    assert '_suspendMusicForNavigation();' in FRONTEND


def test_tv_profile_toolbar_and_inline_backend_flows():
    assert 'tv-toolbar ${fixedProfile ? "fixed-profile" : ""}' in FRONTEND
    assert 'grid-template-areas:"brand identity actions" "music music music"' in FRONTEND
    assert 'id="backend-config"' in FRONTEND
    assert 'id="add-backend-profile"' in FRONTEND
    assert 'class FitnessBackendFlow extends HTMLElement' in FRONTEND
    assert 'config/config_entries/flow' in FRONTEND
    assert 'fitness/dashboard/options_flow/start' in FRONTEND
    assert 'fitness/dashboard/options_flow/step' in FRONTEND
    assert 'fitness/dashboard/options_flow/cancel' in FRONTEND
    assert 'config/config_entries/options/flow' not in FRONTEND
    assert 'next_step_id:button.dataset.next' in FRONTEND
    assert 'document.createElement("fitness-backend-flow")' in FRONTEND
    assert '_openBackendFlow("add")' in FRONTEND
    assert '_openBackendFlow("options", entryId' in FRONTEND


def test_unreleased_38_flow_modal_is_scrollable_translated_and_has_main_menu_button():
    assert 'fitness/dashboard/flow_translations' in DASHBOARD
    assert 'websocket_dashboard_flow_translations' in DASHBOARD
    assert 'type:"fitness/dashboard/flow_translations"' in FRONTEND
    assert 'class="flow-home"' in FRONTEND
    assert 'mdi:view-dashboard-outline' in FRONTEND
    assert '_restartOptionsFlow()' in FRONTEND
    assert '.flow-body{display:grid;gap:9px;padding:15px;overflow-y:auto;overflow-x:hidden;min-height:0' in FRONTEND
    assert ':host{display:block;color:var(--primary-text-color);height:100%;max-height:100%;min-height:0;overflow:hidden}' in FRONTEND
    assert 'flowBody.scrollTop += Number(event.deltaY || 0);' in FRONTEND
    assert 'settings_main_menu' in DASHBOARD


def test_unreleased_38_cast_takes_over_existing_music_and_laptop_controls_target_tv():
    assert 'cast_expected = self.has_cast_expectation(profile_entry_id)' in TV
    assert 'client_id = await self.async_wait_cast_active(' in TV
    assert '_ensureCastMusicPlayback(state = {})' in FRONTEND
    assert 'if (this._audioOwner && FITNESS_TV_CAST_RECEIVER)' in FRONTEND
    assert 'await this._playResolvedMedia(mediaContentId' in FRONTEND
    assert 'this._activeCastTarget = String(result?.cast_target || "")' in FRONTEND
    assert '"cast_target": hub.cast_target(profile_entry_id)' in TV


def test_unreleased_40_live_setting_updates_remain_available_without_volume_control():
    assert 'FITNESS_TV_SETTINGS_EVENT = "fitness_tv_settings"' in FRONTEND
    assert 'TV_SETTINGS_EVENT = "fitness_tv_settings"' in TV
    assert 'hub.broadcast_settings(' in TV
    assert '_subscribeTvSettings()' in FRONTEND
    assert 'id="cast-volume"' not in FRONTEND
    assert '_sendMediaCommand("volume"' not in FRONTEND
    assert 'command === "volume"' not in FRONTEND
    assert 'payload.tv_scale_percent' in FRONTEND
    assert 'payload.oled_protection' in FRONTEND


def test_unreleased_38_favorite_feedback_is_optimistic_and_toolbar_cannot_overlap():
    assert 'Optimistic UI feedback' in FRONTEND
    assert 'favorite-pulse' in FRONTEND
    assert 'ev.currentTarget' in FRONTEND
    assert '@media(max-width:1600px)' in FRONTEND
    assert '.tv-toolbar.fixed-profile .tv-actions .tool span{display:none}' not in FRONTEND
    assert '.tv-toolbar.fixed-profile .tv-actions{grid-template-columns:repeat(auto-fit,minmax(94px,1fr))}' in FRONTEND


def test_unreleased_39_cast_handoff_stops_old_audio_and_single_browser_instance_handles_events():
    assert '"reason": "cast_handoff"' in TV
    assert 'self._audio_owner.pop(profile_entry_id, None)' in TV
    assert 'await asyncio.sleep(0.20)' in DASHBOARD
    assert '_claimWindowController()' in FRONTEND
    assert '_isWindowController()' in FRONTEND
    assert 'window.__fitnessTvControllers' in FRONTEND
    assert 'if (!this._isWindowController()) return;' in FRONTEND
    assert '["session_replaced","cast_handoff"]' in FRONTEND


def test_unreleased_40_tv_scale_branding_and_live_controls():
    assert '"volume": max(0.0, min(1.0, volume))' not in TV
    assert 'vol.Range(min=10, max=150)' in TV
    assert 'min="10" max="150"' in FRONTEND
    assert 'Math.max(0.10, Math.min(1.50' in FRONTEND
    assert 'sidebar_icon="mdi:television-play"' in DASHBOARD
    assert 'window.customIconsets.fitness' in FRONTEND
    assert 'FITNESS_BRAND_ICON_PATH = "/fitness/brand/icon.png"' in FRONTEND
    assert 'StaticPathConfig("/fitness/brand"' in DASHBOARD
    assert '.tv-brand .fitness-brand-icon{width:30px;height:30px' in FRONTEND
    assert ':host([fitness-cast-receiver]) .tv-brand .fitness-brand-icon{width:18px;height:18px' in FRONTEND
    assert 'type:"call_service"' in FRONTEND
    assert 'domain:"button"' in FRONTEND
    assert 'service:"press"' in FRONTEND
    assert 'target:{entity_id:entityId}' in FRONTEND


def test_unreleased_40_cast_pointer_keyboard_interaction_helpers_are_present():
    assert '_handleCastKeydown(event)' in FRONTEND
    assert '_castFocusableElements()' in FRONTEND
    assert '["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"]' in FRONTEND
    assert '_castRemoteSections()' in FRONTEND
    assert '_enterCastRemoteSection(section = this._castRemoteSection)' in FRONTEND
    assert 'window.addEventListener("keydown", this._boundCastKeydown, true)' in FRONTEND
    assert 'window.addEventListener("keyup", this._boundCastKeyup, true)' in FRONTEND
    assert 'window.addEventListener("popstate", this._boundCastPopstate, true)' in FRONTEND
    assert 'window.removeEventListener("keydown", this._boundCastKeydown, true)' in FRONTEND


def test_live_card_localizes_session_state_and_includes_pause_stop_controls():
    assert 'l[`session_status_${state.state}`]' in FRONTEND
    assert '"session_status_waiting_for_live_data":"Waiting for live data"' in DASHBOARD
    assert '"session_status_waiting_for_live_data":"Αναμονή ζωντανών δεδομένων"' in DASHBOARD
    assert 'const controlKeys = ["start_workout","pause_workout","resume_workout","stop_workout"]' in FRONTEND


def test_unreleased_44_live_controls_use_native_service_and_stable_more_info():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert 'this._hass.callService("button", "press", {}, {entity_id:entityId})' in FRONTEND
    assert '_liveStateSignature(hass)' in FRONTEND
    assert 'metric.addEventListener("click"' in FRONTEND
    assert '_fitnessOpenMoreInfo(this, metric.dataset.moreInfo)' in FRONTEND


def test_profile_aware_tts_test_service_uses_normal_fitness_routing():
    assert 'SERVICE_TEST_TTS = "test_tts"' in CONST
    assert 'SERVICE_TEST_TTS' in INIT
    assert 'test_tts:' in SERVICES
    assert 'manager.async_test_tts(' in INIT
    assert 'async def async_test_tts' in MANAGER
    assert 'await self._async_speak(spoken)' in MANAGER
    for path in _translation_files():
        service = json.loads(path.read_text(encoding="utf-8"))["services"]["test_tts"]
        assert service["name"]
        assert service["description"]
        assert service["fields"]["config_entry_id"]["name"]
        assert service["fields"]["message"]["name"]


def test_profile_aware_ai_to_tts_service_respects_profile_pipeline():
    assert 'SERVICE_AI_TTS = "ai_tts"' in CONST
    assert 'SERVICE_AI_TTS' in INIT
    assert 'ai_tts:' in SERVICES
    assert 'manager.async_ai_tts(' in INIT
    assert 'async def async_ai_tts' in MANAGER
    assert 'if not self.config.get(CONF_AI_ENABLED)' in MANAGER
    assert 'await self._call_ai_with_language_guard(' in MANAGER
    assert 'await self._async_speak(spoken)' in MANAGER
    for path in _translation_files():
        service = json.loads(path.read_text(encoding="utf-8"))["services"]["ai_tts"]
        assert service["name"]
        assert service["description"]
        assert service["fields"]["config_entry_id"]["name"]
        assert service["fields"]["prompt"]["name"]


def test_stop_cast_service_registration_has_no_stray_test_tts_argument():
    assert 'SERVICE_STOP_TV_DASHBOARD,\n        _stop_tv_dashboard,' in INIT
    assert 'SERVICE_STOP_TV_DASHBOARD,\n    SERVICE_TEST_TTS,\n        _stop_tv_dashboard,' not in INIT


def test_unreleased_44_cast_lifecycle_tracks_real_tv_receiver_and_pauses_phantom_media():
    assert 'def is_cast_active(self, profile_entry_id: str) -> bool:' in TV
    assert 'state.state in {"off", "standby", "unknown", "unavailable"}' in TV
    assert 'CAST_APP_ID_HOMEASSISTANT_LOVELACE' in TV
    assert 'async_track_state_change_event(' in TV
    assert 'async def async_mark_cast_inactive(' in TV
    assert '{"playing": False, "error": False}' in TV
    assert 'CAST_CLIENT_STALE_SECONDS = 14.0' in TV
    assert 'async def async_wait_cast_active(' in TV
    assert 'def arm_cast_receiver(self, profile_entry_id: str) -> None:' in TV
    assert 'self._cast_accept_after: dict[str, float] = {}' in TV
    assert 'hub.arm_cast_receiver(entry.entry_id)' in DASHBOARD
    assert 'if expect_cast:' in TV
    assert 'return None' in TV
    assert '"cast_active": hub.is_cast_active(profile_entry_id)' in TV
    assert 'this._serverCastActive = Boolean(result?.cast_active)' in FRONTEND
    assert '["off", "standby", "unknown", "unavailable"].includes(String(state.state || ""))' in FRONTEND
    assert 'stopCast.hidden = !FITNESS_TV_CAST_RECEIVER || !anyCastActive' in FRONTEND
    assert 'stopCast.disabled = !anyCastActive' in FRONTEND
    assert 'reason="manual_cast_stop"' in DASHBOARD
    assert 'return True' in DASHBOARD


def test_unreleased_44_cast_launch_requires_fitness_browser_heartbeat_and_failure_clears_playing():
    assert 'cast_client = await hub.async_wait_cast_active(' in DASHBOARD
    assert 'no live Fitness receiver heartbeat arrived' in DASHBOARD
    assert 'await hub.async_mark_cast_inactive(' in DASHBOARD
    assert 'reason="cast_launch_failed"' in DASHBOARD
    assert 'await this._heartbeat();' in FRONTEND
    assert 'this._castActive = true;' not in FRONTEND


def test_unreleased_45_now_playing_requires_a_real_selection_and_reflects_actual_playback():
    assert 'id="media-status"' in FRONTEND
    assert "l.media_selected" in FRONTEND
    assert 'const failed = hasSelection && Boolean(error || shared.error)' in FRONTEND
    assert 'const playing = hasSelection && !failed && Boolean(shared.playing' in FRONTEND
    assert 'if (play) play.disabled = playing || !hasSelection' in FRONTEND
    assert 'if (!String(state.media_content_id || "").trim())' in FRONTEND
    assert 'this._musicAudio?.getAttribute("src")' in FRONTEND
    assert 'if not media_content_id:' in TV
    assert '"media_selected":"Selected"' in DASHBOARD
    assert '"media_selected":"Επιλεγμένο"' in DASHBOARD


def test_unreleased_44_tts_follows_the_profile_audio_owner_before_fallback_speakers():
    assert 'get_tv_dashboard_hub(self.hass)' in MANAGER
    assert 'profile_media_playing = bool(' in MANAGER
    assert 'hub.media_state(self.entry.entry_id).get("playing")' in MANAGER
    assert 'whether that owner is a laptop/browser, local Cast receiver' in MANAGER


def test_unreleased_45_powered_off_cast_target_is_woken_before_lovelace_launch():
    assert 'async def _async_wake_cast_target(' in DASHBOARD
    assert '"media_player",\n            "turn_on"' in DASHBOARD
    assert 'if started_off:' in DASHBOARD
    assert 'await _async_wake_cast_target(hass, media_player)' in DASHBOARD
    assert 'state.state in {"off", "standby", "unknown", "unavailable"}' in DASHBOARD


def test_unreleased_45_empty_media_state_cannot_be_playing_or_error():
    empty_block = TV[TV.index('if not media_content_id:'):TV.index('duration = self._media_seconds', TV.index('if not media_content_id:'))]
    assert '"title": ""' in empty_block
    assert '"media_content_id": ""' in empty_block
    assert '"playing": False' in empty_block
    assert '"error": False' in empty_block
    assert '"position": 0.0' in empty_block
    assert '"duration": 0.0' in empty_block
    assert 'title:"",artist:"",album:"",year:"",thumbnail:"",details:"",provider:"",provider_name:"",provider_origin:"",media_content_id:""' in FRONTEND
    assert 'playing:false,error:false,position:0,duration:0' in FRONTEND
    assert 'this._musicTitle = this._sharedMediaState.title;' in FRONTEND
    assert 'this._currentMediaContentId = this._sharedMediaState.media_content_id;' in FRONTEND


def test_unreleased_46_persists_last_music_and_re_resolves_after_cast_restart():
    assert '"last_media": self._sanitize_last_media(profile.get("last_media"))' in TV
    assert 'async def async_restore_last_media(' in TV
    assert 'async def async_play_last_media(' in TV
    assert 'last_media={' in TV
    assert 'await hub.async_restore_last_media(entry.entry_id)' in DASHBOARD
    assert 'try { audio.removeAttribute("src"); } catch (_err) {}' in FRONTEND
    assert 'try { audio.src = ""; }' not in FRONTEND
    assert 'const attachedSrc = String(this._musicAudio?.getAttribute?.("src") || "").trim();' in FRONTEND
    assert 'data.fresh_resolve' in FRONTEND
    assert 'for (let attempt = 0; attempt < 2; attempt += 1)' in FRONTEND


def test_unreleased_46_powered_off_tv_has_wake_cooldown_and_screen_wake_lock():
    assert 'remaining = 10.0 - (asyncio.get_running_loop().time() - wake_started)' in DASHBOARD
    assert 'await asyncio.sleep(remaining)' in DASHBOARD
    assert "l.cast_connecting" in FRONTEND
    assert 'navigator.wakeLock.request("screen")' in FRONTEND
    assert 'FITNESS_TV_CAST_RECEIVER ? 5000 : 10000' in FRONTEND
    assert 'CAST_CLIENT_STALE_SECONDS = 14.0' in TV


def test_unreleased_49_tv_wake_lock_tracks_session_or_music_and_reacquires():
    assert '_shouldKeepScreenAwake()' in FRONTEND
    assert 'this._sessionOpen() || this._musicPlaying()' in FRONTEND
    assert 'setTimeout(() => this._startScreenWakeLock(), 1000);' in FRONTEND
    assert 'this._reconcileScreenWakeLock();' in FRONTEND


def test_unreleased_46_setup_has_one_touch_profile_tv_workout_flow():
    assert 'SERVICE_START_TV_WORKOUT = "start_tv_workout"' in CONST
    assert 'start_tv_workout:' in SERVICES
    assert 'async def async_start_tv_workout' in MANAGER
    assert 'await self.async_cast_tv_dashboard(media_player)' in MANAGER
    assert 'async_play_last_media(' in MANAGER
    assert 'await self.async_start_session()' in MANAGER
    assert 'type:"fitness/tv/start_workout"' in FRONTEND
    assert 'class="tool start-tv-workout"' in FRONTEND
    assert "l.start_tv_workout" in FRONTEND


def test_unreleased_46_cast_uses_profile_language_and_tv_safe_recovery_bar_fallbacks():
    assert 'profile?.language || this._access?.language || this._hass?.language || "en"' in FRONTEND
    assert 'String(this._profile?.language || this._hass?.language || "en")' in FRONTEND
    assert 'background:var(--divider-color);background:color-mix' in FRONTEND
    assert 'background:var(--score-tone);background:linear-gradient' in FRONTEND
    assert '"start_tv_workout":"Έναρξη στην TV"' in DASHBOARD
    assert '"keep_awake":"Προστασία από προφύλαξη οθόνης"' in DASHBOARD


def test_unreleased_48_music_sources_are_profile_native_searchable_and_stream_safe():
    assert 'FITNESS_RADIO_PREFIX = "fitness-radio://"' in RADIO_ADAPTER
    assert 'FITNESS_URL_PREFIX = "fitness-url://"' in DIRECT_ADAPTER
    assert 'FITNESS_SPOTIFY_PREFIX = "fitness-spotify://"' in LEGACY_SPOTIFY_ADAPTER
    assert 'FITNESS_SOUNDCLOUD_PREFIX = "fitness-soundcloud://"' in SOUNDCLOUD_ADAPTER
    assert 'FITNESS_YOUTUBE_PREFIX = "fitness-youtube://"' in YOUTUBE_ADAPTER
    assert 'async def async_music_browse(' in TV
    assert '"/json/stations/search"' in TV
    assert '"/json/stations/topclick/100"' in TV
    assert 'async def async_resolve_fitness_media' in MUSIC_REGISTRY
    assert 'class FitnessMusicProxyView(HomeAssistantView):' in TV
    assert 'url = "/fitness/music/proxy/{token}"' in TV
    assert 'hub._music_proxy_url(url)' in RADIO_ADAPTER
    assert 'type:"fitness/tv/music/browse"' in FRONTEND
    assert 'type:"fitness/tv/music/resolve"' in FRONTEND
    assert 'data-source="radio"' in FRONTEND
    assert 'data-source="ha"' in FRONTEND
    assert 'data-source="link"' in FRONTEND
    assert 'open.spotify.com/embed/iframe-api/v1' not in FRONTEND
    assert "l.music_spotify_requires_provider" in FRONTEND
    assert 'w.soundcloud.com/player/api.js' in FRONTEND
    assert 'youtube.com/iframe_api' in FRONTEND


def test_unreleased_48_embedded_music_respects_tts_and_profile_favorites():
    assert 'async _duckEmbeddedForTts(duck)' in FRONTEND
    assert 'controller.setVolume?.' in FRONTEND
    assert 'provider === "spotify"' not in FRONTEND
    assert 'provider === "youtube"' in FRONTEND
    assert 'provider === "soundcloud"' in FRONTEND
    assert 'await restoreEmbedded()' in FRONTEND
    assert 'profile_entry_id:this._profile.entry_id' in FRONTEND
    assert 'this._mediaFavorites' in FRONTEND
    for label in (
        "music_sources", "music_internet_radio", "music_ha_sources",
        "music_add_link", "music_link", "music_use_link",
    ):
        assert f'"{label}"' in DASHBOARD


def test_unreleased_49_radio_browser_country_filter_and_ambient_tv_background():
    assert 'country_code: str = ""' in TV
    assert '"/json/countrycodes"' in TV
    assert 'f"/json/stations/bycountrycodeexact/{country_code}"' in TV
    assert 'countrycodeExact' not in TV
    assert 'new Intl.DisplayNames([language], {type:"region"})' in FRONTEND
    assert 'country_code:String(countryCode || "").trim().toUpperCase()' in FRONTEND
    assert 'id="media-country"' in FRONTEND
    assert 'this._intensityColors = data?.intensity_colors || {}' in FRONTEND
    assert '_fitnessAmbientRgb()' in FRONTEND
    assert 'vo2max_percent_predicted' in FRONTEND
    assert '--fitness-tv-ambient' in FRONTEND
    assert 'from .feedback import INTENSITY_RGB' in DASHBOARD


def test_unreleased_49_tv_setup_icons_and_labels_are_native_mdi():
    assert 'sidebar_icon="mdi:television-play"' in DASHBOARD
    assert 'fitness:logo' not in DASHBOARD
    assert "l.backend_profile" in FRONTEND
    assert 'class="tool enable-profile"><ha-icon icon="mdi:television-play"' in FRONTEND
    assert 'id="add-profile"><ha-icon icon="mdi:plus-circle-outline"' in FRONTEND


def test_unreleased_49_music_link_copy_explains_that_it_is_not_a_provider_account():
    assert 'This does not add a provider account.' in DASHBOARD
    assert 'Play & remember' in DASHBOARD
    assert 'music-link-examples' in FRONTEND
