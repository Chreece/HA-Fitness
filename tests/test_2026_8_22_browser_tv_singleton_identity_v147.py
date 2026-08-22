from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
FLOW = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")
STRINGS = json.loads((ROOT / "custom_components/fitness/strings.json").read_text(encoding="utf-8"))


def test_restricted_browser_tv_polls_media_commands_and_obeys_pause_stop():
    assert "_media_command_mailbox" in TV
    assert "poll_media_commands" in TV
    assert "take_media_commands" in TV
    assert 'type:"fitness/tv/heartbeat"' in FRONTEND
    assert "poll_media_commands:Boolean(FITNESS_TV_CAST_RECEIVER && !this._hass?.connection)" in FRONTEND
    assert "_handlePolledMediaCommands" in FRONTEND
    assert '["pause","stop"].includes(command)' in FRONTEND


def test_dashboard_stop_cast_can_terminate_browser_receiver_and_receiver_exit_kills_audio():
    assert 'vol.Required("type"): "fitness/tv/cast/stop"' in TV
    assert 'vol.Required("type"): "fitness/tv/receiver/leave"' in TV
    assert 'type:"fitness/tv/cast/stop"' in FRONTEND
    assert "async _quitCastReceiver" in FRONTEND
    assert "this._hardStopMusic();" in FRONTEND
    assert 'window.addEventListener("pagehide", this._boundCastPageHide' in FRONTEND
    assert 'type:"fitness/tv/receiver/leave"' in ACCOUNTS


def test_one_cast_slot_is_reserved_before_automatic_browser_tv_launch():
    receiver = DASH[DASH.index("async def websocket_tv_browser_receiver"):]
    assert "cast_hub.expect_local_cast(" in receiver
    assert receiver.index("cast_hub.expect_local_cast(") < receiver.index("async_wait_cast_bootstrap_redeemed")
    assert '"cast_already_active"' in receiver
    assert '"cast": (' in receiver
    assert "castBusy" in FRONTEND
    assert "modalHaStart.disabled = castPending || (!castConnected" in FRONTEND
    assert "button.disabled = cast.connecting || (!cast.connected" in FRONTEND


def test_pending_browser_tv_stop_rejects_late_receiver_bootstrap():
    assert 'self._cast_stop_requests[profile_entry_id] = "*"' in TV
    assert 'stop_target in {"*", client_id}' in TV
    assert 'target in {"*", str(client_id)}' in TV
    assert "self._cast_stop_requested_at" in TV
    assert "self._cast_stop_requests.pop(profile_entry_id, None)" in TV


def test_duplicate_receiver_departure_cannot_release_legitimate_cast():
    block = TV[TV.index("async def async_receiver_departed"):TV.index("def _claim_audio_owner")]
    assert "authoritative_departure" in block
    assert "client_id not in self._ignored_cast_clients" in block
    assert "if authoritative_departure and profile_entry_id in self._expected_local_cast" in block
    assert "if self._audio_owner.get(profile_entry_id) == client_id" in block


def test_cast_pointer_focus_and_modal_flow_are_not_stuck_on_toolbar():
    assert 'classList?.contains?.("modal-card")' in FRONTEND
    assert "control.focus?.({preventScroll:true})" in FRONTEND
    assert "this._castRemoteSection = section" in FRONTEND
    assert 'controls.find((control) => !control.classList?.contains?.("modal-close"))' in FRONTEND


def test_restricted_cast_has_native_fallback_config_form_renderer():
    assert "_fallbackForm(step, schema)" in FRONTEND
    assert '<input type="date"' in FRONTEND
    assert 'globalThis.customElements?.get?.("ha-form")' in FRONTEND
    assert "_fallbackFormField(step, field)" in FRONTEND


def test_cast_cards_use_natural_size_dense_masonry_and_no_transform_scaling():
    assert 'grid.style.setProperty("display", "flex")' not in FRONTEND
    assert 'const stableDesktopGrid = !FITNESS_TV_CAST_RECEIVER' in FRONTEND
    assert 'const castScale = 1;' in FRONTEND
    assert 'const scale = 1;' in FRONTEND
    assert 'card.toggleAttribute("fitness-natural-height", true)' in FRONTEND
    assert 'skyline' in FRONTEND
    assert 'transform:none!important' in FRONTEND


def test_fitness_username_is_required_unique_and_is_the_remote_hostname():
    account_step = STRINGS["config"]["step"]["account_access"]
    assert "fitness_remote_slug" not in account_step["data"]
    assert "fitness_remote_slug" not in account_step["data_description"]
    assert "invalid_username" in STRINGS["config"]["error"]
    assert "username_in_use" in STRINGS["config"]["error"]
    assert "controller.suggested_username" in FLOW
    assert "vol.Required(\n                _ACCOUNT_USERNAME" in FLOW
    assert '"remote_slug": canonical_username if network_access' in FLOW
    assert "def username_available" in ACCOUNTS
    assert "Disabled accounts keep their name reserved" in ACCOUNTS
    assert 'raise ValueError("username_in_use")' in ACCOUNTS
    assert '"remote_slug": slug' in ACCOUNTS
    save_schema = ACCOUNTS[ACCOUNTS.index('vol.Required("type"): "fitness/accounts/save"'):ACCOUNTS.index('async def websocket_fitness_accounts_save')]
    assert 'vol.Required("username")' in save_schema
    assert 'vol.Optional("remote_slug")' not in save_schema
    assert 'remote_slug:' not in FRONTEND[FRONTEND.index('const payload = {type:"fitness/accounts/save"'):FRONTEND.index('const result = await this._hass.callWS(payload);')]


def test_v147_cache_busts_ha_and_restricted_portal():
    assert "cast-ui-155" in DASH
    assert "cast-ui-155" in ACCOUNTS
