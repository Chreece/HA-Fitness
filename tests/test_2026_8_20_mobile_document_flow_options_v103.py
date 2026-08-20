from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()

def test_phone_dashboard_is_strict_single_column_document_flow():
    assert "@media(max-width:760px)" in FRONTEND
    assert "display:flex!important;" in FRONTEND
    assert "flex-direction:column!important;" in FRONTEND
    assert "grid-template-columns:none!important;" in FRONTEND
    assert ".tv-card-slot[data-manual-height]" in FRONTEND
    assert "overflow:visible!important;" in FRONTEND

def test_phone_cards_do_not_keep_desktop_internal_vertical_scrollers():
    assert ".tv-card-slot .rows" in FRONTEND
    assert "overflow-y:visible!important;" in FRONTEND
    assert "overscroll-behavior-y:auto!important" in FRONTEND
    assert ".card-resize-handle{display:none!important}" in FRONTEND

def test_phone_reveal_button_occupies_layout_space():
    assert "[fitness-public-portal][toolbar-hidden]" in FRONTEND
    assert "position:relative!important;" in FRONTEND
    assert "top:auto!important;" in FRONTEND
    assert "margin:4px auto 8px!important;" in FRONTEND
    assert ".dashboard-switcher{" in FRONTEND

def test_mobile_option_surfaces_are_scrollable():
    for selector in (
        ".modal-scroll-body", ".profile-settings", ".picker-list", ".media-list",
        ".cast-picker", ".remote-gateway-body", ".provider-catalog-list",
        ".music-search-form", ".playlist-list", ".playlist-edit-list",
        ".music-source-list", ".access-admin-body", ".add-profile-list",
        ".modal-auto-scroll-body",
    ):
        assert selector in FRONTEND
    assert "overflow-y:auto!important;" in FRONTEND
    assert "-webkit-overflow-scrolling:touch;" in FRONTEND
    assert "touch-action:pan-y!important;" in FRONTEND

def test_desktop_saved_layout_is_preserved():
    assert "layout[cardId]" in FRONTEND
    assert "column_span" in FRONTEND
    assert "--fitness-manual-card-height" in FRONTEND

def test_frontend_cache_revision_v104_is_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-110"' in FRONTEND
    assert "?v=unreleased-110" in DASHBOARD
    assert 'frontend_version = "unreleased-110"' in ACCOUNTS
