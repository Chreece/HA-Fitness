from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
TV_DASHBOARD = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()


def test_v110_frontend_generation_and_cache_busters_are_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert 'FITNESS_TV_DASHBOARD_CARD_TAG = "fitness-tv-dashboard-card-v110"' in FRONTEND
    assert 'FITNESS_TV_SETUP_CARD_TAG = "fitness-tv-setup-card-v110"' in FRONTEND
    assert '?v=unreleased-138' in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_tv_preferences_accept_and_persist_toolbar_auto_hide():
    assert '"toolbar_auto_hide",' in TV_DASHBOARD
    assert '"toolbar_auto_hide": bool(profile.get("toolbar_auto_hide", False))' in TV_DASHBOARD
    assert 'toolbar_auto_hide: bool | None = None' in TV_DASHBOARD
    assert 'updated["toolbar_auto_hide"] = bool(toolbar_auto_hide)' in TV_DASHBOARD
    assert 'vol.Optional("toolbar_auto_hide"): bool' in TV_DASHBOARD
    assert 'toolbar_auto_hide=msg.get("toolbar_auto_hide")' in TV_DASHBOARD
    assert '"toolbar_auto_hide": result["toolbar_auto_hide"]' in TV_DASHBOARD
    assert 'toolbar_auto_hide:toolbarAutoHide' in FRONTEND


def test_browser_drag_keeps_grabbed_card_under_pointer_and_reflows_peers_live():
    assert 'const grabOffsetX = Number(event.clientX || 0) - startRect.left;' in FRONTEND
    assert 'const syncDraggedPosition = () =>' in FRONTEND
    assert 'wrapper.style.setProperty("position", "fixed", "important");' in FRONTEND
    assert 'this.shadowRoot.appendChild(wrapper);' in FRONTEND
    assert 'grid.insertBefore(placeholder, reference || null);' in FRONTEND
    assert 'placeholder.replaceWith(wrapper);' in FRONTEND
    assert 'wrapper.classList.add("dragging", "dragging-floating")' in FRONTEND
    assert '.tv-card-slot.dragging-floating' in FRONTEND


def test_cast_arrange_mode_arms_one_card_then_uses_dpad_with_edge_wrapping():
    assert 'data-card-move-edit="1"' in FRONTEND
    assert 'class="card-move-edit"' in FRONTEND
    assert '_setCastCardMoveMode(cardId = "")' in FRONTEND
    assert 'String(this._castLayoutMoveCardId || "") === cardId' in FRONTEND
    assert 'async _moveCardDirectional(cardId, direction)' in FRONTEND
    assert 'let wrapped = false;' in FRONTEND
    assert 'const insertAfter = wrapped ? ["left", "up"].includes(wanted)' in FRONTEND
    assert 'this._setCastCardMoveMode(cardId);' in FRONTEND
    assert 'this._setCastCardMoveMode("");' in FRONTEND
    assert 'const resizeHandle = FITNESS_TV_CAST_RECEIVER ? null : document.createElement("button")' in FRONTEND


def test_dashboard_browser_and_fade_form_sticky_scroll_chrome():
    assert '_syncDashboardStickyChrome()' in FRONTEND
    assert 'this.style.setProperty("--fitness-sticky-toolbar-offset"' in FRONTEND
    assert 'this.style.setProperty("--fitness-sticky-browser-height"' in FRONTEND
    assert '.dashboard-browser-row{position:sticky;top:var(--fitness-sticky-toolbar-offset,0px)' in FRONTEND
    assert '.dashboard-scroll-fade{position:sticky;top:calc(var(--fitness-sticky-toolbar-offset,0px) + var(--fitness-sticky-browser-height,0px) - 12px)' in FRONTEND
    assert ':host([toolbar-hidden]) .dashboard-scroll-fade{top:calc(var(--fitness-sticky-browser-height,0px) - 10px)' in FRONTEND
    assert ':host([fitness-cast-receiver]) .dashboard-scroll-fade{display:none!important}' in FRONTEND
