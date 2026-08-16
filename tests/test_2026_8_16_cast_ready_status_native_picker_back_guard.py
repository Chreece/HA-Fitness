from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def _remote_block() -> str:
    return FRONTEND[
        FRONTEND.index("  _clearCastExitConfirmation() {") :
        FRONTEND.index("  _claimWindowController() {")
    ]


def test_native_picker_escape_is_non_destructive_cancel_not_cast_exit_back():
    assert 'Escape:"cancel"' in FRONTEND
    assert 'Esc:"cancel"' in FRONTEND
    assert '27:"cancel"' in FRONTEND
    remote = _remote_block()
    cancel = remote[remote.index("  _handleCastRemoteCancel("):remote.index("  _handleCastRemoteBackPress(")]
    assert 'this._clearCastExitConfirmation();' in cancel
    assert 'if (this._castRemoteMode === "inner") this._leaveCastRemoteSection(source);' in cancel
    assert "_showCastExitConfirmation" not in cancel
    assert "_quitCastFromRemote" not in cancel


def test_select_native_ui_owns_close_back_and_follow_up_events_are_quarantined():
    remote = _remote_block()
    native = remote[remote.index("  _castRemoteNativePickerFromEvent("):remote.index("  _castRemoteBackspaceKey(")]
    assert 'String(node?.tagName || "").toUpperCase() === "SELECT"' in native
    assert 'FITNESS_TV_NATIVE_CONTROL_BACK_SUPPRESS_MS = 900' in FRONTEND
    assert 'this._castRemoteNativeControlBackSuppressUntil' in native
    assert 'this._clearCastExitConfirmation();' in native
    keydown = remote[remote.index("  _handleCastKeydown(event)"):]
    assert 'if (this._yieldCastRemoteKeyToNativePicker(event, action)) return;' in keydown
    back = remote[remote.index("  _handleCastRemoteBackPress("):remote.index("  _beginCastRemoteBack(")]
    assert 'this._castRemoteNativeControlBackSuppressUntil' in back
    pop = remote[remote.index("  _handleCastPopstate(event)"):remote.index("  async _quitCastFromRemote(")]
    assert 'this._castRemoteNativeControlBackSuppressUntil' in pop


def test_directional_navigation_can_never_become_immediate_history_back_exit():
    remote = _remote_block()
    keydown = remote[remote.index("  _handleCastKeydown(event)"):]
    assert 'FITNESS_TV_NAV_HISTORY_SUPPRESS_MS = 550' in FRONTEND
    assert 'this._castRemoteNavigationHistorySuppressUntil = performance.now() + FITNESS_TV_NAV_HISTORY_SUPPRESS_MS;' in keydown
    pop = remote[remote.index("  _handleCastPopstate(event)"):remote.index("  async _quitCastFromRemote(")]
    assert 'this._castRemoteNavigationHistorySuppressUntil' in pop
    assert 'swallowed native-picker/navigation history Back' in pop


def test_cast_picker_and_start_on_tv_use_neutral_preparing_status_not_idle_guess():
    cast = FRONTEND[FRONTEND.index("  async _castDashboard(entityId)"):FRONTEND.index("  async _stopCastDashboard", FRONTEND.index("  async _castDashboard(entityId)"))]
    assert "targetOff" not in cast
    assert "idle or not responding yet" not in cast
    assert 'l.cast_connecting || "Connecting to TV…"' in cast
    start = FRONTEND[FRONTEND.index("  async _startTvWorkout(profile, row)"):FRONTEND.index("  async _openConfigure", FRONTEND.index("  async _startTvWorkout(profile, row)"))]
    assert "targetOff" not in start
    assert "idle or not responding yet" not in start
