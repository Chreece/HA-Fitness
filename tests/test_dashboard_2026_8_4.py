import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "custom_components/fitness/dashboard.py"
FRONTEND = ROOT / "custom_components/fitness/frontend/fitness-dashboard.js"
INIT = ROOT / "custom_components/fitness/__init__.py"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def test_dashboard_release_files_and_version():
    manifest = json.loads((ROOT / "custom_components/fitness/manifest.json").read_text())
    assert manifest["version"] == "0.0.0" or re.fullmatch(
        r"\d{4}\.\d{1,2}\.\d+(?:a\d+|-beta\d+)?",
        manifest["version"],
    )
    assert DASHBOARD.is_file()
    assert FRONTEND.is_file()
    assert "## 2026.8.01a01" in CHANGELOG.read_text()


def test_dashboard_is_registered_after_lovelace_and_served_as_static_resource():
    text = DASHBOARD.read_text()
    assert "async_register_static_paths" in text
    assert "async_when_setup(hass, \"lovelace\"" in text
    assert "if not resources.loaded:" in text
    assert "await resources.async_load()" in text
    assert '"res_type": "module"' in text
    assert '"/fitness/frontend/fitness-dashboard.js"' in text
    assert "await async_setup_dashboard(hass)" in INIT.read_text()


def test_dashboard_strategy_and_visual_cards_are_bundled():
    text = FRONTEND.read_text()
    assert "ll-strategy-dashboard-fitness" in text
    assert "window.customStrategies" in text
    assert 'strategyType: "dashboard"' in text
    assert "custom:fitness-workout-card" in text
    assert "custom:fitness-sleep-recovery-card" in text
    assert "custom:fitness-evaluation-card" in text
    # Component cards remain bundled for advanced/manual use.
    assert "fitness-route-card" in text
    assert "fitness-comparison-card" in text
    assert "fitness-sleep-stage-card" in text
    assert 'type: "statistics-graph"' in text
    assert 'type: "sections"' in text


def test_dashboard_is_capability_aware_and_supports_route_discovery():
    backend = DASHBOARD.read_text()
    frontend = FRONTEND.read_text()
    assert "CONF_WORKOUT_DEVICE_IDS" in backend
    assert '"polyline", "route", "coordinates", "track", "gps_points"' in backend
    assert "const only = (_hass, entities, keys)" in frontend
    assert "route_candidates" in frontend
    assert "OpenStreetMap" in frontend


def test_dashboard_has_all_supported_languages():
    text = DASHBOARD.read_text()
    for lang in ("en", "el", "de", "fr", "es", "it", "pt", "nl", "pl", "ru", "uk", "tr", "zh", "ja", "ko"):
        assert f'    "{lang}":' in text


def test_readme_documents_dashboard_and_manual_resource_fallback():
    text = README.read_text()
    assert "## Fitness dashboard" in text
    assert "Community dashboards" in text
    assert "/fitness/frontend/fitness-dashboard.js" in text
    assert "OpenStreetMap" in text


def test_route_card_editor_selects_profile_and_auto_resolves_source():
    text = FRONTEND.read_text()
    assert 'static getConfigElement()' in text
    assert 'fitness-route-card-editor' in text
    assert 'profile_entry_id' in text
    assert 'type: "fitness/dashboard/config"' in text
    assert 'this._resolved = (profile?.route_candidates || [])[0] || null' in text
    assert 'entity: route.entity_id' not in text
    assert 'profile_entry_id: profile.entry_id' in text
