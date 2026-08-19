from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()


def test_three_consolidated_cards_are_registered():
    for tag in ("fitness-workout-card", "fitness-sleep-recovery-card", "fitness-evaluation-card"):
        assert f'customElements.define("{tag}"' in JS
        assert f'type: "{tag}"' in JS


def test_workout_composite_is_capability_aware():
    assert 'gps_track' in JS
    assert 'class FitnessWorkoutCard' in JS
    assert 'data-prev' in JS and 'data-next' in JS


def test_ui_language_is_independent_from_profile_language():
    assert '"labels_by_language"' in DASH
    assert 'this._hass?.language || "en"' in JS
    assert 'profile.labels_by_language?.[ui]' in JS


def test_dashboard_uses_consolidated_cards():
    assert 'section([{ type: "custom:fitness-workout-card"' in JS
    assert 'section([{ type: "custom:fitness-sleep-recovery-card"' in JS
    assert 'section([{ type: "custom:fitness-evaluation-card"' in JS


def test_changelog_documents_consolidation():
    assert "consolidated user-focused views" in CHANGELOG
