from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")

LANGS = ("en","el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko")


def test_training_load_uses_multicolour_scale_and_baseline_state():
    start = JS.index("class FitnessTrainingLoadCard")
    end = JS.index("\nclass ", start + 10)
    card = JS[start:end]
    assert "linear-gradient(90deg,#42a5f5" in card
    assert "baselineReliable" in card
    assert 'zone = "balanced"' in card
    assert 'zone = "excessive"' in card
    assert 'baseline_building_hint' in card


def test_training_load_does_not_show_unreliable_ratio_as_number():
    start = JS.index("class FitnessTrainingLoadCard")
    end = JS.index("\nclass ", start + 10)
    card = JS[start:end]
    assert 'baselineReliable && ratio != null ? `${ratio.toFixed(2)}×` : "—"' in card


def test_training_load_new_labels_exist_for_all_languages():
    for code in LANGS:
        start = DASH.index(f'"{code}": {{')
        chunk = DASH[start:start+10000]
        for key in ("load_ratio","baseline_building","baseline_building_hint","load_low","load_balanced","load_elevated","load_high","load_excessive"):
            assert f'"{key}":' in chunk


def test_frontend_backend_revision_match():
    front = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    back = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert front and back
    assert front.group(1) == back.group(1)
