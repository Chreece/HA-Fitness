from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text(encoding="utf-8")

def test_recovery_current_contract():
    card = JS[JS.index("class FitnessRecoveryCard"):JS.index("class FitnessTrainingLoadCard")]
    assert 'class="recovery-readiness-panel"' in card
    assert 'class="recovery-score-stack"' in card
    assert 'kind:"readiness"' in card
    assert 'kind:"progress"' in card
    assert 'class="next-workout entity-link"' in card
    assert 'class="dual-hero"' not in card
    assert "ready_for_next_workout_at" in card
    assert "broader_recovery_window" in card
    assert "recovery_progress_percent" in card
    assert "recovery_signals" in card
    assert "@media(max-width:520px)" in card

def test_adaptation_current_contract():
    load = JS[JS.index("class FitnessTrainingLoadCard"):JS.index("class FitnessCompositeCard")]
    assert "adaptationTones" in load
    assert 'class="adapt-summary entity-link"' in load
    assert "adaptation_building" in load
    evaluation = JS[JS.index("class FitnessEvaluationCard"):JS.index("class FitnessDashboardStrategy")]
    assert 'this._mount("fitness-training-adaptation-card")' not in evaluation

def test_resource_revision_only_needs_to_match():
    f = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    b = re.search(r'_RESOURCE_URL = f".*?\?v=([^"]+)"', DASH)
    assert f and b and f.group(1) == b.group(1)
