from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
TV_DASHBOARD = (ROOT / "custom_components/fitness/tv_dashboard.py").read_text()


def _layout_method() -> str:
    start = FRONTEND.index("  _applyDashboardCardLayout() {")
    end = FRONTEND.index("\n  _scheduleDashboardCardLayout()", start)
    return FRONTEND[start:end]


def _reorder_method() -> str:
    start = FRONTEND.index("  _wireCardReorder(wrapper, cardId) {")
    end = FRONTEND.index("\n  _profileHasLastWorkoutData", start)
    return FRONTEND[start:end]


def test_browser_drag_persists_horizontal_drop_lane():
    reorder = _reorder_method()
    layout = _layout_method()
    assert "placeholder.dataset.dragXPercent = laneKey;" in reorder
    assert "x_percent:Math.round(Math.max(0, Math.min(100, droppedXPercent)) * 10) / 10" in reorder
    assert "const hasTransientX = !FITNESS_TV_CAST_RECEIVER" in layout
    assert "const hasSavedX = !FITNESS_TV_CAST_RECEIVER" in layout
    assert "bestStart = Math.max(0, Math.min(packUnits - widthUnits" in layout
    assert "if (placed.length && !hasPositionedLane)" in layout


def test_drag_target_uses_moving_card_geometry_not_mouse_handle():
    reorder = _reorder_method()
    assert "const targetAt = (dragRect) =>" in reorder
    assert "const overlapArea = overlapX * overlapY;" in reorder
    assert "const edgeDistance = Math.hypot(gapX, gapY);" in reorder
    assert "const dragCx = dragRect.left + dragRect.width / 2;" in reorder
    assert "const dragCy = dragRect.top + dragRect.height / 2;" in reorder
    assert "const normalizedY = dy / Math.max(1, (dragRect.height + rect.height) / 2);" in reorder
    assert "targetAt(pointerX, pointerY)" not in reorder


def test_backend_accepts_zero_and_bounded_horizontal_lane():
    assert 'if "x_percent" in raw:' in TV_DASHBOARD
    assert 'item["x_percent"] = round(max(0.0, min(100.0, x_percent)), 1)' in TV_DASHBOARD


def test_reset_size_preserves_position_lane():
    assert "if (previous.x_percent !== undefined && previous.x_percent !== null" in FRONTEND
    assert "layout[cardId] = {x_percent:Number(previous.x_percent)};" in FRONTEND
