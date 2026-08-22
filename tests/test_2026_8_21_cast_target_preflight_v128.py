from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
FRONT = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()

def test_explicit_fitness_cast_replaces_only_selected_targets_active_app():
    assert "replace_active_app: bool = False" in DASH
    assert "replace_active_app=True" in DASH
    assert "Never\n        # touch any other Cast device" in DASH
    assert "if current_app_id:" in DASH

def test_cache_contract_v128():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in FRONT
    assert '?v=unreleased-138' in DASH
