from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def _method(name: str, next_name: str) -> str:
    return JS[JS.index(f"  {name}("):JS.index(f"  {next_name}(")]


def test_cast_toolbar_has_one_explicit_reveal_helper_for_dashboard_browser():
    helper = _method("_revealCastToolbarFromDashboardBrowser", "_toolbarIsBeingBrowsed")
    assert "FITNESS_TV_CAST_RECEIVER" in helper
    assert "this._toolbarAutoHide" in helper
    assert "this._toolbarHidden" in helper
    assert "this._setToolbarHidden(false)" in helper
    assert 'this._castRemoteSection = toolbar' in helper


def test_reveal_button_is_an_allowed_cast_toolbar_trigger():
    start = JS.index("    const revealToolbar = (event) => {")
    block = JS[start:start + 700]
    assert 'this._revealCastToolbarFromDashboardBrowser("reveal-button")' in block


def test_remote_up_reveals_only_from_dashboard_browser_not_from_cards():
    arrows = _method("_handleCastRemoteArrow", "_handleCastRemoteActivate")
    assert 'current?.classList?.contains("dashboard-switcher")' in arrows
    assert 'this._revealCastToolbarFromDashboardBrowser("remote-outer-up")' in arrows
    assert 'this._castRemoteSection?.classList?.contains("dashboard-switcher")' in arrows
    assert 'this._revealCastToolbarFromDashboardBrowser("remote-inner-up")' in arrows
    assert '(!next || next === current)' not in arrows


def test_cast_scroll_wheel_and_pointer_proximity_cannot_reveal_toolbar():
    wire = _method("_wireToolbarAutoHide", "_setLayoutEditing")
    assert 'if (FITNESS_TV_CAST_RECEIVER) return;' in wire
    assert 'if (!FITNESS_TV_CAST_RECEIVER && Number(scrollSurface.scrollTop || 0) <= 12) show();' in wire
    assert 'if (!FITNESS_TV_CAST_RECEIVER && this._toolbarAutoHide && Number(event.deltaY || 0) < 0' in wire
    assert 'if (!FITNESS_TV_CAST_RECEIVER && this._toolbarAutoHide && Number(event.clientY || 999) <= 72) show();' in wire


def test_cast_toolbar_hint_documents_explicit_reveal_contract():
    assert 'On Cast, show it again only with the down-arrow button or by pressing Up from the dashboard browser.' in DASH
    assert 'Στο Cast εμφανίζεται ξανά μόνο με το κουμπί κάτω βέλους ή πατώντας Πάνω από τον browser πινάκων.' in DASH


def test_v155_cache_contract_for_both_receiver_paths():
    assert '_RESOURCE_URL += "&build=cast-ui-155"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS
