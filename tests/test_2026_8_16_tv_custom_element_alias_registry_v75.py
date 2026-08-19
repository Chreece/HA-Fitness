from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_tv_custom_element_aliases_use_unique_subclass_constructors():
    assert "const _fitnessDefineCustomElement = (tag, BaseClass) =>" in FRONTEND
    assert "customElements.define(tag, class extends BaseClass {});" in FRONTEND
    assert "customElements.define(tag, FitnessTvDashboardCard)" not in FRONTEND
    assert "customElements.define(tag, FitnessTvSetupCard)" not in FRONTEND


def test_stable_lovelace_tags_and_current_alias_are_registered():
    assert 'FITNESS_TV_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card-v76"' in FRONTEND
    assert 'FITNESS_TV_SETUP_CARD_TAG = "fitness-tv-setup-card-v76"' in FRONTEND
    assert '"fitness-tv-dashboard-card",' in FRONTEND
    assert '"fitness-tv-setup-card",' in FRONTEND
    assert '"fitness-tv-dashboard-card-v75"' in FRONTEND
    assert '"fitness-tv-setup-card-v75"' in FRONTEND
    assert '_TV_DASHBOARD_CARD_TYPE = "custom:fitness-tv-dashboard-card"' in DASHBOARD
    assert '_TV_SETUP_CARD_TYPE = "custom:fitness-tv-setup-card"' in DASHBOARD


def test_frontend_resource_revision_is_v76():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-89"' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-89"' in DASHBOARD
