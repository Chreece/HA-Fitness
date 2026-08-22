from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()


def test_managed_lovelace_uses_stable_wrapper_not_release_specific_type():
    assert '_TV_DASHBOARD_CARD_TYPE = "custom:fitness-tv-dashboard-card"' in DASH
    assert '_TV_SETUP_CARD_TYPE = "custom:fitness-tv-setup-card"' in DASH
    assert 'FITNESS_TV_LOVELACE_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card"' in JS
    assert 'FITNESS_TV_LOVELACE_SETUP_CARD_TAG = "fitness-tv-setup-card"' in JS


def test_fresh_internal_elements_still_force_new_implementation_after_reload():
    assert 'FITNESS_TV_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card-v110"' in JS
    assert 'FITNESS_TV_SETUP_CARD_TAG = "fitness-tv-setup-card-v110"' in JS
    assert '"fitness-tv-dashboard-card-v103"' in JS
    assert '"fitness-tv-setup-card-v103"' in JS
    assert '"fitness-tv-dashboard-card-v104"' in JS
    assert '"fitness-tv-setup-card-v104"' in JS


def test_frontend_version_is_fresh_in_ha_resource_and_remote_portal():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-138"' in DASH
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS
    assert 'src="/fitness/frontend/fitness-dashboard.js?v={frontend_cache_version}"' in ACCOUNTS


def test_desktop_ha_claims_one_ancestor_scroll_owner_without_nested_shell_scroll():
    assert "_claimDashboardScrollOwner()" in JS
    assert "this._dashboardScrollOwner = owner" in JS
    assert 'element.style.overflowY = "hidden"' not in JS
    assert 'scrollbarWidth = "none"' in JS
    assert ':host(:not([fitness-cast-receiver])) ha-card.tv-shell{height:auto!important' in JS
    assert 'overflow:visible!important' in JS


def test_remote_webpage_keeps_document_scroll_and_skips_ha_scroll_claim():
    assert 'this.hasAttribute("fitness-public-portal")' in JS
    assert '_releaseDashboardScrollOwner();' in JS
    assert ':host(:not([fitness-cast-receiver])) ha-card.tv-shell{height:auto!important' in JS
    assert 'overflow:visible!important' in JS

def test_mobile_document_flow_contract_remains_in_force():
    assert '@media(max-width:760px)' in JS
    assert 'flex-direction:column!important;' in JS
    assert 'overflow-y:visible!important;' in JS
