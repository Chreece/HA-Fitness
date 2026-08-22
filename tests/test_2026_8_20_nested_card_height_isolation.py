from pathlib import Path

JS = Path("custom_components/fitness/frontend/fitness-dashboard.js").read_text()


def test_dashboard_min_height_targets_only_root_ha_card():
    assert ':host([fitness-natural-height]) > ha-card{' in JS
    assert ':host([fitness-user-sized]) > ha-card{' in JS
    assert ':host([fitness-natural-height]) ha-card{' not in JS
    assert ':host([fitness-user-sized]) ha-card{' not in JS


def test_sport_comparison_nested_cards_keep_intrinsic_height():
    start = JS.index('class FitnessComparisonCard extends HTMLElement')
    end = JS.index('class FitnessSleepStageCard extends HTMLElement')
    block = JS[start:end]
    assert '<div class="comparison-stack">${cards}</div>' in block
    assert '<ha-card class="sport-comparison">' in block
    assert '.sport-comparison{overflow:hidden;align-self:start;height:auto!important;min-height:0!important}' in block
