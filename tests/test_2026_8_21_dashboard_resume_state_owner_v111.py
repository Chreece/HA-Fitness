from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_dashboard_resume_state_methods_belong_to_tv_dashboard_card():
    route = FRONTEND.split("class FitnessRouteCard extends HTMLElement {", 1)[1].split(
        "class FitnessRouteCardEditor extends HTMLElement {", 1
    )[0]
    tv = FRONTEND.split("class FitnessTvDashboardCard extends HTMLElement {", 1)[1].split(
        "class FitnessBackendFlow extends HTMLElement {", 1
    )[0]

    assert "_captureDashboardResumeState()" not in route
    assert "_restoreDashboardResumeState()" not in route
    assert "_captureDashboardResumeState()" in tv
    assert "_restoreDashboardResumeState()" in tv
    assert "this._captureDashboardResumeState();" in tv
    assert "this._restoreDashboardResumeState();" in tv
