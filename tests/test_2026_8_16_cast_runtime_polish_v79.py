from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
JS = (BASE / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
TV = (BASE / "custom_components/fitness/tv_dashboard.py").read_text(encoding="utf-8")
DASH = (BASE / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
MANAGER = (BASE / "custom_components/fitness/manager.py").read_text(encoding="utf-8")


def test_now_playing_progress_is_capped_instead_of_filling_toolbar():
    assert 'width:min(420px,100%);max-width:420px;justify-self:start' in JS
    assert 'width:min(300px,100%);max-width:300px' in JS


def test_intentional_audio_teardown_cannot_publish_selected_state_during_cast_handoff():
    assert 'this._suppressMusicElementStateUntil = 0' in JS
    assert 'if (this._musicElementStateSuppressed()) { this._updateMediaControls(); return; }' in JS
    assert 'audio === this._musicAudio' in JS
    assert 'performance.now() + 750' in JS


def test_live_cast_receiver_heartbeat_is_authoritative_over_transient_cast_entity_state():
    assert 'def _cast_receiver_heartbeat_alive(' in TV
    block = TV[TV.index('    def is_cast_active('):TV.index('    def _ensure_cast_target_monitor', TV.index('    def is_cast_active('))]
    assert 'return self._cast_receiver_heartbeat_alive(profile_entry_id)' in block
    assert '_cast_target_state_ok' not in block
    reconcile = TV[TV.index('    async def async_reconcile_cast_target('):TV.index('    async def async_reconcile_profile', TV.index('    async def async_reconcile_cast_target('))]
    assert 'and not self._cast_receiver_heartbeat_alive(profile_entry_id)' in reconcile


def test_profile_playback_routes_tts_to_current_audio_owner_not_configured_speaker():
    assert 'profile_media_playing = bool(' in MANAGER
    assert 'hub.is_active(self.entry.entry_id)' in MANAGER
    assert 'hub.media_state(self.entry.entry_id).get("playing")' in MANAGER
    assert 'local Cast receiver' in MANAGER


def test_stop_cast_uses_actual_active_session_not_profile_default():
    assert 'async _stopCurrentCast()' in JS
    assert 'if (this._castState === "idle") return;' in JS
    assert 'if (this._castMode === "server" && this._activeCastTarget)' in JS
    assert 'await this._stopCastDashboard(String(this._activeCastTarget));' in JS
    assert 'String(this._activeCastTarget || root.querySelector("#cast-target")?.value || "")' in JS
    stop = DASH[DASH.index('async def async_stop_tv_dashboard('):DASH.index('async def _async_cast_receiver_is_stable', DASH.index('async def async_stop_tv_dashboard('))]
    assert 'active_target = str(hub.cast_target(entry.entry_id) or "").strip()' in stop
    assert 'active_target or media_player_override or config.get(CONF_TV_MEDIA_PLAYER_ID)' in stop


def test_scale_slider_pushes_live_preview_to_cast_receiver():
    assert '  _previewTvScale(value) {' in JS
    assert '  _previewProfileScale(profile, value) {' in JS
    assert JS.count('type:"fitness/tv/preferences/save"') >= 4
    assert 'this._previewTvScale(scaleInput.value);' in JS
    assert 'this._previewProfileScale(profile, scaleInput.value);' in JS
    assert 'hub.broadcast_settings(' in TV
