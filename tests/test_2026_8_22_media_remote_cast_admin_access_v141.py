from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()


def test_v141_frontend_contract_is_synchronized():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-138"' in DASH
    assert '"frontend_version": "unreleased-138"' in DASH


def test_pending_cast_keeps_controller_and_ha_outputs_silent_until_attempt_expires():
    assert 'CAST_PENDING_EXPECTATION_SECONDS = 24.0' in TV
    assert 'self._expected_cast_at' in TV
    assert 'self._expected_local_cast_at' in TV
    dispatch = TV[TV.index('async def async_dispatch_media_command') : TV.index('async def async_broadcast_media_state')]
    assert 'elif cast_expected:' in dispatch
    assert 'return {"sent": False, "reason": "cast_unavailable"}' in dispatch
    assert 'client_id = source_client_id' not in dispatch[dispatch.index('elif cast_expected:'):dispatch.index('elif audio_output.startswith')]
    assert dispatch.index('elif cast_expected:') < dispatch.index('elif audio_output.startswith("media_player.")')
    assert '_friendlyMediaError' in JS
    assert 'result?.state?.details' in JS


def test_remote_manual_browser_receiver_is_allowed_but_local_ha_tv_launch_is_not():
    assert 'if not access.get("session_allowed"):' in DASH
    assert 'if launch_entity_id or launch_method:' in DASH
    assert 'if not access.get("local_ha_hardware_allowed"):' in DASH
    assert '"local_only" if access.get("is_local_connection") else "remote_only"' in DASH
    assert 'ticket_network == NETWORK_REMOTE_ONLY and _client_is_local(remote)' in ACCOUNTS
    assert 'remote_receiver' in DASH


def test_android_tv_open_reuses_browser_activity_without_force_stopping_it():
    assert 'am start --activity-clear-top --activity-single-top' in DASH
    assert 'force-stop' not in DASH[DASH.index('am start --activity-clear-top --activity-single-top')-600:DASH.index('am start --activity-clear-top --activity-single-top')+600]


def test_fitness_devices_is_native_ha_admin_only_and_uses_integration_page():
    assert 'this._access?.native_ha_admin && !FITNESS_TV_CAST_RECEIVER' in JS
    assert '!this.hasAttribute("fitness-public-portal")' in JS
    assert 'this._navigate("/config/integrations/integration/fitness")' in JS


def test_admin_add_edit_flow_has_access_prelude_but_users_do_not_gain_admin_editor():
    assert '_openAccountAccessPrelude' in JS
    assert 'flow-access-role' in JS
    assert 'flow-access-network' in JS
    assert 'flow-access-views' in JS
    assert '_saveAccountAccess' in JS
    assert 'native_ha_admin' in JS
    assert 'is_admin' in JS


def test_dashcast_heartbeat_is_authoritative_over_home_assistant_cast_app_id():
    start = JS.index('  _refreshCastUiState() {')
    block = JS[start:JS.index('  _cancelRadioRecovery()', start)]
    assert 'this._castState === "connected"' in block
    assert 'real receiver heartbeat' in block
    assert 'FITNESS_TV_CAST_APP_ID' not in block
    code_only = '\n'.join(line for line in block.splitlines() if not line.lstrip().startswith('//'))
    assert 'A078F6B0' not in code_only


def test_cast_toolbar_can_auto_hide_even_when_remote_section_was_selected():
    assert 'fitness-remote-section-selected' in JS
    assert '_toolbarAutoHide' in JS
    assert 'toolbar-hidden' in JS
    # v141 transfers TV remote focus away before hiding rather than pinning the toolbar.
    assert '_firstVisibleDashboardSection' in JS or '_focusFirstVisible' in JS or 'fitness-remote-section-selected' in JS


def test_cast_manual_card_height_and_legacy_surfaces_follow_receiver_scale():
    assert '--fitness-manual-card-height' in JS
    assert 'FITNESS_TV_CAST_RECEIVER' in JS
    assert 'color-mix' in JS
    assert 'fitness-cast-receiver' in JS
