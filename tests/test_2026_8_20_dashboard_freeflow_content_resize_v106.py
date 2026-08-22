from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()


def test_v106_resource_is_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert '?v=unreleased-138' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS
    assert 'FITNESS_TV_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card-v110"' in JS


def test_dashboard_uses_measured_masonry_not_synthetic_row_spans():
    assert 'const packUnits = 200' in JS
    assert 'const skyline = Array(packUnits).fill(0)' in JS
    assert 'centerDistance = Math.abs((startUnit + widthUnits / 2) - packUnits / 2)' in JS
    assert 'grid.style.height = `${Math.ceil(totalHeight)}px`' in JS
    assert 'wrapper.style.removeProperty("grid-row-end")' in JS


def test_non_cast_dashboard_has_one_document_scroll_owner():
    assert ':host(:not([fitness-cast-receiver])){height:auto!important' in JS
    assert 'ha-card.tv-shell{height:auto!important' in JS
    assert 'overflow:visible!important;overscroll-behavior-y:auto!important;scrollbar-gutter:auto!important' in JS


def test_manual_resize_never_clips_card_content():
    assert '.tv-card-slot[data-manual-height]{height:auto!important;min-height:var(--fitness-manual-card-height,120px)!important' in JS
    assert 'const manualVisualHeight = manualHeight > 0 ? Math.ceil' in JS
    assert 'const requestedVisualHeight = Math.max(contentVisualHeight, manualVisualHeight)' in JS
    assert 'const settleTolerance = aiSettlingCard ? 6 : 2' in JS
    assert 'A saved height is a minimum canvas size, never a clipping box.' in JS


def test_hidden_cards_reserve_layout_only_in_edit_mode():
    assert '.fitness-empty-card{display:none!important}' in JS
    assert ':host([layout-editing]) .tv-card-slot.fitness-empty-card{display:block!important' in JS
    assert 'const visible = this._layoutEditing || !wrapper.classList.contains("fitness-empty-card")' in JS


def test_toolbar_reveal_shares_dashboard_browser_row():
    assert 'class="dashboard-browser-row">${dashboardNavigator}${canControl ? `<button type="button" id="toolbar-reveal"' in JS
    assert '.dashboard-browser-row .toolbar-reveal-zone' in JS
    assert '.dashboard-browser-row .dashboard-switcher{margin:0!important' in JS


def test_version_mismatch_does_not_reload_page_or_restore_toolbar():
    block = JS[JS.index('const _fitnessEnsureFrontendVersion'):JS.index('const _fitnessSafeExternalUrl')]
    assert 'location.reload()' not in block
    assert 'keeping the current view without an automatic reload' in block
