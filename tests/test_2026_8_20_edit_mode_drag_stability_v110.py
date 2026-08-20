from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_edit_mode_disables_decorative_dashboard_and_card_motion():
    assert "&& !this._layoutEditing" in FRONTEND
    assert 'this._cancelDashboardMotion();' in FRONTEND
    assert 'this._setCardEditingMotionFrozen(card, this._layoutEditing);' in FRONTEND
    assert 'style[data-fitness-edit-freeze]' in FRONTEND
    assert 'animation:none!important;' in FRONTEND
    assert ':host([layout-editing]) *,:host([layout-editing]) *::before,:host([layout-editing]) *::after{animation:none!important;transition:none!important}' in FRONTEND
    assert ':host([layout-editing]) .fitness-ambient-layer i{animation:none!important;transition:none!important}' in FRONTEND


def test_drag_lifts_real_card_out_of_masonry_and_tracks_viewport_pointer():
    reorder = _reorder_method()
    assert 'const placeholder = wrapper.cloneNode(false);' in reorder
    assert 'placeholder.classList.add("fitness-drag-placeholder");' in reorder
    assert 'wrapper.before(placeholder);' in reorder
    assert 'this.shadowRoot.appendChild(wrapper);' in reorder
    assert 'wrapper.style.setProperty("position", "fixed", "important");' in reorder
    assert 'const painted = wrapper.getBoundingClientRect();' in reorder
    assert 'dragTranslateX += desiredLeft - painted.left;' in reorder
    assert 'dragTranslateY += desiredTop - painted.top;' in reorder
    assert 'wrapper.offsetLeft' not in reorder
    assert 'wrapper.offsetTop' not in reorder


def test_drag_does_not_reorder_from_unbounded_nearest_card_or_desaturate_surface():
    reorder = _reorder_method()
    assert 'const boundary = 34;' in reorder
    assert 'const overlapArea = overlapX * overlapY;' in reorder
    assert 'const snapDistance = Math.max(44, Math.min(110' in reorder
    assert 'if (placementKey === lastPlacementKey) return;' in reorder
    assert 'grid.insertBefore(placeholder, reference || null);' in reorder
    assert 'placeholder.replaceWith(wrapper);' in reorder
    assert ':host([card-dragging]),:host([card-dragging]) ha-card.tv-shell' in FRONTEND
    assert '.tv-card-slot.dragging-floating{filter:none!important;opacity:1!important;' in FRONTEND
    assert '.tv-card-slot.dragging-floating>.tv-mounted-card{transform:none!important;filter:none!important;opacity:1!important;' in FRONTEND


def _reorder_method() -> str:
    start = FRONTEND.index("  _wireCardReorder(wrapper, cardId) {")
    end = FRONTEND.index("\n  _profileHasLastWorkoutData", start)
    return FRONTEND[start:end]
