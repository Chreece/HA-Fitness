from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def test_fitness_cards_register_with_home_assistant_picker_metadata():
    assert "window.customCards = window.customCards || []" in JS
    for card in ("fitness-route-card", "fitness-comparison-card", "fitness-sleep-stage-card"):
        assert f'type: "{card}"' in JS
    assert "preview: false" in JS
    assert "documentationURL" in JS


def test_frontend_resource_revision_is_cache_busted():
    assert '?v=2026.8.4.3' in DASHBOARD
    assert 'FITNESS_DASHBOARD_VERSION = "2026.8.4.3"' in JS


def test_route_card_does_not_resolve_and_render_on_every_hass_update():
    assert "_resolvedConfigKey" in JS
    assert "_routeSignature()" in JS
    assert "signature !== this._lastRouteSignature" in JS
    assert "width === this._lastRenderedWidth" in JS


def test_changelog_mentions_picker_and_route_stability_fixes():
    assert "Community card discovery" in CHANGELOG
    assert "map blinking/reloads" in CHANGELOG
