from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def test_map_uses_pointer_drag_and_pinch():
    assert "_bindMapGestures()" in JS
    assert "map.onpointerdown" in JS
    assert "map.onpointermove" in JS
    assert "map.onpointerup" in JS
    assert "distance(a, b)" in JS
    assert "Math.log2" in JS


def test_map_supports_desktop_wheel_and_double_fit():
    assert "map.onwheel" in JS
    assert "map.ondblclick" in JS
    assert "this._zoomDelta = 0" in JS
    assert "this._panX = 0" in JS
    assert "this._panY = 0" in JS


def test_map_has_no_navigation_buttons():
    assert 'data-map-pan=' not in JS
    assert 'data-map-zoom=' not in JS
    assert "map-controls" not in JS
    assert "pan-pad" not in JS
    assert "zoom-pad" not in JS


def test_gesture_motion_does_not_rebuild_tiles_every_pointer_move():
    block = JS[JS.index("  _bindMapGestures() {"):JS.index("  _render() {", JS.index("  _bindMapGestures() {"))]
    pointer_move = block[block.index("map.onpointermove"):block.index("const finishPointer")]
    assert "this._render()" not in pointer_move
    assert "scene.style.transform" in pointer_move


def test_touch_action_disables_browser_gesture_conflict_inside_map():
    assert "touch-action:none" in JS
    assert "overscroll-behavior:contain" in JS


def test_frontend_resource_revision_matches():
    frontend = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    backend = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert frontend and backend
    assert frontend.group(1) == backend.group(1)


def test_changelog_documents_touch_map():
    assert "native-style workout map interaction" in CHANGELOG
