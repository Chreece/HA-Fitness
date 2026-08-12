from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def test_all_custom_cards_have_visual_editors():
    assert 'fitness-route-card-editor' in JS
    assert 'fitness-comparison-card-editor' in JS
    assert 'fitness-sleep-stage-card-editor' in JS
    assert 'static getConfigElement() { return document.createElement("fitness-comparison-card-editor"); }' in JS
    assert 'static getConfigElement() { return document.createElement("fitness-sleep-stage-card-editor"); }' in JS


def test_profile_selector_auto_resolves_comparison_and_sleep_entities():
    assert 'profile_entry_id' in JS
    assert 'last_workout_efficiency_vs_baseline' in JS
    assert 'last_workout_trimp_vs_recent' in JS
    assert 'last_sleep_awake' in JS
    assert 'last_sleep_rem' in JS
    assert 'VISUAL_EDITOR_COPY' in JS


def test_dashboard_strategy_uses_profile_based_consolidated_cards():
    assert 'type: "custom:fitness-workout-card", profile_entry_id: profile.entry_id' in JS
    assert 'type: "custom:fitness-sleep-recovery-card", profile_entry_id: profile.entry_id' in JS
    assert 'type: "custom:fitness-evaluation-card", profile_entry_id: profile.entry_id' in JS


def test_changelog_mentions_visual_editors():
    assert "visual editors" in CHANGELOG.lower()
