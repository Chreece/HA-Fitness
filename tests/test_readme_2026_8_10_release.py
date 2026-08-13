from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_readme_has_branded_header_and_overview_graphic():
    assert "assets/fitness-logo.png" in README
    assert "assets/fitness-logo-dark.png" in README
    assert "assets/fitness-overview.png" in README


def test_readme_keeps_tldr_and_questions_answers():
    assert "## TL;DR" in README
    assert "## Questions & answers" in README
    assert "### Why install Fitness if my watch integration already works?" in README
    assert "### Does Fitness use AI to calculate my metrics?" in README


def test_readme_is_evergreen_not_release_notes():
    assert "## What's new in 2026.8.10" not in README
    assert "## What's new in 2026.8.11" not in README
    assert "[Changelog](CHANGELOG.md)" in README
    assert "[Workout calendar](docs/WORKOUT_CALENDAR.md)" in README


def test_readme_has_science_and_health_boundaries():
    assert "[Science & methods](docs/SCIENCE.md)" in README
    assert "not a medical device or health advisor" in README
    assert "Do not use Fitness to diagnose" in README
    assert "[LICENSE](LICENSE)" in README


def test_changelog_keeps_2026_8_10_and_documents_2026_8_11():
    assert "## 2026.8.10 — Recovery, readiness & personal context" in CHANGELOG
    assert "## 2026.8.11 — Unified workout calendar & historical reconciliation" in CHANGELOG
    assert "[Science & methods](docs/SCIENCE.md)" in CHANGELOG
