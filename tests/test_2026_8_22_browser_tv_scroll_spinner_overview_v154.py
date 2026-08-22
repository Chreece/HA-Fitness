from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text(encoding="utf-8")


def test_cast_receiver_has_one_explicit_vertical_scroll_owner():
    assert ':host([fitness-cast-receiver]){position:fixed;inset:0;left:0;z-index:1;width:100vw;height:100dvh;max-width:none;margin:0;overflow:hidden!important' in JS
    shell = JS[JS.index(':host([fitness-cast-receiver]) ha-card.tv-shell{height:100dvh'):][:500]
    assert 'height:100dvh' in shell
    assert 'overflow-y:auto!important' in shell
    assert 'touch-action:pan-y!important' in shell
    assert '-webkit-overflow-scrolling:touch' in shell


def test_cast_remote_navigation_scrolls_the_shell_explicitly():
    start = JS.index('  _scrollCastElementIntoView(element) {')
    block = JS[start:start + 1500]
    assert 'ha-card.tv-shell' in block
    assert '--fitness-cast-browser-reserve' in block
    assert 'shell.scrollTop = Math.max(0, Number(shell.scrollTop || 0) + delta);' in block
    assert 'this._scrollCastElementIntoView(section);' in JS
    assert 'this._scrollCastElementIntoView(element);' in JS


def test_desktop_connecting_cast_uses_a_real_looping_loading_ring():
    assert 'castPending ? "mdi:loading" : "mdi:cast"' in JS
    assert '@keyframes fitness-cast-pending-spin{to{transform:rotate(1turn)}}' in JS
    assert ':host(:not([fitness-cast-receiver])) .cast-pending ha-icon[icon="mdi:loading"]{animation:fitness-cast-pending-spin .82s linear infinite!important' in JS


def test_overview_cast_pending_icon_is_loading_too():
    assert 'overviewCastPending ? "mdi:loading" : "mdi:cast-connected"' in JS
    assert 'connected ? "mdi:cast-off" : (pending ? "mdi:loading" : "mdi:cast-connected")' in JS


def test_overview_cast_buttons_cannot_collapse_into_vertical_bars():
    assert ':host([fitness-cast-receiver]) .profile-actions{grid-column:1/-1!important;display:grid!important;grid-template-columns:repeat(auto-fit,minmax(132px,1fr))!important' in JS
    assert ':host([fitness-cast-receiver]) .setup-actions>.tool,:host([fitness-cast-receiver]) .profile-actions>.tool{box-sizing:border-box!important;flex:none!important;width:100%!important;height:44px!important;min-height:44px!important;max-height:44px!important' in JS
    assert 'white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;overflow-wrap:normal!important;word-break:normal!important' in JS


def test_v154_cache_contract_for_both_receivers():
    assert '_RESOURCE_URL += "&build=cast-ui-155"' in DASH
    assert 'frontend_cache_version = f"{frontend_version}-cast-ui-155"' in ACCOUNTS
