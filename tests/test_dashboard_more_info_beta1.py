from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")

def test_release_version_is_harel_safe_beta_format():
    version = json.loads((ROOT / "custom_components/fitness/manifest.json").read_text())["version"]
    assert version == "0.0.0" or re.fullmatch(r"\d{4}\.\d{1,2}\.\d+(?:a\d+|-beta\d+)?", version)

def test_dashboard_entity_tiles_open_more_info():
    assert 'new CustomEvent("hass-more-info"' in JS
    assert 'data-more-info=' in JS
    assert '_fitnessBindMoreInfo(this)' in JS
    assert 'class FitnessLiveWorkoutCard' in JS
    assert 'class FitnessWorkoutHighlightsCard' in JS
    assert 'class FitnessRecoveryCard' in JS
    assert 'class FitnessTrainingLoadCard' in JS
