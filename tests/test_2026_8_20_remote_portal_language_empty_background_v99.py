from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_remote_login_defaults_to_profile_language_and_remembers_explicit_choice():
    assert "def account_language(" in ACCOUNTS
    assert "config = {**entry.data, **entry.options}" in ACCOUNTS
    assert "config.get(CONF_LANGUAGE)" in ACCOUNTS
    assert '_LANGUAGE_COOKIE = "__Host-fitness_language"' in ACCOUNTS
    assert "requested_language or remembered_language or controller.account_language(remote_account)" in ACCOUNTS
    assert 'max_age=31536000' in ACCOUNTS


def test_remote_portal_chrome_uses_session_language():
    assert "_PORTAL_APP_TEXT" in ACCOUNTS
    assert "window.__FITNESS_PORTAL_TEXT__" in ACCOUNTS
    assert "portalText.administration" in ACCOUNTS
    assert "portalText.view_only" in ACCOUNTS
    assert 'id="account-btn"' not in ACCOUNTS
    assert "app_text['sign_out']" in ACCOUNTS


def test_view_only_never_gets_toolbar_reveal_handle():
    assert '${canControl ? `<button type="button" id="toolbar-reveal"' in JS
    assert ':host([fitness-view-only]) .toolbar-reveal-zone{display:none!important}' in JS
    assert 'this._canControlProfile && !this.hasAttribute("fitness-view-only")' in JS


def test_remote_reveal_handle_uses_normal_flow_below_portal_bar():
    assert 'syncPortalGeometry' in ACCOUNTS
    assert '--fitness-portal-top-height' in ACCOUNTS
    assert ':host([fitness-public-portal][toolbar-hidden]:not([fitness-view-only])) .toolbar-reveal-zone{position:relative;top:auto' in JS
    assert 'margin:4px auto 8px' in JS


def test_composite_cards_propagate_empty_child_state_and_portal_fills_viewport():
    assert 'const syncInformation = () =>' in JS
    assert 'this.toggleAttribute("fitness-empty", !hasInformation)' in JS
    assert 'this.toggleAttribute("fitness-has-information", hasInformation)' in JS
    assert ':host([fitness-public-portal]) ha-card.tv-shell{min-height:calc(100dvh - var(--fitness-portal-top-height,57px))' in JS
    assert '#app>fitness-tv-dashboard-card,#app>fitness-tv-setup-card' in ACCOUNTS


def test_frontend_cache_revision_is_v99():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in JS
    assert '?v=unreleased-110' in DASH
    assert 'frontend_version = "unreleased-110"' in ACCOUNTS
