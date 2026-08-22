from pathlib import Path

JS = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_ai_resize_observer_cannot_be_starved_by_continuous_updates():
    assert 'if (wrapper.__fitnessAiResizeTimer) continue;' in JS
    assert 'clearTimeout(wrapper.__fitnessAiResizeTimer)' not in JS
    assert '}, 120);' in JS


def test_desktop_masonry_uses_live_rendered_card_height_not_only_cached_height():
    assert 'const renderedCardHeight = card ? Math.max(' in JS
    assert 'Number(card.getBoundingClientRect?.().height || 0)' in JS
    assert 'Number(card.scrollHeight || 0)' in JS
    assert 'const visualHeight = Math.max(cachedVisualHeight' in JS


def test_v125_cache_contract():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in JS
