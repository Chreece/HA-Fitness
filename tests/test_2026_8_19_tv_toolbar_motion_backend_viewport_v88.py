from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components" / "fitness" / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components" / "fitness" / "dashboard.py").read_text(encoding="utf-8")


def test_toolbar_auto_hide_waits_while_user_is_browsing_toolbar():
    assert "_toolbarIsBeingBrowsed(toolbar" in JS
    assert 'toolbar.matches?.(":hover")' in JS
    assert 'toolbar.classList?.contains("fitness-remote-section-selected")' in JS
    assert 'toolbar?.addEventListener("pointerenter", holdOpen' in JS
    assert 'toolbar?.addEventListener("pointerleave", () => this._scheduleToolbarAutoHide()' in JS


def test_toolbar_hides_with_transition_instead_of_display_none():
    assert ':host([toolbar-hidden]) .tv-toolbar{display:none!important}' not in JS
    assert ':host([toolbar-hidden]) .tv-toolbar{opacity:0;transform:translate3d(0,-18px,0) scaleY(.94);max-height:0' in JS
    assert 'transition:opacity .24s ease,transform .38s cubic-bezier(.22,.72,.18,1),max-height .38s' in JS


def test_dashboard_entry_motion_is_gentle_top_edge_unroll():
    assert 'clipPath:"inset(0 0 96% 0 round 16px)"' in JS
    assert 'const unroll = wrapper.animate([' in JS
    assert 'translate3d(0,18px,0) scale(.68)' not in JS
    assert 'filter:"blur(3px) brightness(.88)"' not in JS


def test_profile_backend_submenus_remain_inside_centered_viewport_panel():
    assert 'position:fixed!important;top:var(--modal-effective-top)!important;right:0!important;bottom:0!important;left:0!important' in JS
    assert 'display:flex!important;justify-content:center!important;align-items:center!important' in JS
    assert 'position:relative!important;inset:auto!important;flex:0 1 auto!important' in JS
    assert '@media(max-width:760px){' in JS
    assert '.backend-flow-backdrop{justify-content:center!important;align-items:stretch!important' in JS


def test_frontend_revision_88_is_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in JS
    assert '?v=unreleased-110' in DASH
