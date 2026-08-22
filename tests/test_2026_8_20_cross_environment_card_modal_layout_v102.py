from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_manual_card_width_cannot_squeeze_below_current_logical_column_outside_cast():
    assert 'const responsivePercent = FITNESS_TV_CAST_RECEIVER && savedPercent > 0' in FRONTEND
    assert ': Math.max(naturalPercent, requestedPercent);' in FRONTEND
    assert 'const widthUnits = Math.max(1, Math.min(packUnits' in FRONTEND
    assert 'wrapper.style.width = `${Math.min(gridWidth, width)}px`;' in FRONTEND
    assert 'data-responsive-width-expanded' in FRONTEND


def test_resize_cannot_create_subcolumn_card_on_current_breakpoint():
    assert 'const minimumPercent = 100 / Math.max(1, this._logicalGridColumns(grid));' in FRONTEND
    assert 'Math.max(minimumPercent, Math.min(100, requestedWidth / Math.max(1, gridRect.width) * 100))' in FRONTEND
    assert 'width_percent:widthPercent' in FRONTEND


def test_natural_cards_expand_instead_of_clipping_across_environments():
    assert '.tv-card-slot:not([data-manual-height]){height:auto!important;max-height:none!important;overflow:visible!important}' in FRONTEND
    assert ':host([fitness-natural-height]){display:block!important;width:100%!important' in FRONTEND


def test_mobile_option_panels_take_focus_without_full_tv_toolbar():
    assert 'const toolbarWasHidden = Boolean(this._toolbarHidden || this.hasAttribute("toolbar-hidden"));' in FRONTEND
    assert 'this.setAttribute("modal-focus-open", "");' in FRONTEND
    assert ':host([modal-focus-open]) .tv-toolbar' in FRONTEND
    assert ':host([modal-focus-open]) .dashboard-switcher' in FRONTEND
    assert 'toolbarRect?.top' in FRONTEND


def test_modal_focus_is_released_for_programmatic_and_button_closes():
    assert 'root.__fitnessModalFocusObserver = new MutationObserver' in FRONTEND
    assert 'this.removeAttribute("modal-focus-open");' in FRONTEND


def test_frontend_cache_revision_v102():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
