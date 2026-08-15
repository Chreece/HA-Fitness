from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_readiness_and_recovery_progress_share_one_score_bar_component():
    score_bar = FRONTEND.split("const scoreBar =", 1)[1].split("const signalLabels", 1)[0]
    assert 'kind:"readiness"' in score_bar
    assert 'kind:"progress"' in score_bar
    assert 'recovery-score-stack' in score_bar
    assert '--score-tone:${tone}' in score_bar
    assert '#c62828 0%' not in score_bar
    recovery_card = FRONTEND.split("class FitnessRecoveryCard", 1)[1].split("class FitnessTrainingAdaptationCard", 1)[0]
    assert '${readinessStack}' in recovery_card
    assert 'recoveryProgressBar' in recovery_card


def test_training_component_is_not_duplicated_as_small_readiness_tile():
    component_block = FRONTEND.split("const componentRows = [", 1)[1].split("].map", 1)[0]
    assert '["training",' not in component_block


def test_vo2_current_and_predicted_positions_share_absolute_axis_when_available():
    assert 'useAbsoluteVo2Scale' in FRONTEND
    assert '((current - progressMin) / progressSpan) * 100' in FRONTEND
    assert '((predictedAbsolute - progressMin) / progressSpan) * 100' in FRONTEND
    assert '.vo2-reference{position:absolute;top:-4px' in FRONTEND
    assert 'background:#fff' in FRONTEND
    reference_css = FRONTEND.split('.vo2-reference{', 1)[1].split('.vo2-marker{', 1)[0]
    assert ':after' not in reference_css
