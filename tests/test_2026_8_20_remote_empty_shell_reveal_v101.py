from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_empty_dashboard_waits_for_information_before_showing_cards():
    assert 'wrapper.classList.add("fitness-empty-card")' in FRONTEND
    assert 'const hasVisibleCard = wrappers.some((wrapper) => !wrapper.classList.contains("fitness-empty-card"));' in FRONTEND
    assert 'this.toggleAttribute("fitness-dashboard-empty", empty);' in FRONTEND
    assert ':host([fitness-dashboard-empty]:not([layout-editing])) .dashboard-empty-state{display:grid}' in FRONTEND
    assert ':host([fitness-dashboard-empty]:not([layout-editing])) .tv-grid' in FRONTEND
    assert 'class="dashboard-empty-state"' in FRONTEND
    assert '${_fitnessEscape(l.no_current_data)}' in FRONTEND


def test_reveal_handle_is_outside_perspective_stage_and_occupies_layout_space():
    assert 'class="dashboard-browser-row">${dashboardNavigator}${canControl ? `<button type="button" id="toolbar-reveal"' in FRONTEND
    assert 'width:52px;height:30px' in FRONTEND
    assert '.toolbar-reveal-zone{display:none;position:relative;top:auto;' in FRONTEND
    assert '.dashboard-browser-row .toolbar-reveal-zone' in FRONTEND
    assert '.dashboard-browser-row .dashboard-switcher{margin:0!important' in FRONTEND
    assert 'transform:none' in FRONTEND
    assert ':host([fitness-view-only]) .toolbar-reveal-zone{display:none!important}' in FRONTEND


def test_restricted_portal_has_real_chevron_glyph_not_fallback_diamond():
    assert '"mdi:chevron-down":"⌄"' in ACCOUNTS
    assert '"mdi:chevron-up":"⌃"' in ACCOUNTS


def test_frontend_cache_revision_is_consistent():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS
    assert '?v=unreleased-138' in DASHBOARD
