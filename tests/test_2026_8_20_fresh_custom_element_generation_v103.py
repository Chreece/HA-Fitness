from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")


def test_managed_lovelace_uses_fresh_release_specific_elements():
    assert 'FITNESS_TV_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card-v110"' in FRONTEND
    assert 'FITNESS_TV_SETUP_CARD_TAG = "fitness-tv-setup-card-v110"' in FRONTEND
    assert '_TV_DASHBOARD_CARD_TYPE = "custom:fitness-tv-dashboard-card"' in DASHBOARD
    assert '_TV_SETUP_CARD_TYPE = "custom:fitness-tv-setup-card"' in DASHBOARD


def test_previous_aliases_remain_registered_and_managed():
    assert '"fitness-tv-dashboard-card-v76"' in FRONTEND
    assert '"fitness-tv-setup-card-v76"' in FRONTEND
    assert 're.fullmatch(r"custom:fitness-tv-dashboard-card-v\\d+", card_type)' in DASHBOARD
    assert 're.fullmatch(r"custom:fitness-tv-setup-card-v\\d+", card_type)' in DASHBOARD
