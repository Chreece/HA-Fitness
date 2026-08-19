from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIT=ROOT/'custom_components'/'fitness'
JS=(FIT/'frontend'/'fitness-dashboard.js').read_text()
INIT=(FIT/'__init__.py').read_text()
MANAGER=(FIT/'manager.py').read_text()
SERVICES=(FIT/'services.yaml').read_text()
CONFIG=(FIT/'config_flow.py').read_text()


def test_workouts_card_owns_calendar_popup_and_navigation():
    assert 'this.config.title||"Workouts"' in JS
    assert 'class="history"' in JS
    assert '<dialog><fitness-workout-browser-card>' in JS
    assert 'fitness-workout-selected' in JS
    assert 'data-prev' in JS and 'data-next' in JS
    assert 'data-edit' in JS and 'data-delete' in JS
    assert 'gps_track' in JS and 'selected-route' in JS


def test_history_popup_is_calendar_selector_not_second_management_card():
    start=JS.index('class FitnessWorkoutBrowserCard')
    end=JS.index('class FitnessBodyCompositionCard',start)
    block=JS[start:end]
    assert 'class="calendar"' in block
    assert 'workout-choice' in block
    assert 'fitness/workouts/edit' not in block
    assert 'fitness/workouts/delete' not in block
    assert 'fitness/workouts/empty' not in block


def test_maintenance_services_are_exposed_and_regenerable_clear_removes_guards():
    for name in ('clear_workout_history','clear_fit_files','manage_bluetooth_device','delete_workout_tombstone','edit_workout_tombstone','clear_workout_tombstones','clear_saved_data'):
        assert f'{name}:' in SERVICES
        assert name in INIT
    assert 'self.deleted_workouts_before = None' in MANAGER
    assert 'await self._async_reconcile_external_workouts()' in MANAGER
    assert 'CONF_FIT_FILE_RETENTION_COUNT' in CONFIG
    assert 'DEFAULT_FIT_FILE_RETENTION_COUNT' in CONFIG
    assert 'Source files on watches/cycling computers are never deleted.' in SERVICES
    assert 'shared with another integration' in INIT
