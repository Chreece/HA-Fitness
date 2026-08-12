from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT/"custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT/"custom_components/fitness/dashboard.py").read_text()

def test_custom_element_editor_constructors_are_unique():
    registrations = re.findall(r'customElements\.define\("([^"]+)",\s*([A-Za-z0-9_]+)\)', JS)
    constructors = [ctor for name, ctor in registrations]
    assert len(constructors) == len(set(constructors))

def test_route_has_native_gestures_and_summary():
    assert "_bindMapGestures()" in JS
    assert "map.onpointerdown" in JS
    assert "map.onwheel" in JS
    assert "_workoutSummary()" in JS

def test_frontend_cache_revision_matches():
    a = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    b = re.search(r'_RESOURCE_URL = f".*?\?v=([^"]+)"', DASH)
    assert a and b and a.group(1) == b.group(1)
