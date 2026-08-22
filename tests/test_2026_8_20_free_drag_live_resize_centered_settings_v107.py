from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()


def test_frontend_cache_revision_v107_is_synchronized():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in FRONTEND
    assert "?v=unreleased-138" in DASHBOARD
    assert 'frontend_version = "unreleased-138"' in ACCOUNTS


def test_editor_has_move_resize_and_best_size_reset_controls():
    assert 'class="card-move-handle"' in FRONTEND
    assert 'className = "card-resize-handle"' in FRONTEND
    assert 'data-move="-1"' not in FRONTEND
    assert 'data-move="1"' not in FRONTEND
    assert 'class="card-reset-size"' in FRONTEND
    assert '_resetCardSize(item.id)' in FRONTEND


def test_drag_reorders_live_and_reflows_other_cards():
    assert 'handle.addEventListener("pointerdown"' in FRONTEND
    assert 'grid.insertBefore(placeholder, reference || null);' in FRONTEND
    assert 'this._applyDashboardCardLayout();' in FRONTEND
    assert 'this._scheduleLiveCardContentResize();' in FRONTEND
    assert 'await this._savePreferences(cards);' in FRONTEND


def test_resize_updates_all_mounted_card_contents_live():
    assert '_scheduleLiveCardContentResize()' in FRONTEND
    assert 'for (const mounted of this._mountedCards || [])' in FRONTEND
    assert 'globalThis.dispatchEvent?.(new Event("resize"))' in FRONTEND
    assert 'this._scheduleDashboardCardLayout();' in FRONTEND


def test_hidden_cards_only_reserve_space_in_edit_mode():
    assert 'const visible = this._layoutEditing || !wrapper.classList.contains("fitness-empty-card");' in FRONTEND
    assert ':host(:not([layout-editing])) .tv-card-slot.fitness-empty-card{display:none!important' in FRONTEND
    assert ':host([layout-editing]) .tv-card-slot.fitness-empty-card{display:block!important' in FRONTEND


def test_masonry_cluster_is_centered_after_packing():
    assert 'const usedLeft = Math.min(...placed.map((item) => item.left));' in FRONTEND
    assert 'const usedRight = Math.max(...placed.map((item) => item.left + item.width));' in FRONTEND
    assert 'const shift = ((gridWidth - usedWidth) / 2) - usedLeft;' in FRONTEND
    assert 'item.wrapper.style.left = `${centeredLeft}px`;' in FRONTEND


def test_overview_remove_dashboard_button_matches_sibling_tools():
    assert '<button class="tool remove-profile"' in FRONTEND
    assert '<button class="icon-tool remove-profile"' not in FRONTEND
    assert '<span>${_fitnessEscape(l.disable_tv_view)}</span>' in FRONTEND


def test_per_user_backend_settings_are_centered_like_tv_settings():
    assert '.backend-flow-backdrop{background:' in FRONTEND
    assert 'justify-content:center!important;align-items:center!important;' in FRONTEND
    assert '_openBackendFlow(mode, entryId = "", profileName = "")' in FRONTEND
