from pathlib import Path

JS = Path('custom_components/fitness/frontend/fitness-dashboard.js').read_text()


def test_normal_desktop_uses_native_grid_not_absolute_masonry():
    assert 'const stableDesktopGrid = !FITNESS_TV_CAST_RECEIVER && !this._layoutEditing && !mobileDocumentFlow;' in JS
    assert ':host(:not([fitness-cast-receiver]):not([layout-editing])) .tv-grid{display:grid!important' in JS
    assert ':host(:not([fitness-cast-receiver]):not([layout-editing])) .tv-card-slot{position:relative!important' in JS


def test_native_grid_does_not_feed_natural_card_height_back():
    assert 'Native CSS Grid owns normal desktop geometry.' in JS
    assert 'wrapper.style.removeProperty("--tv-card-visual-height")' in JS


def test_v126_cache_contract():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
