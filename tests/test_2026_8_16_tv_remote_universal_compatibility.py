from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_remote_input_adapter_normalizes_standard_android_tizen_and_webos_keys():
    assert 'const FITNESS_TV_REMOTE_KEY_ACTIONS = Object.freeze({' in FRONTEND
    assert 'ArrowLeft:"left"' in FRONTEND
    assert 'NavigateIn:"activate"' in FRONTEND
    assert 'NavigateOut:"back"' in FRONTEND
    assert 'BrowserBack:"back"' in FRONTEND
    assert 'Escape:"cancel"' in FRONTEND
    assert 'Esc:"cancel"' in FRONTEND
    assert '27:"cancel"' in FRONTEND
    # Android KEYCODE_BACK, LG/webOS Back, Samsung/Tizen Back.
    assert '4:"back"' in FRONTEND
    assert '461:"back"' in FRONTEND
    assert '10009:"back"' in FRONTEND
    assert '_castRemoteInputAction(event)' in FRONTEND


def test_vendor_and_standard_media_keys_map_to_one_fitness_media_adapter():
    for token in (
        'MediaPlayPause:"media_toggle"',
        'MediaPlay:"media_play"',
        'MediaPause:"media_pause"',
        'MediaStop:"media_stop"',
        'MediaTrackNext:"media_next"',
        'MediaTrackPrevious:"media_previous"',
        '412:"media_rewind"',
        '413:"media_stop"',
        '415:"media_play"',
        '417:"media_forward"',
        '10252:"media_toggle"',
    ):
        assert token in FRONTEND
    assert 'async _dispatchCastRemoteMediaAction(action, source = "key", data = {})' in FRONTEND
    assert 'await this._playlistTransport("next")' in FRONTEND
    assert 'await this._playlistTransport("previous")' in FRONTEND
    assert 'await this._sendMediaCommand("seek", {position})' in FRONTEND


def test_google_cast_caf_is_detected_without_bridging_its_media_request_pipeline():
    block = FRONTEND[
        FRONTEND.index("  _scheduleCastFrameworkRemoteAdapter()"):
        FRONTEND.index("  _bindBrowserMediaSessionAdapter()")
    ]
    assert 'CastReceiverContext?.getInstance?.()' in block
    assert 'this._registerCastRemoteCapability("cast-caf", "receiver_context")' in block
    # Fitness audio is an independent dashboard Audio/MA transport. CAF's own
    # PlayerManager request events must not be mirrored back into Fitness, or
    # PLAY/STOP state can feed back into the dashboard and restart a failing stream.
    assert 'REQUEST_PLAY' not in block
    assert 'REQUEST_PAUSE' not in block
    assert 'REQUEST_STOP' not in block
    assert 'REQUEST_SEEK' not in block
    assert 'getPlayerManager' not in block
    assert 'manager.addEventListener' not in block
    assert '.setMessageInterceptor(' not in block
    assert '.setSupportedMediaCommands(' not in block


def test_browser_media_session_adds_hardware_media_control_fallback():
    block = FRONTEND[
        FRONTEND.index("  _bindBrowserMediaSessionAdapter()"):
        FRONTEND.index("  async _dispatchCastRemoteMediaAction(")
    ]
    assert 'navigator?.mediaSession?.setActionHandler' in block
    for action in ("play", "pause", "stop", "previoustrack", "nexttrack", "seekbackward", "seekforward", "seekto"):
        assert f'["{action}",' in block or f', ["{action}",' in block
    assert 'mediaSession.setActionHandler(browserAction' in block
    assert 'mediaSession.setActionHandler(action, null)' in block


def test_pointer_remote_clicks_sync_focus_without_intercepting_pointer_behavior():
    assert 'window.addEventListener("click", this._boundCastPointerClick, true);' in FRONTEND
    assert 'window.removeEventListener("click", this._boundCastPointerClick, true);' in FRONTEND
    block = FRONTEND[
        FRONTEND.index("  _handleCastPointerClick(event)"):
        FRONTEND.index("  _scheduleCastFrameworkRemoteAdapter()")
    ]
    assert 'event?.isTrusted === false' in block
    assert 'this._castRemoteMode = "inner"' in block
    assert 'this._markCastRemoteSection(section, true)' in block
    assert 'preventDefault' not in block


def test_capabilities_are_observed_without_restoring_on_screen_debug_overlay():
    assert 'globalThis.__fitnessTvRemoteCapabilities = snapshot;' in FRONTEND
    assert 'id="remote-diagnostic"' not in FRONTEND
    assert 'FITNESS_TV_REMOTE_DIAGNOSTIC_STORAGE' not in FRONTEND
