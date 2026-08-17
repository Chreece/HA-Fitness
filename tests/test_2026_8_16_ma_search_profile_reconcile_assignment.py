from pathlib import Path

ROOT = Path(__file__).parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text()


def test_ma_search_never_requires_sendspin_client_registration():
    start = FRONTEND.index("async _runMusicSearch(root)")
    end = FRONTEND.index("_musicLinkId(target)", start)
    body = FRONTEND[start:end]
    assert 'type:"fitness/tv/music/search"' in body
    assert "await this._ensureMASendspinPlayer()" not in body
    assert "await this._connectMASendspinPlayer" not in body
    assert 'void Promise.all([this._sendspinModule(), this._primeMASendspinRelay()])' in body


def test_ma_relay_client_id_is_optional_and_backend_returns_authoritative_id():
    assert 'vol.Optional("client_id", default=""): str' in TV
    assert 'or f"fitness-tv-{uuid4().hex}"' in TV
    assert 'connection.send_result(msg["id"], {"url": relay_url, "client_id": client_id})' in TV
    assert 'this._maSendspinRelayClientId = String(result?.client_id || FITNESS_TV_CLIENT_ID || "");' in FRONTEND
    assert 'const playerId = String(this._maSendspinRelayClientId || FITNESS_TV_CLIENT_ID || "").trim();' in FRONTEND


def test_ma_play_click_unlocks_before_network_connect_and_queue_dispatch():
    start = FRONTEND.index("async _selectMusic(item, options = {})")
    end = FRONTEND.index("async _playMusic()", start)
    body = FRONTEND[start:end]
    unlock = body.index("await player.unlock?.();")
    connect = body.index("await this._connectMASendspinPlayer(player);")
    dispatch = body.index('await this._sendMediaCommand("select"')
    assert unlock < connect < dispatch


def test_dashboard_config_reconciles_managed_fitness_tv_views_before_open():
    marker = 'async def websocket_dashboard_config(hass: HomeAssistant, connection, msg) -> None:'
    start = DASHBOARD.index(marker)
    ensure = DASHBOARD.index("await async_ensure_tv_dashboard(hass)", start)
    registry = DASHBOARD.index("registry = er.async_get(hass)", start)
    assert start < ensure < registry
    assert 'type:"fitness/dashboard/config"' in FRONTEND
    assert 'row.querySelector(".open-profile")?.addEventListener("click", () => this._navigate(`/fitness-tv/profile-${entryId}`))' in FRONTEND


def test_admin_profile_can_be_assigned_directly_to_an_ha_admin_user():
    assert 'class="access-profile-field ${role === "none" ? "hidden" : ""}"' in FRONTEND
    assert 'profileField?.classList.toggle("hidden", withoutProfile)' in FRONTEND
    assert '.access-role-field,.access-profile-field{display:block;min-width:0;align-self:stretch}' in FRONTEND
    assert 'data-profile-owner' in FRONTEND
    assert 'data-assign-profile' in FRONTEND
    assert 'const assignedRole = selectedUser.is_admin' in FRONTEND
    assert '? "admin"' in FRONTEND
    assert 'profile_entry_id:profileEntryId' in FRONTEND
    # Explicit empty string now clears an admin's optional own-profile binding;
    # omitting the key still means preserve the existing binding.
    assert 'if "profile_entry_id" in msg' in ACCESS
    assert 'profile_entry_id is None' in ACCESS


def test_manage_ha_users_uses_exact_person_route_not_people_route():
    assert 'href="/config/person"' in FRONTEND
    assert ('/config/' + 'people') not in FRONTEND


def test_frontend_resource_revision_is_68_and_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert '_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"' in DASHBOARD
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-82"' in DASHBOARD


def test_unreleased_frontend_uses_uncached_unique_resource_path():
    assert '_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard.js"' in DASHBOARD
    assert '"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"' in DASHBOARD
    assert '_LEGACY_CAST_RESOURCE_NAMESPACE = "/fitness/frontend/fitness-dashboard-cast.js"' in DASHBOARD
    assert '(_RESOURCE_PREFIX, _LEGACY_RESOURCE_NAMESPACE, _LEGACY_CAST_RESOURCE_NAMESPACE)' in DASHBOARD


def test_ma_playing_state_requires_local_sendspin_stream_and_uses_pcm_media_element():
    state_start = FRONTEND.index("_handleMASendspinState(state)")
    state_end = FRONTEND.index("_createMASendspinPlayer()", state_start)
    state_body = FRONTEND[state_start:state_end]
    assert "const playing = Boolean(state?.isPlaying);" in state_body
    assert 'playbackState === "playing"' not in state_body
    assert "progress?.track_progress" in state_body
    assert "progress?.track_duration" in state_body
    assert 'details:current.details || "Track"' in state_body
    assert 'provider_origin:current.provider_origin || "Music Assistant"' in state_body
    player_start = FRONTEND.index("_createMASendspinPlayer()")
    player_end = FRONTEND.index("async _connectMASendspinPlayer", player_start)
    player_body = FRONTEND[player_start:player_end]
    assert 'codecs:["pcm"]' in player_body
    assert "audioElement:this._maAudioElement" in player_body


def test_ma_resume_does_not_fake_playing_without_audio_stream():
    start = FRONTEND.index("async _handleMediaCommand(command, data = {})")
    end = FRONTEND.index("async _ackTts(data, success)", start)
    body = FRONTEND[start:end]
    ma = body.index('this._embeddedProvider === "music_assistant"')
    assert 'Music Assistant did not deliver an audio stream to this browser' in body[ma:]
