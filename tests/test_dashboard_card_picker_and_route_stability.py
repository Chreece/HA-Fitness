from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASHBOARD = (ROOT / "custom_components/fitness/dashboard.py").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def test_fitness_cards_register_with_home_assistant_picker_metadata():
    assert "window.customCards = window.customCards || []" in JS
    public = JS[JS.index("const FITNESS_PUBLIC_CARDS"):JS.index("console.info(")]
    for card in (
        "fitness-workout-card",
        "fitness-sleep-recovery-card",
        "fitness-evaluation-card",
    ):
        assert f'type: "{card}"' in public
    for legacy in (
        "fitness-route-card",
        "fitness-comparison-card",
        "fitness-sleep-stage-card",
    ):
        assert f'type: "{legacy}"' not in public
    assert "documentationURL" in JS


def test_frontend_resource_revision_is_cache_busted():
    dashboard_match = re.search(r'\\?v=([0-9.]+)', DASHBOARD)
    js_match = re.search(r'FITNESS_DASHBOARD_VERSION = "([0-9.]+)"', JS)
    assert dashboard_match
    assert js_match
    assert dashboard_match.group(1) == js_match.group(1)


def test_route_card_does_not_resolve_and_render_on_every_hass_update():
    assert "_resolvedConfigKey" in JS
    assert "_routeSignature()" in JS
    assert "signature !== this._lastRouteSignature" in JS
    assert "width === this._lastRenderedWidth" in JS


def test_changelog_mentions_picker_and_route_stability_fixes():
    assert "Community card discovery" in CHANGELOG
    assert "map blinking/reloads" in CHANGELOG
