from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
TV = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")


def test_restricted_cast_portal_exposes_music_assistant_sendspin_relay():
    assert '"fitness/tv/music/ma/sendspin": ("tv_dashboard", "websocket_tv_music_ma_sendspin")' in ACCOUNTS
    assert 'type:"fitness/tv/music/ma/sendspin"' in JS


def test_cast_routing_precedes_configured_ha_music_output():
    dispatch = TV[TV.index("async def async_dispatch_media_command") : TV.index("async def async_broadcast_media_state")]
    assert "# Cast is the physical/audible authority for this profile." in dispatch
    assert dispatch.index("if cast_client is not None:") < dispatch.index('elif audio_output.startswith("media_player.")')
    assert dispatch.index("elif cast_expected:") < dispatch.index('elif audio_output.startswith("media_player.")')
    assert 'return {"sent": False, "reason": "cast_unavailable"}' in dispatch


def test_cast_handoff_silences_previous_ha_media_player_owner():
    assert "async def _async_silence_ha_output" in TV
    assert 'for service in ("media_stop", "media_pause")' in TV
    claim = TV[TV.index("def _claim_audio_owner") : TV.index("def is_audio_owner")]
    assert 'str(previous or "").startswith("ha:media_player.")' in claim
    assert "self._async_silence_ha_output(str(previous)[3:])" in claim
    assert "self._release_audio_owner_for_cast(profile_entry_id)" in TV[TV.index("def expect_local_cast") : TV.index("def clear_expected_local_cast")]
    assert "self._release_audio_owner_for_cast(profile_entry_id)" in TV[TV.index("def expect_cast") : TV.index("def cast_attempt_is_current")]


def test_controller_browser_does_not_prime_ma_audio_while_cast_or_ha_output_owns_sound():
    helper = JS[JS.index("  _browserMayOwnLocalAudio()") : JS.index("  async _selectMusic", JS.index("  _browserMayOwnLocalAudio()"))]
    assert "if (FITNESS_TV_CAST_RECEIVER) return Boolean(this._audioOwner);" in helper
    assert 'this._castState === "connecting"' in helper
    assert 'this._castState === "connected"' in helper
    assert 'return !output.startsWith("media_player.");' in helper
    select = JS[JS.index("  async _selectMusic") : JS.index("  async _playlistTransport")]
    play = JS[JS.index("  async _playMusic()") : JS.index("  async _pauseMusic()")]
    assert "await this._prepareMALocalAudioFromGesture();" in select
    assert "await this._prepareMALocalAudioFromGesture();" in play


def test_only_audio_owner_may_publish_sendspin_transport_state():
    block = JS[JS.index("  _handleMASendspinState(state)") : JS.index("  _createMASendspinPlayer()")]
    assert "if (this._audioOwner && this._currentMediaContentId && !this._ttsDuckingActive)" in block


def test_cast_map_paint_policy_has_opaque_fallbacks_and_explicit_overlay_layers():
    block = JS[JS.index("  _applyCastMotionPolicy(card)") : JS.index("  _ensureCastCardLivingMotion")]
    assert ".route-wrap,.map,.workout-map,.map-wrap{background-color:" in block
    assert ".map-metrics{display:flex!important;z-index:8!important}" in block
    assert ".workout-map-tools{display:flex!important;z-index:9!important}" in block
    assert ".selected-route,.map-scene svg,.workout-map-scene svg" in block
    assert "will-change:auto!important" in block
    assert "stroke-opacity:1!important" in block
    assert "Some modern\n             Android/Google TV WebViews advertise color-mix/backdrop support" in block
    assert ".strava,.viewer-rpe,.all-facts{background-color:" in block


def test_cast_audio_fix_cache_busts_ha_and_restricted_portal_resources():
    assert '_RESOURCE_URL += "&build=cast-ui-146"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-146"' in ACCOUNTS
    assert 'fitness-dashboard.js?v={frontend_cache_version}' in ACCOUNTS
