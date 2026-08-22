from pathlib import Path

JS = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_normal_desktop_native_grid_centers_incomplete_rows():
    assert "const stableGridUnits = 24;" in JS
    assert 'grid-template-columns:repeat(24,minmax(0,1fr))!important' in JS
    assert "const stableSpan = Math.max(1, Math.min(stableGridUnits, span12 * 2));" in JS
    assert "Math.floor((stableGridUnits - row.used) / 2)" in JS
    assert 'item.wrapper.style.setProperty("grid-column-start", String(column));' in JS
    assert 'item.wrapper.style.setProperty("grid-row-start", String(rowIndex + 1));' in JS


def test_hidden_empty_cards_do_not_shift_normal_view_centering():
    assert 'if (!wrapper.classList.contains("fitness-empty-card")) stableItems.push({wrapper, span:stableSpan});' in JS


def test_normal_view_still_uses_native_grid_not_absolute_masonry():
    block = JS[JS.index("if (stableDesktopGrid) {"):JS.index("if (mobileDocumentFlow)")]
    assert 'wrapper.style.removeProperty("position")' in block
    assert 'wrapper.style.position = "absolute"' not in block
    assert 'grid.style.height = `${Math.ceil(totalHeight)}px`' not in block
