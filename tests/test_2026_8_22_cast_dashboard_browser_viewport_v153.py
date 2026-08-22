from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def test_cast_dashboard_browser_is_outside_scrollable_card_shell():
    start = JS.index('this.shadowRoot.innerHTML = `', JS.index('const dashboardTitle = FITNESS_TV_CAST_RECEIVER'))
    end = JS.index('this._updateWeightMeasurementPrompt()', start)
    render = JS[start:end]
    browser = render.index('id="cast-dashboard-browser-root"')
    shell = render.index('<ha-card class="tv-shell')
    assert browser < shell
    assert '${FITNESS_TV_CAST_RECEIVER ? "" : dashboardBrowser}' in render


def test_cast_dashboard_browser_is_fixed_viewport_chrome_above_cards():
    start = JS.index(':host([fitness-cast-receiver]) .cast-dashboard-browser-root{')
    block = JS[start:start + 1500]
    assert 'position:fixed!important' in block
    assert 'top:max(8px,env(safe-area-inset-top))!important' in block
    assert 'width:100vw!important' in block
    assert 'z-index:8000!important' in block
    assert 'pointer-events:none!important' in block
    assert 'isolation:isolate!important' in block
    assert 'transform:none!important' in block
    assert '.dashboard-switcher' in block
    assert 'pointer-events:auto!important' in block


def test_cast_browser_has_reserved_safe_area_in_scrollable_shell():
    assert ':host([fitness-cast-receiver][dashboard-browser-visible]) ha-card.tv-shell{padding-top:var(--fitness-cast-browser-reserve,44px)!important}' in JS
    assert 'const castBrowserReserve = FITNESS_TV_CAST_RECEIVER && browserVisible ? Math.max(0, browserHeight + 12) : 0;' in JS
    assert 'this.style.setProperty("--fitness-cast-browser-reserve", `${castBrowserReserve}px`);' in JS


def test_cast_remote_navigation_never_scrolls_fixed_browser_chrome():
    start = JS.index('  _scrollCastElementIntoView(element) {')
    block = JS[start:start + 1500]
    assert 'element.closest?.(".cast-dashboard-browser-root")' in block
    assert 'ha-card.tv-shell' in block
    assert 'shell.scrollTop = Math.max(0, Number(shell.scrollTop || 0) + delta);' in block
    assert 'this._scrollCastElementIntoView(section);' in JS
    assert 'this._scrollCastElementIntoView(element);' in JS


def test_cast_remote_focus_cannot_move_or_dim_dashboard_browser():
    assert ':host([fitness-cast-receiver][remote-section-engaged]) .cast-dashboard-browser-root .dashboard-switcher:not(.fitness-remote-section-selected):not(.fitness-remote-section-active)' in JS
    browser_rule = JS[JS.index(':host([fitness-cast-receiver]) .cast-dashboard-browser-root .dashboard-switcher,:host([fitness-cast-receiver][remote-section-engaged])'):][:1000]
    assert 'transform:none!important' in browser_rule
    assert 'filter:none!important' in browser_rule
    assert 'opacity:1!important' in browser_rule


def test_modal_suppresses_browser_but_global_exit_overlay_stays_higher():
    assert ':host([fitness-cast-receiver][cast-modal-open]) .cast-dashboard-browser-root{visibility:hidden!important;pointer-events:none!important}' in JS
    assert 'z-index:2147483647!important' in JS


def test_v153_cache_contract_for_dashcast_and_browser_tv():
    assert '_RESOURCE_URL += "&build=cast-ui-155"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS
