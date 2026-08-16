from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def _remote_block() -> str:
    return FRONTEND[
        FRONTEND.index("  _clearCastExitConfirmation() {") :
        FRONTEND.index("  _claimWindowController() {")
    ]


def test_cast_remote_uses_two_level_section_then_control_navigation():
    remote = _remote_block()
    assert 'this._castRemoteMode = "outer"' in FRONTEND
    assert "_castRemoteSections()" in remote
    assert 'const toolbar = this.shadowRoot?.querySelector(".tv-toolbar")' in remote
    assert 'this.shadowRoot?.querySelectorAll(".tv-card-slot")' in remote
    assert "_enterCastRemoteSection(section = this._castRemoteSection)" in remote
    assert 'this._castRemoteMode = "inner"' in remote
    assert "_castRemoteInnerElements(section)" in remote
    assert "_leaveCastRemoteSection(source = \"back\")" in remote
    assert 'this._castRemoteMode = "outer"' in remote


def test_outer_dpad_selects_sections_and_ok_is_required_before_controls():
    remote = _remote_block()
    arrows = remote[remote.index("  _handleCastRemoteArrow(event,"):remote.index("  _handleCastRemoteActivate(event,")]
    activate = remote[remote.index("  _handleCastRemoteActivate(event,"):remote.index("  _handleCastRemoteBackPress(event")]
    assert 'if (this._castRemoteMode !== "inner")' in arrows
    assert "const sections = this._castRemoteSections();" in arrows
    assert "this._markCastRemoteSection(this._castRemoteSection, false);" in arrows
    assert 'if (this._castRemoteMode !== "inner")' in activate
    assert "this._enterCastRemoteSection();" in activate
    assert "target.click?.();" in activate


def test_back_is_captured_on_keydown_keyup_and_browser_history():
    assert 'window.addEventListener("keydown", this._boundCastKeydown, true);' in FRONTEND
    assert 'window.addEventListener("keyup", this._boundCastKeyup, true);' in FRONTEND
    assert 'window.addEventListener("popstate", this._boundCastPopstate, true);' in FRONTEND
    remote = _remote_block()
    assert "_castRemoteBackKey(event)" in remote
    assert 'BrowserBack:"back"' in FRONTEND
    assert 'GoBack:"back"' in FRONTEND
    assert 'NavigateOut:"back"' in FRONTEND
    assert '4:"back"' in FRONTEND
    assert '166:"back"' in FRONTEND
    assert '461:"back"' in FRONTEND
    assert '10009:"back"' in FRONTEND
    assert "_ensureCastBackGuard()" in remote
    assert "history.pushState" in remote
    assert "__fitnessTvBackGuard:true" in remote


def test_short_back_leaves_inner_section_and_outer_back_arms_double_press_exit():
    remote = _remote_block()
    back = remote[remote.index("  _handleCastRemoteBackPress("):remote.index("  async _quitCastFromRemote(")]
    assert 'if (this._castRemoteMode === "inner")' in back
    assert "this._leaveCastRemoteSection(source);" in back
    assert "this._showCastExitConfirmation();" in back
    assert 'void this._quitCastFromRemote("double back", quitAuthorization)' in back
    assert "FITNESS_TV_BACK_CONFIRM_MS = 2800" in FRONTEND


def test_one_physical_back_or_held_repeat_cannot_count_as_second_press():
    remote = _remote_block()
    back = remote[remote.index("  _handleCastRemoteBackPress("):remote.index("  _beginCastRemoteBack(")]
    assert "FITNESS_TV_BACK_DISTINCT_PRESS_MS = 280" in FRONTEND
    assert "this._castRemoteBackLastEventAt" in back
    assert "< FITNESS_TV_BACK_DISTINCT_PRESS_MS" in back
    assert "this._castRemoteBackLastEventAt = now;" in back
    assert "this._ensureCastBackGuard();" in back


def test_second_top_level_back_exits_cast_but_hold_detection_is_gone():
    remote = _remote_block()
    assert "FITNESS_TV_BACK_HOLD_MS" not in FRONTEND
    assert "FITNESS_TV_BACK_SEQUENCE_IDLE_MS" not in FRONTEND
    assert "held repeat" not in remote
    assert "held history" not in remote
    back = remote[remote.index("  _handleCastRemoteBackPress("):remote.index("  _beginCastRemoteBack(")]
    assert "this._castRemoteExitArmedUntil" in back
    assert 'void this._quitCastFromRemote("double back", quitAuthorization)' in back


def test_double_back_stops_backend_cast_and_receiver_application():
    remote = _remote_block()
    quit_block = remote[remote.index("  async _quitCastFromRemote("):remote.index("  _handleCastKeydown(event)")]
    assert 'await this._syncMediaState({playing:false, error:false});' in quit_block
    assert 'this._hass.callService("fitness", "stop_tv_dashboard"' in quit_block
    assert 'type:"fitness/tv/local_cast_stopped"' in quit_block
    assert 'reason:"tv_remote_double_back"' in quit_block
    assert "CastReceiverContext?.getInstance?.()" in quit_block
    assert "receiverContext.stop();" in quit_block


def test_exit_confirmation_is_localized_and_remote_debug_overlay_is_removed():
    assert 'id="cast-exit-confirm" class="cast-exit-confirm"' in FRONTEND
    assert 'l.cast_exit_confirm || "Press Back once more to exit Cast"' in FRONTEND
    assert 'id="remote-diagnostic"' not in FRONTEND
    assert ':host([fitness-cast-receiver]) .remote-diagnostic' not in FRONTEND
    assert "FITNESS_TV_REMOTE_DIAGNOSTIC_STORAGE" not in FRONTEND
    assert 'console.debug(`[Fitness TV remote]' in FRONTEND
