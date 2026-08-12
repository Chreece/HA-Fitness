from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()

def test_modern_visual_cards_are_registered_and_editable():
    # Internal visual components stay registered because the three public
    # summary cards compose them, but they are no longer picker-visible.
    for tag in (
        "fitness-progress-card",
        "fitness-recovery-card",
        "fitness-training-load-card",
    ):
        assert f'customElements.define("{tag}"' in JS
    assert "fitness-profile-card-editor" in JS

    public = JS[JS.index("const FITNESS_PUBLIC_CARDS"):JS.index("console.info(")]
    assert 'type: "fitness-workout-card"' in public
    assert 'type: "fitness-sleep-recovery-card"' in public
    assert 'type: "fitness-evaluation-card"' in public

def test_route_map_uses_tighter_fit():
    assert "const pad = 12;" in JS
    assert "for (let zoom = 18; zoom >= 2; zoom--)" in JS

def test_resource_reconciliation_is_single_module():
    assert "matches[1:]" in DASH
    assert 'update["res_type"] = "module"' in DASH
    assert "async_delete_item" in DASH
    dash_version = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    js_version = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    assert dash_version and js_version
    assert dash_version.group(1) == js_version.group(1)

def test_changelog_documents_modern_cards():
    assert "Modern fitness visual cards" in CHANGELOG
