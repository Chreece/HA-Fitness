from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")

LANGS = ("en","el","de","fr","es","it","pt","nl","pl","ru","uk","tr","zh","ja","ko")


def test_recovery_card_does_not_squeeze_two_heroes_side_by_side():
    start = JS.index("class FitnessRecoveryCard")
    end = JS.index("class FitnessTrainingLoadCard", start + 10)
    card = JS[start:end]
    assert 'class="readiness-panel entity-link"' in card
    assert 'class="next-workout entity-link"' in card
    assert "dual-hero" not in card
    assert "ready_for_next_workout_at" in card
    assert "broader_recovery_window" in card
    assert "recovery_progress_percent" in card
    assert "recovery_signals" in card
    assert "@media(max-width:520px)" in card


def test_training_adaptation_is_integrated_into_training_load():
    start = JS.index("class FitnessTrainingLoadCard")
    end = JS.index("class FitnessCompositeCard", start + 10)
    card = JS[start:end]
    assert 'class="adapt-summary entity-link"' in card
    assert "adaptationTones" in card
    assert "adaptation_building" in card
    assert "adaptation_baseline" in card
    assert "adaptation_fitness" in card
    assert "adaptation_recovery" in card

    eval_start = JS.index("class FitnessEvaluationCard")
    eval_end = JS.index("class FitnessDashboardStrategy", eval_start + 10)
    evaluation = JS[eval_start:eval_end]
    assert 'this._mount("fitness-training-load-card")' in evaluation
    assert 'this._mount("fitness-training-adaptation-card")' not in evaluation


def test_new_card_labels_exist_in_all_languages():
    for code in LANGS:
        start = DASH.index(f'"{code}": {{')
        chunk = DASH[start:start+12000]
        for key in (
            "broader_recovery_window",
            "adaptation_evidence",
            "adaptation_baseline",
            "adaptation_fitness",
            "adaptation_recovery",
            "adaptation_building",
        ):
            assert f'"{key}":' in chunk


def test_frontend_backend_revision_match():
    front = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    back = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert front and back
    assert front.group(1) == back.group(1)
