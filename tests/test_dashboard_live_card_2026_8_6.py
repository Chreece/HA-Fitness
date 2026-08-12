from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def test_live_workout_is_public_add_card_option():
    assert "class FitnessLiveWorkoutCard extends FitnessAutoProfileCard" in JS
    assert 'customElements.define("fitness-live-workout-card", FitnessLiveWorkoutCard)' in JS
    assert 'type: "fitness-live-workout-card"' in JS
    assert 'name: "Fitness live workout"' in JS


def test_live_workout_uses_normalized_fitness_entities_and_controls():
    for key in (
        "session_status", "session_duration", "current_heart_rate", "current_power",
        "current_cadence", "current_speed", "current_pace", "current_distance",
        "start_workout", "pause_workout", "resume_workout", "stop_workout",
    ):
        assert f'"{key}"' in JS
    assert 'callService("button", "press"' in JS


def test_sleep_recovery_metric_grid_wraps_instead_of_overflowing():
    assert "repeat(auto-fit,minmax(118px,1fr))" in JS
    assert "overflow-wrap:anywhere" in JS
    assert ".metric{background:var(--secondary-background-color);padding:10px;border-radius:12px;min-width:0;overflow:hidden}" in JS


def test_sleep_stage_legend_is_width_safe():
    start = JS.index("class FitnessSleepStageCard")
    end = JS.index("const _fitnessNumber")
    sleep_stage = JS[start:end]

    assert "flex-direction:column" in sleep_stage
    assert "grid-template-columns:10px minmax(0,1fr) minmax(72px,max-content) 38px" in sleep_stage
    assert "overflow-wrap:anywhere" not in sleep_stage
    assert "word-break:normal" in sleep_stage
    assert "overflow-wrap:normal" in sleep_stage
    assert "white-space:nowrap" in sleep_stage

def test_changelog_mentions_live_card_and_responsive_fix():
    assert "Fitness live workout" in CHANGELOG
    assert "auto-fit/wrap" in CHANGELOG
