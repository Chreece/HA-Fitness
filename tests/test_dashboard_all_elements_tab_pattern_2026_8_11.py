"""Every major custom Fitness dashboard element should use the tab-card pattern."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (
    ROOT / "custom_components/fitness/frontend/fitness-dashboard.js"
).read_text(encoding="utf-8")


EXPECTED_THEMED_CARDS = (
    "FitnessWorkoutHighlightsCard",
    "FitnessRouteCard",
    "FitnessWorkoutRpeCard",
    "FitnessComparisonCard",
    "FitnessStrengthDetailsCard",
    "FitnessRecoveryCard",
    "FitnessSleepStageCard",
    "FitnessProgressCard",
    "FitnessTrainingAdaptationCard",
    "FitnessTrainingLoadCard",
    "FitnessTodayCard",
)


def test_expected_cards_are_explicitly_themed():
    for name in EXPECTED_THEMED_CARDS:
        assert f"_fitnessInstallTabPanelTheme({name}" in FRONTEND


def test_panel_theme_uses_recovery_readiness_surface_hierarchy():
    assert "background:var(--secondary-background-color) !important" in FRONTEND
    assert "background:var(--card-background-color) !important" in FRONTEND
    assert "border-radius:22px !important" in FRONTEND
    assert "border-radius:11px !important" in FRONTEND
