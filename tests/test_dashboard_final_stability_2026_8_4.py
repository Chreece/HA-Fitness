from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def test_composite_cards_do_not_rebuild_on_unrelated_hass_updates():
    assert "if (signature === this._compositeSignatureValue) return;" in JS
    assert "for (const child of this._compositeChildren || [])" in JS
    assert "Keep the existing nodes alive" in JS


def test_route_signature_ignores_provider_last_updated():
    block = JS[JS.index("  _routeSignature() {"):JS.index("  async _resolveSource()", JS.index("  _routeSignature() {"))]
    assert "state?.last_updated" not in block
    assert "JSON.stringify(value)" in block


def test_map_has_drag_pinch_wheel_and_fit_gestures():
    assert "_bindMapGestures()" in JS
    assert "map.onpointerdown" in JS
    assert "map.onpointermove" in JS
    assert "map.onpointerup" in JS
    assert "map.onwheel" in JS
    assert "map.ondblclick" in JS
    assert "data-map-pan=" not in JS
    assert "data-map-zoom=" not in JS
    assert "this._panX" in JS
    assert "this._panY" in JS


def test_only_four_consolidated_cards_are_public():
    public = JS[JS.index("const FITNESS_PUBLIC_CARDS"):JS.index("console.info(")]
    assert public.count('type: "fitness-') == 4
    assert 'type: "fitness-live-workout-card"' in public
    assert 'type: "fitness-workout-card"' in public
    assert 'type: "fitness-sleep-recovery-card"' in public
    assert 'type: "fitness-evaluation-card"' in public
    for legacy in (
        "fitness-route-card",
        "fitness-comparison-card",
        "fitness-sleep-stage-card",
        "fitness-progress-card",
        "fitness-recovery-card",
        "fitness-training-load-card",
        "fitness-today-card",
        "fitness-workout-highlights-card",
    ):
        assert f'type: "{legacy}"' not in public


def test_generated_dashboard_uses_summary_plus_live_views():
    block = JS[JS.index("  static _profileViews"):JS.index("class FitnessComparisonCardEditor")]
    assert 'custom:fitness-workout-card' in block
    assert 'custom:fitness-sleep-recovery-card' in block
    assert 'custom:fitness-evaluation-card' in block
    assert 'path: `${slug}-live`' in block


def test_frontend_revision_matches_backend_resource():
    js_version = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    resource_version = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert js_version and resource_version
    assert js_version.group(1) == resource_version.group(1)


def test_changelog_contains_final_stability_polish():
    assert "Final dashboard stability polish" in CHANGELOG
