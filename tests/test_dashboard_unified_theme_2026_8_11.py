"""2026.8.11 unified Fitness tab-card visual contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = (
    ROOT / "custom_components/fitness/frontend/fitness-dashboard.js"
).read_text(encoding="utf-8")


def test_no_outer_accent_rail_design():
    assert "border-left:4px solid var(--fitness-card-accent)" not in FRONTEND


def test_composite_shell_is_only_header_and_stack():
    assert ".composite-body{" in FRONTEND
    assert "display:grid;gap:7px" in FRONTEND
    assert "background:transparent" in FRONTEND


def test_shared_tab_panel_theme_exists():
    assert "const _FITNESS_TAB_PANEL_BASE" in FRONTEND
    assert "border-radius:20px !important" in FRONTEND
    assert "background:var(--secondary-background-color) !important" in FRONTEND
    assert "const _fitnessInstallTabPanelTheme" in FRONTEND


def test_all_major_fitness_sections_use_shared_tab_pattern():
    for card in (
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
    ):
        assert f"_fitnessInstallTabPanelTheme({card}" in FRONTEND


def test_inner_metrics_are_mini_cards():
    assert "background:var(--card-background-color) !important" in FRONTEND
    assert "border-radius:11px !important" in FRONTEND


def test_single_frontend_revision_contract_stays_unchanged():
    assert 'const FITNESS_DASHBOARD_VERSION = "2026.8.11.1";' in FRONTEND
