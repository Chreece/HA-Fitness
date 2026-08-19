from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def _back_block():
    start = FRONTEND.index("  _handleCastRemoteBackPress(")
    end = FRONTEND.index("  _beginCastRemoteBack(", start)
    return FRONTEND[start:end]


def test_unsolicited_startup_back_marks_session_unreliable_instead_of_arming_exit():
    block = _back_block()
    assert "this._castRemoteBackUnreliable = true" in block
    assert "startup/system Back detected; guarded exit enabled" in block
    startup_start = block.index("if (!this._castRemoteUserEngaged")
    startup_end = block.index("if (Number(this._castRemoteExitArmedUntil", startup_start)
    startup = block[startup_start:startup_end]
    assert "this._showCastExitConfirmation()" not in startup
    assert '_quitCastFromRemote("double back"' not in startup


def test_double_back_no_longer_requires_matching_runtime_key_signature():
    block = _back_block()
    assert "FITNESS_TV_BACK_DISTINCT_PRESS_MS = 280" in FRONTEND
    assert "const signature = this._castRemoteBackSignature(event);" not in block
    assert "authorized === signature" not in block
    assert "Any genuinely second physical Back press may confirm the exit" in block
    assert "const authorization = `physical-back:${Math.round(now)}`;" in block
    assert 'void this._quitCastFromRemote("double back", quitAuthorization)' in block


def test_double_back_still_requires_physical_keydown_and_authorization():
    block = _back_block()
    assert 'const physicalBack = source === "keydown" && !!event;' in block
    assert 'if (!physicalBack)' in block
    assert 'non-physical top-level Back ignored' in block
    quit_start = FRONTEND.index("  async _quitCastFromRemote(")
    quit_end = FRONTEND.index("  _handleCastKeydown(", quit_start)
    quit_block = FRONTEND[quit_start:quit_end]
    assert 'authorization !== String(this._castRemoteExitAuthorization || "")' in quit_block
    assert "receiverContext.stop();" in quit_block


def test_history_never_authorizes_cast_quit():
    pop_start = FRONTEND.index("  _handleCastPopstate(")
    pop_end = FRONTEND.index("  async _quitCastFromRemote(", pop_start)
    pop = FRONTEND[pop_start:pop_end]
    assert "_quitCastFromRemote" not in pop
    assert "_castRemoteExitAuthorization =" not in pop
