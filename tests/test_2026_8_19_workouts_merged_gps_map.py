from pathlib import Path
ROOT = Path(__file__).parents[1]
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()

def test_dashboard_promotes_namespaced_merged_provider_gps_track():
    assert '_route_points(data.get("gps_track")) or _route_points(extra)' in DASH
    assert '_route_points(data.get("provider_values") or {})' in DASH
    assert 'extra["gps_track"] = track' in DASH

def test_workouts_card_accepts_namespaced_gps_from_existing_merged_history():
    assert 'const leaf=String(key).split(".").pop()' in JS
    assert 'keys.has(leaf)' in JS and '"gps_track","gps_points","route","track"' in JS

def test_more_details_strip_internal_provider_namespace_from_labels():
    assert "const label=String(k).split('.').pop().replaceAll('_',' ')" in JS
