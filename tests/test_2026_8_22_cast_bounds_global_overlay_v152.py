from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def test_cast_respects_saved_widths_and_normal_dashboard_gap():
    assert 'const gap = Math.max(6, Number.parseFloat(getComputedStyle(this).getPropertyValue("--fitness-theme-gap")) || 12);' in JS
    assert 'const responsivePercent = FITNESS_TV_CAST_RECEIVER && savedPercent > 0' in JS
    assert '? requestedPercent' in JS
    assert ': Math.max(naturalPercent, requestedPercent);' in JS


def test_cast_card_pixels_are_clipped_to_the_measured_slot():
    assert ':host([fitness-cast-receiver]) .tv-card-slot:not(.fitness-empty-card){' in JS
    block = JS[JS.index(':host([fitness-cast-receiver]) .tv-card-slot:not(.fitness-empty-card){'):][:700]
    assert 'overflow:hidden!important' in block
    assert 'contain:layout paint!important' in block
    assert 'isolation:isolate!important' in block
    assert 'z-index:1!important' in block
    assert ':host([fitness-cast-receiver]) .cast-dashboard-browser-root{position:fixed!important' in JS


def test_cast_remote_section_focus_cannot_scale_or_use_3d_perspective():
    assert ':host([fitness-cast-receiver]) .fitness-remote-section-selected{transform:none!important' in JS
    assert ':host([fitness-cast-receiver]) .fitness-remote-section-active{transform:none!important' in JS
    assert ':host([fitness-cast-receiver][remote-section-engaged]) .tv-card-slot:not(.fitness-remote-section-selected):not(.fitness-remote-section-active)' in JS
    assert 'transform:none!important' in JS
    assert ':host([fitness-cast-receiver]) .tv-oled-stage{perspective:none!important;transform-style:flat!important}' in JS


def test_cast_exit_confirmation_is_a_direct_top_level_overlay_after_ha_card():
    profile_render = JS[JS.index('this.shadowRoot.innerHTML = `', JS.index('const dashboardTitle = FITNESS_TV_CAST_RECEIVER')):JS.index('this._updateWeightMeasurementPrompt()', JS.index('const dashboardTitle = FITNESS_TV_CAST_RECEIVER'))]
    assert '</ha-card>\n      <div id="cast-global-overlay-root" class="cast-global-overlay-root"' in profile_render
    overview_start = JS.index('this.shadowRoot.innerHTML = `<ha-card class="setup-shell">', JS.index('const overviewTitle = FITNESS_TV_CAST_RECEIVER'))
    overview_render = JS[overview_start:JS.index('const openAdminProfileRow', overview_start)]
    assert '</ha-card><div id="cast-global-overlay-root" class="cast-global-overlay-root"' in overview_render
    assert 'z-index:2147483647!important' in JS
    assert 'position:fixed!important;inset:0!important' in JS
    assert 'bottom:max(28px,env(safe-area-inset-bottom))' in JS


def test_v152_cache_contract_applies_to_dashcast_and_browser_tv():
    assert '_RESOURCE_URL += "&build=cast-ui-155"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS
