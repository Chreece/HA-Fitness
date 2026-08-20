from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def _remote_block() -> str:
    return FRONTEND[
        FRONTEND.index("  _clearCastExitConfirmation() {") :
        FRONTEND.index("  _claimWindowController() {")
    ]


def test_top_level_cast_exit_requires_physical_remote_keydown():
    remote = _remote_block()
    back = remote[
        remote.index("  _handleCastRemoteBackPress(") :
        remote.index("  _beginCastRemoteBack(")
    ]
    assert 'const physicalBack = source === "keydown" && !!event;' in back
    assert 'if (!physicalBack)' in back
    assert 'non-physical top-level Back ignored' in back
    outer = back[back.index('this._ensureCastRemoteOuterFocus()'):]
    assert outer.index('if (!physicalBack)') < outer.index('this._showCastExitConfirmation();')


def test_popstate_can_never_arm_or_complete_cast_exit():
    remote = _remote_block()
    pop = remote[
        remote.index("  _handleCastPopstate(event)") :
        remote.index("  async _quitCastFromRemote(")
    ]
    assert '_handleCastRemoteBackPress(event, "history")' not in pop
    assert '_showCastExitConfirmation' not in pop
    assert '_quitCastFromRemote' not in pop
    assert 'this._leaveCastRemoteSection("history-fallback")' in pop
    assert 'this._ensureCastBackGuard();' in pop


def test_receiver_startup_grace_blocks_stray_back_from_arming_exit():
    assert "FITNESS_TV_CAST_EXIT_STARTUP_GRACE_MS = 12000" in FRONTEND
    assert "this._castRemoteExitAllowedAfter" in FRONTEND
    assert "this._castRemoteUserEngaged = false" in FRONTEND
    remote = _remote_block()
    back = remote[
        remote.index("  _handleCastRemoteBackPress(") :
        remote.index("  _beginCastRemoteBack(")
    ]
    assert '!this._castRemoteUserEngaged && now < Number(this._castRemoteExitAllowedAfter || 0)' in back
    assert 'startup/system Back detected; guarded exit enabled' in back


def test_dpad_ok_or_media_input_lifts_startup_grace_without_changing_back_mapping():
    remote = _remote_block()
    keydown = remote[remote.index("  _handleCastKeydown(event)") :]
    assert 'if (action === "back")' in keydown
    assert 'this._castRemoteUserEngaged = true;' in keydown
    assert keydown.index('if (action === "back")') < keydown.index('this._castRemoteUserEngaged = true;')
    assert 'BrowserBack:"back"' in FRONTEND
    assert '166:"back"' in FRONTEND
