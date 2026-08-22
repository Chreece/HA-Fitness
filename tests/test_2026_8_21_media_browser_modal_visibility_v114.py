from pathlib import Path

JS = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")

def test_media_browser_shared_scroll_region_cannot_collapse_to_title_only():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert '.fitness-modal-scroll-region{box-sizing:border-box!important;display:block!important;flex:1 1 auto!important;' in JS
    assert '.browser-modal{height:min(760px,calc(100dvh - var(--modal-top,68px) - 18px))!important;' in JS
    assert '.browser-modal>.fitness-modal-scroll-region{flex:1 1 auto!important;min-height:0!important;' in JS

def test_media_browser_submenus_use_the_audited_browser_modal():
    for marker in [
        'class="modal-card browser-modal"',
        'class="modal-card browser-modal playlist-modal"',
        'class="media-list"',
        'class="music-source-list"',
        'class="playlist-list"',
        'class="playlist-edit-list"',
    ]:
        assert marker in JS
