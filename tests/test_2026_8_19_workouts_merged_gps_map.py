from pathlib import Path
ROOT = Path(__file__).parents[1]
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()

def test_dashboard_promotes_namespaced_merged_provider_gps_track():
    assert 'suffix = str(key).rsplit(".", 1)[-1]' in DASH
    assert 'suffix in {"gps_track", "gps_points"}' in DASH
    assert 'extra["gps_track"] = track' in DASH

def test_workouts_card_accepts_namespaced_gps_from_existing_merged_history():
    assert 'const leaf=String(key).split(".").pop()' in JS
    assert 'leaf==="gps_track"||leaf==="gps_points"' in JS

def test_more_details_strip_internal_provider_namespace_from_labels():
    assert "const label=String(k).split('.').pop().replaceAll('_',' ')" in JS
