from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_recovery_card_limiting_factor_does_not_reference_undefined_identifier():
    start = JS.index("class FitnessRecoveryCard")
    end = JS.index("class FitnessTrainingAdaptationCard", start)
    section = JS[start:end]
    assert "_fitnessEscape(limitingFactor)" in section
    assert "limiting_factor || limitingFactor" not in section


def test_recovery_card_still_renders_primary_recovery_sections():
    start = JS.index("class FitnessRecoveryCard")
    end = JS.index("class FitnessTrainingAdaptationCard", start)
    section = JS[start:end]
    assert 'class="readiness-panel' in section
    assert 'class="next-workout' in section
    assert 'class="recovery-progress"' in section
    assert 'class="signals"' in section
