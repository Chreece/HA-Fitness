from pathlib import Path

ROOT = Path(__file__).parents[1]
MUSIC = ROOT / "custom_components/fitness/music"
BASE = (MUSIC / "base.py").read_text()
MA = (MUSIC / "music_assistant.py").read_text()
REGISTRY = (MUSIC / "registry.py").read_text()
CATALOG = (MUSIC / "provider_catalog.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_music_assistant_exposes_configured_provider_instances_as_search_scopes():
    assert "search_scopes: tuple[dict[str, Any], ...]" in BASE
    assert "music_assistant_music_provider_scopes" in MA
    assert '"id": instance_id' in MA
    assert '"domain": domain' in MA
    assert '"busy": is_busy' in MA
    assert "providers=requested_scopes or None" in MA
    assert '"music/search"' in MA
    assert "search_scopes=scopes" in MA


def test_busy_provider_accounts_include_ma_queues_and_external_ha_playback():
    assert "music_assistant_busy_provider_tokens" in MA
    assert "if not _queue_is_playing(queue):" in MA
    assert 'startswith("media_player.")' in MA
    assert 'str(getattr(state, "state", "")).lower() != "playing"' in MA
    assert "registry.async_get(state.entity_id)" in MA
    assert "externally_busy_domains.add(platform)" in MA
    assert "music_assistant_music_provider_scopes(" in TV
    assert '"provider_busy"' in TV


def test_music_assistant_results_are_native_playable_through_sendspin_relay():
    assert 'FITNESS_MA_PREFIX = "fitness-ma://"' in MA
    assert '"can_play": media_type in {' in MA
    for media_type in ("track", "album", "playlist", "artist", "radio", "podcast", "audiobook"):
        assert f'"{media_type}"' in MA
    assert "async_play_music_assistant_uri" in MA
    assert '"player_queues/play_media"' in MA
    assert 'url = "/fitness/music/ma/sendspin/{token}"' in TV
    assert "class FitnessMASendspinProxyView" in TV
    assert "MUSIC_ASSISTANT_SENDSPIN_PORT = 8927" in MA
    assert "music_assistant_sendspin_url(entry)" in TV
    assert 'playerId: config.playerId' not in FRONTEND  # SDK internals stay external
    assert 'const playerId = String(this._maSendspinRelayClientId || FITNESS_TV_CLIENT_ID || "").trim();' in FRONTEND
    assert 'playerId,' in FRONTEND
    assert 'this._maSendspinPlayerId = playerId;' in FRONTEND
    assert 'vol.Required("type"): "fitness/tv/music/ma/sendspin"' in TV
    assert 'vol.Required("type"): "fitness/tv/music/ma/pair"' not in TV
    assert 'vol.Required("type"): "fitness/tv/music/ma/play"' in TV
    assert '@sendspin/sendspin-js@3.2.0/+esm' in FRONTEND
    assert "async _ensureMASendspinPlayer()" in FRONTEND
    assert "async _playMusicAssistant(" in FRONTEND
    assert 'type:"fitness/tv/music/ma/play"' in FRONTEND
    assert 'controller?.sendCommand?.("pause")' in FRONTEND
    assert "controller.setVolume?.(Math.max(0, Math.min(100, Math.round(original * duck))))" in FRONTEND


def test_search_ui_scopes_music_assistant_and_only_shows_working_state_during_request():
    assert 'data-adapter-scope=' in FRONTEND
    assert 'scopes[adapterId]' in FRONTEND
    assert 'scopes,' in FRONTEND
    assert 'ma_player_id:String(this._maSendspinPlayerId || "")' in FRONTEND
    assert 'class="music-search-status music-search-working" hidden' in FRONTEND
    assert "if (working) working.hidden = false;" in FRONTEND
    assert "if (working) working.hidden = true;" in FRONTEND
    assert "l.music_search_working" in FRONTEND
    assert "scopeLocked" in FRONTEND
    assert 'scopeLocked ? "disabled" : ""' in FRONTEND


def test_ytdlp_is_managed_inside_music_provider_catalog_not_general_settings():
    assert 'id="cfg-ytdlp"' not in FRONTEND
    assert 'provider.id === "yt_dlp"' in FRONTEND
    assert '"requires_acknowledgement": True' in CATALOG
    assert 'type:"fitness/tv/music/ytdlp"' in FRONTEND
    assert "_openYtdlpAcknowledgement" in FRONTEND
    assert "_openSetupYtdlpAcknowledgement" in FRONTEND
    assert "_setSetupYtdlp" in FRONTEND


def test_every_fitness_tv_modal_has_sticky_chrome_and_scrollable_content_contract():
    assert ".modal-head{position:sticky!important;top:0" in FRONTEND
    assert ".modal-actions,.settings-actions{position:sticky;bottom:0" in FRONTEND
    assert "overscroll-behavior:contain" in FRONTEND
    assert "scrollbar-gutter:stable" in FRONTEND
    assert ".modal-scroll-body{min-height:0;overflow-y:auto" in FRONTEND


def test_sendspin_relay_ticket_is_reset_after_failed_one_shot_connection():
    assert 'player.disconnect?.("fitness_connect_failed")' in FRONTEND
    assert 'this._maSendspinRelayPath = "";' in FRONTEND
    assert 'this._maSendspinRelayClientId = "";' in FRONTEND
    assert 'void this._primeMASendspinRelay().catch(() => {});' in FRONTEND


def test_music_search_preferences_persist_per_profile_and_ma_results_are_scope_filtered():
    assert '"music_search_adapters"' in TV
    assert '"music_search_configured"' in TV
    assert '"music_search_scopes"' in TV
    assert "_sanitize_music_search_scopes" in TV
    assert 'music_search_adapters:selected' in FRONTEND
    assert 'music_search_scopes:scopes' in FRONTEND
    assert 'this._musicSearchConfigured = Boolean(result?.music_search_configured);' in FRONTEND
    assert 'void this._saveMusicSearchPreferences(root);' in FRONTEND
    assert 'allowed_scope_tokens' in MA
    assert 'provider_tokens.isdisjoint(allowed_scope_tokens)' in MA
    assert '"player_queues/play_media"' in MA


def test_music_search_scrolls_the_whole_inner_body_not_only_provider_rows():
    assert '.music-search-form{display:flex;flex:1 1 auto;min-height:0;overflow-y:auto' in FRONTEND
    assert '.music-search-form>.music-adapter-picker{flex:0 0 auto;min-height:auto;overflow:visible}' in FRONTEND
    assert '.music-search-form>.field-label,.music-search-form>.music-search-status,.music-search-form>.music-search-error,.music-search-form>.modal-actions{flex:0 0 auto}' in FRONTEND
    assert '.modal-card.music-search-modal{' in FRONTEND
    assert 'max-height:calc(100dvh - var(--modal-top,68px) - 26px);overflow:hidden!important}' in FRONTEND
    assert '.modal-card.music-search-modal .music-search-form{display:flex;flex:1 1 auto;min-height:0;overflow-y:auto!important' in FRONTEND
    assert '.modal-card.music-search-modal .music-adapter-picker{flex:0 0 auto;min-height:auto;overflow:visible!important' in FRONTEND



def test_music_assistant_stable_sendspin_contract_uses_explicit_player_id_without_pairing():
    assert '@sendspin/sendspin-js@3.2.0/+esm' in FRONTEND
    assert 'const playerId = String(this._maSendspinRelayClientId || FITNESS_TV_CLIENT_ID || "").trim();' in FRONTEND
    assert 'playerId,' in FRONTEND
    assert 'this._maSendspinPlayerId = playerId;' in FRONTEND
    assert 'pairing_token' not in FRONTEND
    assert 'sendspin/pair_web_player' not in MA
    assert 'fitness/tv/music/ma/pair' not in TV
    assert 'for attempt in range(40):' in MA

def test_music_assistant_search_is_independent_and_play_unlocks_before_connecting():
    assert 'const wantsMusicAssistant = all' in FRONTEND
    search_start = FRONTEND.index('async _runMusicSearch(root)')
    search_end = FRONTEND.index('_musicLinkId(target)', search_start)
    search_body = FRONTEND[search_start:search_end]
    assert 'await this._ensureMASendspinPlayer();' not in search_body
    assert 'type:"fitness/tv/music/search"' in search_body
    assert 'void Promise.all([this._sendspinModule(), this._primeMASendspinRelay()]).catch(() => {});' in search_body

    select_start = FRONTEND.index('async _selectMusic(item, options = {})')
    select_end = FRONTEND.index('async _playMusic()', select_start)
    select_body = FRONTEND[select_start:select_end]
    assert 'await this._prepareMALocalAudioFromGesture();' in select_body
    helper_start = FRONTEND.index('_browserMayOwnLocalAudio()')
    helper_end = FRONTEND.index('async _selectMusic(item, options = {})', helper_start)
    helper_body = FRONTEND[helper_start:helper_end]
    assert 'const player = this._maSendspinPlayer || this._createMASendspinPlayer();' in helper_body
    assert 'await player.unlock?.();' in helper_body
    assert 'await this._connectMASendspinPlayer(player);' in helper_body
    assert helper_body.index('await player.unlock?.();') < helper_body.index('await this._connectMASendspinPlayer(player);')
    assert select_body.index('await this._prepareMALocalAudioFromGesture();') < select_body.index('await this._sendMediaCommand("select"')

    assert '_createMASendspinPlayer()' in FRONTEND
    assert 'async _connectMASendspinPlayer(' in FRONTEND
    assert 'this._maSendspinPlayerId = playerId;' in FRONTEND
    assert 'await player.unlock?.();' not in FRONTEND[FRONTEND.index('async _ensureMASendspinPlayer()'):FRONTEND.index('async _playMusicAssistant(')]


def test_music_assistant_browser_relay_uses_authenticated_ma_proxy_and_waits_for_real_playback():
    assert 'return urlunsplit((scheme, parsed.netloc, "/sendspin", "", ""))' in MA
    assert 'music_assistant_direct_sendspin_url' in MA
    assert 'vol.Optional("client_id", default=""): str' in TV
    assert '{"type": "auth", "token": ma_token, "client_id": client_id}' in TV
    assert 'auth_payload.get("type") != "auth_ok"' in TV
    assert 'client_id:String(FITNESS_TV_CLIENT_ID || "")' in FRONTEND
    assert 'codecs:["pcm"]' in FRONTEND
    assert 'requiredLeadTimeMs:250' in FRONTEND
    assert 'minBufferMs:2500' in FRONTEND
    play_start = FRONTEND.index('async _playMusicAssistant(')
    play_end = FRONTEND.index('async _resolveFitnessMedia(', play_start)
    play_body = FRONTEND[play_start:play_end]
    assert 'await player.unlock?.();' not in play_body
    assert 'while (!this._embeddedPlaying' in play_body
    assert 'Sendspin did not start playback' in play_body
    select_start = FRONTEND.index('async _selectMusic(item, options = {})')
    select_end = FRONTEND.index('async _playMusic()', select_start)
    select_body = FRONTEND[select_start:select_end]
    assert 'await_result:true' in select_body
    assert 'if (!result?.playing)' in select_body
    assert 'console.error("[Fitness TV] music selection failed"' in select_body
