from pathlib import Path

JS = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_intrinsic_inner_scroll_height_is_read_before_old_minimum_is_restored():
    start = JS.index("  _syncCardGridSpan(card, wrapper) {")
    end = JS.index("  async _moveCardDirectional", start)
    block = JS[start:end]

    measure = block.index("const intrinsicInnerScrollHeight = Math.max(0, Number(innerCard?.scrollHeight || 0));")
    restore = block.index('if (previousNaturalMin) card.style.setProperty("--fitness-natural-card-min-height", previousNaturalMin);')
    assert measure < restore
    assert "const innerScrollHeight = Math.max(0, Number(innerCard?.scrollHeight || 0));" not in block


def test_natural_height_uses_intrinsic_measurement_not_restored_assigned_height():
    start = JS.index("  _syncCardGridSpan(card, wrapper) {")
    end = JS.index("  async _moveCardDirectional", start)
    block = JS[start:end]
    assert "intrinsicInnerScrollHeight," in block
    assert "Math.max(intrinsicInnerScrollHeight, Math.ceil(visualHeight / Math.max(scale, 0.01)))" in block
    assert "positive ResizeObserver feedback loop" in block
