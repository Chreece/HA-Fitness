from pathlib import Path
import json
import zlib

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
ACCESS = (ROOT / "custom_components/fitness/access_control.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")
GARMIN = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text(encoding="utf-8")
GFDI = (ROOT / "custom_components/fitness/device_adapters/garmin/gfdi.py").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def _method(name: str, next_name: str) -> str:
    return JS[JS.index(f"  {name}("):JS.index(f"  {next_name}(")]


def test_tv_dense_masonry_no_longer_manufactures_a_source_order_last_row():
    layout = _method("_applyDashboardCardLayout", "_wireCardResize")
    assert "wrappers.length % logicalColumns" not in layout
    assert 'const packUnits = 200' in layout
    assert 'const skyline = Array(packUnits).fill(0)' in layout
    assert 'centerDistance = Math.abs((startUnit + widthUnits / 2) - packUnits / 2)' in layout
    assert 'grid.style.height = `${Math.ceil(totalHeight)}px`' in layout


def test_hidden_toolbar_is_not_spatial_target_and_only_dashboard_browser_up_reveals_it():
    spatial = _method("_moveCastRemoteSpatial", "_handleCastRemoteArrow")
    arrows = _method("_handleCastRemoteArrow", "_handleCastRemoteActivate")
    assert "this._visibleCastRemoteElement(rawToolbar)" in spatial
    assert 'key === "ArrowUp"' in arrows
    assert 'current?.classList?.contains("dashboard-switcher")' in arrows
    assert 'this._revealCastToolbarFromDashboardBrowser("remote-outer-up")' in arrows
    assert "(!next || next === current)" not in arrows
    assert "_isTopDashboardCard(current)" not in arrows


def test_tv_remote_selection_uses_depth_and_unselected_sections_recede():
    assert 'remote-section-engaged' in JS
    assert 'perspective:1200px' in JS
    assert 'translateZ(-34px) scale(.982)' in JS
    assert 'translateZ(42px) scale(1.026)' in JS
    assert 'translateZ(52px) scale(1.018)' in JS


def test_recovery_score_and_all_cast_card_motion_are_static_on_tv():
    assert ':host([fitness-tv-display]) .recovery-score-track i' in JS
    assert 'transform:none!important' in JS
    cast_motion = _method("_applyCastMotionPolicy", "_ensureCastCardLivingMotion")
    assert 'data-fitness-cast-static' in cast_motion
    assert 'animation:none!important;transition:none!important' in cast_motion
    assert 'card.removeAttribute("fitness-animations")' in cast_motion


def test_double_back_uses_distinct_physical_presses_and_ignores_focus_trail_for_physical_back():
    back = _method("_handleCastRemoteBackPress", "_beginCastRemoteBack")
    assert "FITNESS_TV_BACK_DISTINCT_PRESS_MS = 110" in JS
    assert "event?.repeat" in back
    assert "while (!physicalBack && this._castRemoteSectionTrail?.length)" in back
    inner = back[back.index('if (this._castRemoteMode === "inner")'):back.index("this._ensureCastRemoteOuterFocus()")]
    assert "this._showCastExitConfirmation()" not in inner
    assert "Back inside a card/menu is navigation" in inner
    assert 'void this._quitCastFromRemote("double back", quitAuthorization)' in back


def test_accounts_use_profile_domain_and_language_and_admins_have_no_redundant_view_grants():
    start = JS.index("  _renderAccessAdmin(snapshot, oneTimeSecret = null)")
    account_ui = JS[start:JS.index("  _style() {", start)]
    assert "data-account-language" not in account_ui
    assert "data-account-slug" not in account_ui
    assert "data-account-username" in account_ui
    assert 'const remoteUrl = String(account.remote_url' in account_ui
    assert 'const viewOptions = role !== "user" ? ""' in account_ui
    assert 'remote_url = f"https://{slug}.{base}"' in ACCOUNTS
    assert 'if _is_admin_role(role):' in ACCOUNTS
    assert 'views.clear()' in ACCOUNTS

def test_view_only_grants_can_browse_all_dashboards_without_persisting_selection():
    assert 'const dashboardNavigator = dashboardRows.length > 1' in JS
    start = JS.index("  async _switchDashboard(")
    switch = JS[start:JS.index("  async _manageDashboard(", start)]
    assert 'if (!this._profile || !this._hass) return;' in switch
    assert 'if (this._canControlProfile)' in switch
    assert 'this._activeDashboardId = dashboardId;' in switch
    assert 'this._selectedCards = Array.isArray(row?.cards)' in switch
    assert 'await this._manageDashboard("select", dashboardId);' in switch
    render_start = JS.index('const dashboardNavigator = dashboardRows.length > 1')
    render_tail = JS[render_start:JS.index('this._canControlProfile = canControl;', render_start)]
    assert 'canControl && dashboardRows.length > 1' not in render_tail

def test_public_profile_entry_has_session_gate_security_headers_and_exact_profile_confinement():
    assert '_SESSION_COOKIE = "__Host-fitness_session"' in ACCOUNTS
    login = ACCOUNTS[ACCOUNTS.index('class FitnessPortalLoginView'):ACCOUNTS.index('class FitnessPortalPasswordView')]
    assert 'response.set_cookie(' in login
    assert 'secure=True' in login
    assert 'httponly=True' in login
    assert 'samesite="Strict"' in login
    assert 'Content-Security-Policy' in ACCOUNTS
    assert 'Strict-Transport-Security' in ACCOUNTS
    assert 'allowed_prefixes = ("/fitness-auth/", "/fitness/frontend/", "/fitness/brand/")' in ACCOUNTS
    assert 'remote_account = controller.account_by_remote_host(request.host)' in ACCOUNTS
    assert 'raise web.HTTPNotFound(text="This hostname serves the restricted HA-Fitness portal only")' in ACCOUNTS

def test_liveactivity_is_structured_device_data_not_invalid_fit_and_old_quarantine_reprobes():
    assert "GARMIN_PAYLOAD_DECODER_REVISION = 3" in GARMIN
    assert 'normalized_type == "LIVEACTIVITY"' in GARMIN
    assert '"kind": "device_artifact"' in GARMIN
    assert '"artifact_type": "live_activity"' in GARMIN
    assert 'int(cached.get("decoder_revision") or 0) < GARMIN_PAYLOAD_DECODER_REVISION' in GARMIN
    assert 'structured families such as LiveActivity' in GFDI

    sample = {
        "uuid": "bb5425c6-9bf1-41e6-9c98-db64e328672a",
        "name": "Βάση",
        "steps": [{"id": 0, "intensity": 5, "durationType": 0, "duration": 2040.0,
                   "targets": [{"priority": 0, "targetType": 0, "targetHigh": 2.6659998893737793, "targetLow": 2.3610000610351562}]}],
        "clusters": [{"clusterId": 0, "firstStepId": 0, "lastStepId": 0, "activeStepId": 0, "state": 0}],
    }
    raw = zlib.compress(json.dumps(sample, ensure_ascii=False, separators=(",", ":")).encode())
    # Static source contract plus the actual capture shape: LiveActivity is JSON
    # after zlib inflation and therefore must not be routed to FIT validation.
    assert json.loads(zlib.decompress(raw))["steps"][0]["duration"] == 2040.0


def test_frontend_cache_bumped_for_tv_and_public_gate_changes():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert '?v=unreleased-138' in DASH
    assert '"frontend_version": "unreleased-138"' in DASH
