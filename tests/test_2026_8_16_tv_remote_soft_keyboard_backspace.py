from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def _remote_block() -> str:
    return FRONTEND[
        FRONTEND.index("  _clearCastExitConfirmation() {") :
        FRONTEND.index("  _claimWindowController() {")
    ]


def test_text_entry_mode_is_tracked_for_remote_and_pointer_activation():
    remote = _remote_block()
    assert "_castRemoteTextEntryControl(element)" in remote
    assert "_beginCastRemoteTextEntry(element, source = \"activate\")" in remote
    assert 'this._beginCastRemoteTextEntry(target, "activate")' in remote
    assert 'this._beginCastRemoteTextEntry(control, "pointer")' in remote
    assert 'window.addEventListener("input", this._boundCastTextInput, true);' in FRONTEND
    assert 'window.addEventListener("focusout", this._boundCastFocusOut, true);' in FRONTEND


def test_backspace_remains_legacy_back_fallback_but_is_yielded_to_editable_fields():
    remote = _remote_block()
    # Preserve compatibility for TV runtimes that expose their Back key as code 8.
    assert 'Backspace:"back"' in FRONTEND
    assert '8:"back"' in FRONTEND
    assert '_castRemoteBackspaceKey(event)' in remote
    yield_block = remote[
        remote.index("  _yieldCastRemoteKeyToTextEntry(") :
        remote.index("  _registerCastRemoteCapability(")
    ]
    assert "if (backspace && editable)" in yield_block
    assert 'this._beginCastRemoteTextEntry(editable, "backspace")' in yield_block
    assert "this._consumeCastRemoteEvent(event)" not in yield_block
    assert "preventDefault" in yield_block  # explanatory comment: intentionally not called
    assert "native TV keyboard must receive" in yield_block


def test_keyboard_back_dismissal_cannot_arm_or_complete_cast_exit():
    remote = _remote_block()
    assert "FITNESS_TV_TEXT_ENTRY_BACK_SUPPRESS_MS = 900" in FRONTEND
    yield_block = remote[
        remote.index("  _yieldCastRemoteKeyToTextEntry(") :
        remote.index("  _registerCastRemoteCapability(")
    ]
    assert 'if (action === "back")' in yield_block
    assert "this._castRemoteTextEntryBackSuppressUntil = performance.now() + FITNESS_TV_TEXT_ENTRY_BACK_SUPPRESS_MS" in yield_block
    assert 'this._releaseCastRemoteTextEntrySoon("keyboard-back")' in yield_block
    assert 'this._recordCastRemoteDiagnostic("text-entry", "yield Back to keyboard")' in yield_block

    popstate = remote[
        remote.index("  _handleCastPopstate(event)") :
        remote.index("  async _quitCastFromRemote(")
    ]
    assert "this._castRemoteTextEntryActive" in popstate
    assert "this._castRemoteTextEntryBackSuppressUntil" in popstate
    assert 'this._recordCastRemoteDiagnostic("text-entry", "swallowed keyboard/history Back")' in popstate
    assert "this._ensureCastBackGuard();" in popstate


def test_cast_keydown_yields_to_ime_before_dashboard_navigation_or_back():
    remote = _remote_block()
    keydown = remote[remote.index("  _handleCastKeydown(event)") :]
    assert "if (this._yieldCastRemoteKeyToTextEntry(event, action)) return;" in keydown
    assert keydown.index("_yieldCastRemoteKeyToTextEntry") < keydown.index('if (action === "back")')
    assert keydown.index("_yieldCastRemoteKeyToTextEntry") < keydown.index('if (action === "activate")')


def test_leaving_section_or_receiver_clears_text_entry_mode():
    remote = _remote_block()
    leave = remote[
        remote.index('  _leaveCastRemoteSection(source = "back")') :
        remote.index("  _moveCastRemoteSpatial(")
    ]
    assert "this._endCastRemoteTextEntry(`leave-${source}`);" in leave
    assert 'this._endCastRemoteTextEntry("hidden")' in FRONTEND
    assert 'this._endCastRemoteTextEntry("disconnect")' in FRONTEND
