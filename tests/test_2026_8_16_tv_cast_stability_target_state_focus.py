from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_cast_picker_checks_the_entity_selected_in_the_picker_not_only_profile_default():
    block = FRONTEND[FRONTEND.index("  async _castDashboard(entityId)"):FRONTEND.index("  async _stopCastDashboard", FRONTEND.index("  async _castDashboard(entityId)"))]
    assert 'this._hass?.states?.[entityId]' not in block
    assert 'entity_id:entityId' in block
    assert 'this._activeCastTarget = entityId' in block


def test_cast_picker_does_not_guess_physical_tv_readiness_from_media_player_state():
    assert "TV is off. Waking it first" not in FRONTEND
    assert "TV is off. Waking it first" not in DASHBOARD
    assert "Η TV είναι κλειστή" not in DASHBOARD
    cast = FRONTEND[FRONTEND.index("  async _castDashboard(entityId)"):FRONTEND.index("  async _stopCastDashboard", FRONTEND.index("  async _castDashboard(entityId)"))]
    assert 'this._hass?.states?.[entityId]' not in cast
    assert 'l.cast_connecting || "Connecting to TV…"' in cast
    start = FRONTEND[FRONTEND.index("  async _startTvWorkout(profile, row)"):FRONTEND.index("  async _openConfigure", FRONTEND.index("  async _startTvWorkout(profile, row)"))]
    assert "targetOff" not in start
    assert 'l.start_tv_workout_preparing || "Preparing TV, music and workout…"' in start


def test_cast_receiver_error_is_latched_against_heartbeat_replay_loops():
    assert 'this._castFailedMediaContentId = mediaContentId;' in FRONTEND
    ensure = FRONTEND[FRONTEND.index("  async _ensureCastMusicPlayback(state = {})"):FRONTEND.index("  _startHeartbeat()", FRONTEND.index("  async _ensureCastMusicPlayback(state = {})"))]
    assert 'if (!state.playing || state.error || !mediaContentId) return;' in ensure
    assert 'if (this._castFailedMediaContentId === mediaContentId) return;' in ensure
    handle = FRONTEND[FRONTEND.index("  async _handleMediaCommand(command, data = {})"):FRONTEND.index("  async _ackTts", FRONTEND.index("  async _handleMediaCommand(command, data = {})"))]
    assert '["select","play"].includes(String(command || ""))' in handle
    assert 'this._castFailedMediaContentId = "";' in handle


def test_cast_caf_player_requests_are_not_wired_into_fitness_audio_controls():
    block = FRONTEND[FRONTEND.index("  _scheduleCastFrameworkRemoteAdapter()") : FRONTEND.index("  _bindBrowserMediaSessionAdapter()") ]
    for token in ("REQUEST_PLAY", "REQUEST_PAUSE", "REQUEST_STOP", "REQUEST_SEEK", "getPlayerManager"):
        assert token not in block
    assert 'CastReceiverContext?.getInstance?.()' in block


def test_remote_focus_visuals_have_clear_toolbar_spacing_and_modern_press_feedback():
    assert ':host([fitness-cast-receiver]) .tv-toolbar{grid-template-columns:auto minmax(70px,120px) auto minmax(130px,1fr);gap:3px;margin-bottom:11px' in FRONTEND
    # Keep the focus effect on the real element: launcher-style lift + outer halo,
    # not pseudo overlays that can steal/obscure TV remote interaction.
    assert '.fitness-remote-section-selected::after' not in FRONTEND
    assert '.fitness-remote-section-selected{outline:2px solid color-mix' in FRONTEND
    assert 'transform:scale(1.028)' in FRONTEND
    assert '.tv-toolbar.fitness-remote-section-selected{transform:scale(1.012)}' in FRONTEND
    assert '0 0 24px 8px color-mix(in srgb,var(--primary-color,#03a9f4) 29%,transparent)' in FRONTEND
    assert '.fitness-remote-section-active' in FRONTEND
    assert 'transform:scale(1.012)' in FRONTEND
    focus = FRONTEND[FRONTEND.index("  _markCastRemoteFocus(element, pressed = false)"):FRONTEND.index("  _ensureCastRemoteOuterFocus()") ]
    assert 'scale(1.065)' in focus
    assert 'scale(1.02)' in focus
    assert 'brightness(1.15) saturate(1.09)' in focus
    # Inner controls need an unmistakable outer halo and lift from TV distance.
    assert 'transformOrigin:element.style.transformOrigin' in focus
    assert 'element.style.transformOrigin = "center center"' in focus
    assert '0 0 0 6px color-mix(in srgb,var(--primary-color,#03a9f4) 52%,transparent)' in focus
    assert '0 0 22px 8px color-mix(in srgb,var(--primary-color,#03a9f4) 42%,transparent)' in focus
    assert '0 16px 36px rgba(0,0,0,.40)' in focus
    assert 'element.style.backgroundColor = "color-mix(in srgb,var(--primary-color,#03a9f4) 18%,var(--secondary-background-color))"' in focus
    assert 'element.style.backgroundColor = "color-mix(in srgb,var(--primary-color,#03a9f4) 24%,var(--secondary-background-color))"' in focus
    assert 'element.style.accentColor = "var(--primary-color,#03a9f4)"' in focus
