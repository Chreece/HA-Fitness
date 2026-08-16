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
    startup = block[block.index("if (!this._castRemoteUserEngaged"):block.index("const signature", block.index("if (!this._castRemoteUserEngaged"))]
    assert "this._showCastExitConfirmation()" not in startup


def test_unreliable_back_requires_recent_non_back_user_input():
    assert "FITNESS_TV_BACK_GUARDED_RECENT_INPUT_MS = 4000" in FRONTEND
    assert "_castRemoteCanArmGuardedExit(now)" in FRONTEND
    block = _back_block()
    assert "idle/system Back ignored by guarded exit" in block
    assert "this._castRemoteLastNonBackInputAt = performance.now();" in FRONTEND
    assert "this._castRemoteLastNonBackInputAt = now;" in FRONTEND


def test_double_back_exit_requires_same_physical_key_signature_and_authorization():
    block = _back_block()
    assert "const signature = this._castRemoteBackSignature(event);" in block
    assert "authorized && authorized === signature" in block
    assert 'void this._quitCastFromRemote("double back", quitAuthorization)' in block
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
