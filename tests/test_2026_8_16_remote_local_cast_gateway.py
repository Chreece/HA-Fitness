from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = (ROOT / "custom_components/fitness/remote_gateway.py").read_text()
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
DOC = (ROOT / "docs/REMOTE_GATEWAY_PROTOCOL.md").read_text()


def test_remote_gateway_is_registered_with_tv_websocket_api():
    assert "async_register_remote_gateway_websocket_commands" in TV
    for command in (
        "fitness/remote_gateway/capabilities",
        "fitness/remote_gateway/hello",
        "fitness/remote_gateway/ble_device",
        "fitness/remote_gateway/ble_frames",
        "fitness/remote_gateway/ant_packets",
        "fitness/remote_gateway/status",
        "fitness/tv/local_cast_credentials",
        "fitness/tv/local_cast_release",
    ):
        assert command in REMOTE


def test_remote_ble_forwards_raw_standard_measurements_to_existing_decoders():
    for parser in (
        "_parse_hr",
        "_parse_cycling_power",
        "_parse_csc",
        "_parse_rsc",
        "_parse_ftms_indoor_bike",
        "_parse_ftms_treadmill",
    ):
        assert parser in REMOTE
    assert 'endpoint_id = f"bluetooth:web:{profile_entry_id}:{gateway_id}:{device_id}"' in REMOTE
    assert "_async_assign_sensor_to_profile" in REMOTE
    assert 'transport="bluetooth"' in REMOTE


def test_remote_ant_reuses_existing_remote_packet_worker_and_auto_assigns_profile():
    assert "REMOTE_PACKET_EVENT" in REMOTE
    assert "REMOTE_GATEWAY_HELLO_EVENT" in REMOTE
    assert "REMOTE_GATEWAY_STATUS_EVENT" in REMOTE
    assert "_async_assign_remote_ant_devices" in REMOTE
    assert 'runtime.endpoint_aliases.get(f"antplus:{device_id}")' in REMOTE


def test_browser_gateway_supports_web_bluetooth_permission_and_reconnect():
    assert "navigator.bluetooth.requestDevice" in JS
    assert "acceptAllDevices:true" in JS
    assert "navigator.bluetooth.getDevices" in JS
    assert 'type:"fitness/remote_gateway/ble_device"' in JS
    assert 'type:"fitness/remote_gateway/ble_frames"' in JS
    assert "FITNESS_REMOTE_BLE_SERVICES" in JS
    assert "FITNESS_REMOTE_BLE_CHARACTERISTICS" in JS
    assert 'id="remote-sensors"' in JS


def test_browser_ant_gateway_scans_supported_dynastream_usb_and_forwards_extended_packets():
    assert "navigator.usb.requestDevice" in JS
    assert "navigator.usb.getDevices" in JS
    assert "vendorId:0x0fcf" in JS
    assert "productId:0x1008" in JS
    assert "productId:0x1009" in JS
    assert "0xB9,0xA5,0x21,0xFB,0xBD,0x72,0xC3,0x45" in JS
    assert "await this._antTransferOut(0x66, [0x00, 0x01])" in JS
    assert "await this._antTransferOut(0x5B, [0x00])" in JS
    assert 'type:"fitness/remote_gateway/ant_packets"' in JS


def test_local_cast_uses_browser_sender_and_current_session_credentials():
    assert "https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1" in JS
    assert "context.requestSession()" in JS
    assert "session.addMessageListener(namespace" in JS
    assert "session.sendMessage(namespace" in JS
    assert 'type:"connect"' in JS
    assert 'type:"show_lovelace_view"' in JS
    assert "urn:x-cast:com.nabucasa.hast" in JS

    # Browser-local Cast must mirror HA's browser Web Sender, not the
    # server-side Cast integration's system/admin user model.
    assert "_current_browser_refresh_token" in REMOTE
    assert 'getattr(connection, "refresh_token_id", None)' in REMOTE
    assert "hass.auth.async_get_refresh_token" in REMOTE
    assert '"credential_source": "current_browser_session"' in REMOTE
    assert '"refresh_token": refresh.token' in REMOTE
    assert '"client_id": refresh.client_id' in REMOTE
    assert "async_create_system_user" not in REMOTE
    assert "async_create_refresh_token" not in REMOTE
    assert "GROUP_ID_ADMIN" not in REMOTE
    assert "require_ssl=True" in REMOTE
    assert "prefer_external=True" in REMOTE

    # Never revoke the refresh token that backs the active browser connection.
    assert 'token_id == getattr(connection, "refresh_token_id", None)' in REMOTE
    assert 'clientId:credentials.client_id ?? null' in JS
    cast_block = JS[JS.index("  async _castLocalDashboard() {"):JS.index("  async _stopLocalCast() {")]
    assert 'hassUUID:credentials.hass_uuid' not in cast_block
    assert "_localCastTokenId" not in JS
    assert "_releaseLocalCastToken" not in JS
    assert "payload?.error_code" in JS


def test_remote_gateway_copy_and_protocol_are_exposed_in_dashboard_labels_and_docs():
    for key in (
        "remote_sensors",
        "remote_gateway_title",
        "remote_ble_connect",
        "remote_ant_connect",
        "local_cast_choose",
        "cast_ha_devices",
    ):
        assert f'"{key}"' in DASH
    assert "Fitness Remote Gateway Protocol v1" in DOC
    assert "future native senders" in DOC.lower()
    assert "Android" in DOC and "iOS" in DOC and "Windows" in DOC



def test_browser_local_cast_handoff_moves_audio_owner_to_receiver_and_stop_is_live():
    assert 'self._expected_local_cast: dict[str, str] = {}' in TV
    assert 'def expect_local_cast(' in TV
    assert 'def is_local_cast_active(' in TV
    assert 'def is_any_cast_active(' in TV
    assert 'def has_cast_expectation(' in TV
    assert 'vol.Required("type"): "fitness/tv/local_cast_handoff"' in TV
    assert 'vol.Required("type"): "fitness/tv/local_cast_stopped"' in TV
    assert 'handoffArmed = await this._armLocalCastHandoff' in JS
    assert 'type:"fitness/tv/local_cast_handoff"' in JS
    assert 'type:"fitness/tv/local_cast_stopped"' in JS
    assert 'this._localCastSessionActive()' in JS
    assert 'this._localCastServerActive = Boolean(result?.local_cast_active)' in JS
    assert 'stopCast.hidden = !anyCastActive' in JS
    assert 'stopCast.disabled = !anyCastActive' in JS
    assert 'if self.is_any_cast_active(profile_entry_id)' in TV
    assert 'cast_expected = self.has_cast_expectation(profile_entry_id)' in TV
    assert 'if (this._audioOwner && FITNESS_TV_CAST_RECEIVER)' in JS


def test_local_cast_handoff_preserves_playing_state_for_receiver_resume():
    block = TV[TV.index('    def expect_local_cast('):TV.index('    def clear_expected_local_cast(')]
    assert '"command": "stop"' in block
    assert '"reason": "cast_handoff"' in block
    assert 'async_broadcast_media_state' not in block
    handler = JS[JS.index('  async _handleMediaCommand('):JS.index('  async _ackTts(')]
    assert '["session_replaced","cast_handoff"]' in handler

def test_frontend_cache_revision_bumped_for_gateway_release():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in JS
    assert '?v=unreleased-82' in DASH
