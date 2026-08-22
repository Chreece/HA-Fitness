from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_account_enabled_toggle_lives_in_account_header():
    assert 'class="account-enabled-head"' in FRONTEND
    assert 'data-account-enabled type="checkbox"' in FRONTEND
    assert '<label class="account-enabled-field">' not in FRONTEND
    assert '.account-enabled-head input{' in FRONTEND


def test_remote_only_users_do_not_get_editable_login_name():
    assert 'access-username-field ${networkAccess === "remote_only" ? "hidden" : ""}' in FRONTEND
    assert 'username:currentNetwork === "remote_only" ? null' in FRONTEND
    assert 'if network_access == NETWORK_REMOTE_ONLY:' in ACCOUNTS
    assert 'requested_username = _normalize_username(slug)' in ACCOUNTS
    assert 'name="username"' not in ACCOUNTS[ACCOUNTS.index('def _password_page'):ACCOUNTS.index('def _portal_app_page')]

def test_remote_portal_top_bar_keeps_profile_selector_and_logout_only():
    portal = ACCOUNTS[ACCOUNTS.index('def _portal_app_page'):ACCOUNTS.index('class FitnessPortalLoginView')]
    assert 'id="profile-nav"' in portal
    assert 'id="logout-btn"' in portal
    assert 'id="account-btn"' not in portal
    assert 'id="account-modal"' not in portal
    assert 'account-username' not in portal


def test_remote_admin_can_derive_first_slug_when_enabled():
    save = ACCOUNTS[ACCOUNTS.index('async def async_save_account'):ACCOUNTS.index('async def async_delete_account')]
    assert 'if remote_enabled and not slug:' in save
    assert '_normalize_slug((current or {}).get("username"))' in save
    assert '_normalize_slug(display_name)' in save
    assert 'ensureRemoteSlug' in FRONTEND


def test_account_admin_status_is_not_an_empty_sticky_bar():
    assert '.access-status{position:relative;bottom:auto;min-height:0;' in FRONTEND
    assert '.access-status:empty{display:none}' in FRONTEND
    assert '.access-status{position:sticky' not in FRONTEND


def test_toolbar_reveal_is_normal_flow_and_cannot_overlap_dashboard_switcher():
    assert '.toolbar-reveal-zone{display:none;position:relative;top:auto;' in FRONTEND
    assert ':host([fitness-public-portal][toolbar-hidden]:not([fitness-view-only])) .toolbar-reveal-zone{position:relative;top:auto;' in FRONTEND
    assert 'margin:4px auto 8px' in FRONTEND
    assert 'margin:0 auto -28px' not in FRONTEND


def test_v105_frontend_resource_and_portal_are_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-138"' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS
    assert 'fitness-tv-dashboard-card-v109' in FRONTEND
    assert 'fitness-tv-setup-card-v109' in FRONTEND
