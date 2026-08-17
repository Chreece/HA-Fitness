from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
PROFILE_DATA = (ROOT / "custom_components/fitness/profile_data.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
SELECT = (ROOT / "custom_components/fitness/select.py").read_text()
REMOTE_DOC = (ROOT / "docs/REMOTE_ACCESS.md").read_text()


def test_tv_runtime_state_and_preferences_are_profile_scoped():
    for declaration in (
        'self._clients: dict[str, dict[str, dict[str, Any]]] = {}',
        'self._media_state: dict[str, dict[str, Any]] = {}',
        'self._cast_generation: dict[str, int] = {}',
        'self._expected_local_cast: dict[str, str] = {}',
        'self._audio_owner: dict[str, str] = {}',
    ):
        assert declaration in TV
    assert 'self._data: dict[str, Any] = {"profiles": {}}' in TV
    assert 'self._data["profiles"].get(profile_entry_id)' in TV


def test_each_browser_tab_remembers_its_profile_and_local_cast_is_tab_scoped():
    assert 'FITNESS_TV_PROFILE_TAB_STORAGE = "fitness.tv.profile.tab"' in JS
    assert 'sessionStorage.getItem(FITNESS_TV_PROFILE_TAB_STORAGE)' in JS
    assert 'sessionStorage.setItem(FITNESS_TV_PROFILE_TAB_STORAGE, next.entry_id)' in JS
    assert 'AutoJoinPolicy?.TAB_AND_ORIGIN_SCOPED' in JS
    assert 'AutoJoinPolicy?.PAGE_SCOPED' in JS


def test_tts_follows_playing_profile_dashboard_before_configured_speaker_fallback():
    assert 'profile_media_playing = bool(' in MANAGER
    assert 'hub.media_state(self.entry.entry_id).get("playing")' in MANAGER
    assert 'await hub.async_speak(' in MANAGER
    assert 'media_players = self._feedback_media_player_ids()' in MANAGER


def test_browser_ble_chooser_only_advertises_supported_fitness_services_and_can_disconnect():
    assert 'filters:[...FITNESS_REMOTE_BLE_SERVICES].map((service) => ({services:[service]}))' in JS
    assert 'acceptAllDevices:true' not in JS
    assert 'data-remote-ble-disconnect=' in JS
    assert 'async _disconnectRemoteBleDevice(deviceId, forget = true)' in JS
    assert 'type:"fitness/remote_gateway/ble_disconnect"' in JS
    assert '"fitness/remote_gateway/ble_disconnect"' in REMOTE
    assert 'def disconnect_ble_device(' in REMOTE


def test_live_sensor_metrics_enforce_shared_sensor_owner_and_expose_nonzero_metrics():
    assert 'runtime.sensor_workout_owner(sensor_id)' in PROFILE_DATA
    assert 'if owner not in (None, entry.entry_id):' in PROFILE_DATA
    assert 'live_sensor_metrics' in DASH
    assert 'physical_workout_owner_entity_id' in DASH
    assert '"owner_entry_id": self.runtime.sensor_workout_owner(self.sensor_id)' in SELECT
    assert 'if (ownerEntryId && ownerEntryId !== String(this._profile.entry_id || "")) return "";' in JS
    assert 'if (!Number.isFinite(numeric) || Math.abs(numeric) < 1e-9) return "";' in JS


def test_live_card_has_heartbeat_and_speed_motion_visuals():
    assert 'class="live-motion-card live-heart"' in JS
    assert 'mdi:heart-pulse' in JS
    assert '--heart-beat:' in JS
    assert 'class="live-motion-card live-speed"' in JS
    assert 'mdi:run-fast' in JS
    assert '--run-flow:' in JS


def test_access_role_controls_hide_profile_and_extra_views_for_no_profile_role():
    assert 'const withoutProfile = current === "none";' in JS
    assert 'profileField?.classList.toggle("hidden", withoutProfile);' in JS
    assert 'viewField?.classList.toggle("hidden", withoutProfile);' in JS
    assert 'data-access-role-hint' in JS
    assert '.access-role-field,.access-profile-field{display:block;min-width:0;align-self:stretch}' in JS


def test_structured_modals_scroll_the_body_and_keep_config_save_footer_reachable():
    assert '.configure-modal>.settings-actions{flex:0 0 auto;position:relative;bottom:auto' in JS
    assert '.configure-modal,.browser-modal,.picker-modal,.cast-modal,.remote-gateway-modal' in JS
    assert '.profile-settings,.picker-list,.media-list,.cast-picker,.remote-gateway-body' in JS
    # There are two configure surfaces; both must place the footer outside the scroll body.
    assert JS.count('</div>\n        <div class="settings-actions"><button class="tool" id="cfg-save"') >= 1
    assert '</div><div class="settings-actions"><button class="tool" id="cfg-save"' in JS


def test_living_background_uses_existing_fitness_zone_rgb_and_reduced_motion_fallback():
    assert 'const tone = this._fitnessAmbientRgb();' in JS
    assert '--fitness-tv-ambient-rgb' in JS
    assert 'class="fitness-ambient-layer"' in JS
    assert '@keyframes fitness-ambient-drift-a' in JS
    assert ':host([fitness-live-ambient]) .fitness-ambient-layer' in JS
    assert '@media(prefers-reduced-motion:reduce){.fitness-ambient-layer i{animation:none!important}' in JS


def test_remote_access_document_separates_fitness_policy_from_external_network_setup():
    for phrase in (
        'Wildcard DNS',
        'TLS valid for the wildcard hostname',
        'Preserve the incoming `Host` header',
        'Configure Home Assistant for the reverse proxy',
        "Set Home Assistant's external HTTPS URL",
        'Fitness deliberately manages the **logical access layer**',
    ):
        assert phrase in REMOTE_DOC
