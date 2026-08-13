"""Regression tests for Recovery & Readiness as the global Fitness pattern."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (
    ROOT / "custom_components/fitness/frontend/fitness-dashboard.js"
).read_text(encoding="utf-8")


def test_recovery_panel_remains_reference_pattern():
    assert ".recovery-readiness-panel{" in FRONTEND
    assert ".readiness-panel{" in FRONTEND
    assert ".next-workout{" in FRONTEND
    assert ".recovery-grid>div{" in FRONTEND


def test_recovery_card_is_also_a_tab_panel_without_double_background():
    themed = FRONTEND.split(
        "_fitnessInstallTabPanelTheme(FitnessRecoveryCard", 1
    )[1].split(
        "_fitnessInstallTabPanelTheme(FitnessSleepStageCard", 1
    )[0]
    assert "background:transparent !important" in themed
    assert "background:var(--card-background-color) !important" in themed


def test_live_card_is_one_panel_with_mini_cards():
    assert "border-radius:20px" in FRONTEND
    assert ".live-grid,.live-controls{padding:0;background:transparent}" in FRONTEND
    assert ".live-metric" in FRONTEND
    assert "background:var(--card-background-color)" in FRONTEND


def test_generated_live_view_still_uses_fitness_live_card():
    assert '{ type: "custom:fitness-live-workout-card", profile_entry_id: profile.entry_id }' in FRONTEND
