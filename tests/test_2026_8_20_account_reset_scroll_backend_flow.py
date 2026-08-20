from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def test_new_personal_code_replaces_single_password_and_revokes_sessions():
    block = ACCOUNTS[ACCOUNTS.index("async def async_generate_temporary_password"):ACCOUNTS.index("async def _async_set_password")]
    assert 'await self._async_set_password(row, candidate, force_change=True)' in block
    assert 'self._revoke_account_sessions(account_id)' in block
    setter = ACCOUNTS[ACCOUNTS.index("async def _async_set_password"):ACCOUNTS.index("async def async_change_credentials")]
    assert 'row["password_salt"] = salt.hex()' in setter
    assert 'row["password_hash"] = digest' in setter
    assert 'password_hashes' not in setter


def test_account_password_refresh_keeps_same_row_in_same_visual_position():
    assert 'this._accessAdminScrollRestore = {' in JS
    assert 'scrollTop:Number(currentBody?.scrollTop || 0)' in JS
    assert 'anchorOffset:(bodyRect && anchorRect)' in JS
    assert 'body.scrollTop = Math.max(0, Number(restoreScroll.scrollTop || 0))' in JS
    assert 'body.scrollTop += Number(rowRect.top - bodyRect.top - wantedOffset)' in JS


def test_embedded_backend_settings_respect_visible_tv_viewport_and_compact_save():
    assert '.backend-flow-backdrop{background:rgba(0,0,0,.18)!important;position:fixed!important;top:var(--modal-effective-top)!important' in JS
    assert 'height:min(860px,calc(100% - 2px))!important;max-height:calc(100% - 2px)!important' in JS
    flow = JS[JS.index("class FitnessBackendFlow"):JS.index('if (!customElements.get("fitness-backend-flow")')]
    assert '.flow-actions>button{flex:0 0 auto;min-width:118px;max-width:min(220px,100%)}' in flow
    assert '.flow-head{flex:0 0 auto;position:sticky;top:0' in flow
    assert 'if (cardPickerPreview) backdrop?.style?.setProperty("--modal-top", "4px")' in JS
    assert 'if (backendFlowModal) backdrop?.style?.setProperty("--modal-top", "4px")' not in JS
    assert '.flow-body{display:grid;gap:9px' in flow and 'overflow-y:auto' in flow


def test_frontend_revision_95_is_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in JS
    assert 'frontend_version = "unreleased-110"' in ACCOUNTS
