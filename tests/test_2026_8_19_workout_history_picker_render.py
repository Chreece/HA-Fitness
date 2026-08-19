from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TV = (ROOT / 'custom_components/fitness/tv_dashboard.py').read_text()
JS = (ROOT / 'custom_components/fitness/frontend/fitness-dashboard.js').read_text()


def test_workout_history_is_persistable_tv_card():
    block = TV.split('TV_CARD_IDS: tuple[str, ...] = (', 1)[1].split(')', 1)[0]
    assert '"workout_history"' not in block
    assert '"workout"' in block


def test_workout_history_catalog_maps_to_real_custom_element():
    assert '{id:"workout", element:"fitness-workout-card"' in JS
    assert 'fitness-workout-selected' in JS
    assert 'customElements.define("fitness-workout-browser-card", FitnessWorkoutBrowserCard)' in JS


def test_card_picker_reflows_dashboard_instead_of_covering_it():
    assert 'this.setAttribute("card-picker-open", "")' in JS
    assert ':host([card-picker-open]) .tv-oled-stage{padding-right:' in JS
    assert 'this.removeAttribute("card-picker-open")' in JS
