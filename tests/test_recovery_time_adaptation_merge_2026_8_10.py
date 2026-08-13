from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / 'custom_components/fitness/manager.py').read_text(encoding='utf-8')
SENSOR = (ROOT / 'custom_components/fitness/sensor.py').read_text(encoding='utf-8')
WORKOUTS = (ROOT / 'custom_components/fitness/providers/workouts.py').read_text(encoding='utf-8')
JS = (ROOT / 'custom_components/fitness/frontend/fitness-dashboard.js').read_text(encoding='utf-8')
DASH = (ROOT / 'custom_components/fitness/dashboard.py').read_text(encoding='utf-8')


def test_workout_history_is_deduplicated_on_read():
    start = MANAGER.index('def local_workouts')
    end = MANAGER.index('def latest_workout', start)
    assert 'return merged_workouts(result)' in MANAGER[start:end]
    assert 'a_live != b_live and start_delta <= 90' in WORKOUTS
    assert 'if da <= 0 or db <= 0:' in WORKOUTS


def test_adaptation_requires_a_mature_baseline():
    assert 'baseline_reliable = (' in SENSOR
    assert 'workouts_28d >= 6' in SENSOR
    assert 'active_days_28d >= 4' in SENSOR
    assert 'elif not baseline_reliable or evidence_count < 2:' in SENSOR


def test_adaptation_is_integrated_into_training_load_card():
    eval_start = JS.index('class FitnessEvaluationCard')
    eval_end = JS.index('class FitnessDashboardStrategy', eval_start)
    assert 'this._mount("fitness-training-adaptation-card")' not in JS[eval_start:eval_end]
    load_start = JS.index('class FitnessTrainingLoadCard')
    load_end = JS.index('class FitnessCompositeCard', load_start)
    block = JS[load_start:load_end]
    assert 'training_adaptation_status' in block
    assert 'baselineReliable' in block
    assert 'adaptationTones' in block


def test_recovery_time_sensor_and_card_exist():
    assert 'key="estimated_recovery_time"' in SENSOR
    assert 'def recovery_time_evaluation' in MANAGER
    assert 'fitness_next_workout_recovery_estimate_v2' in MANAGER
    assert 'async_track_time_interval(hass, recovery_time_tick, timedelta(minutes=15))' in SENSOR
    recovery = JS[JS.index('class FitnessRecoveryCard'):JS.index('class FitnessTrainingAdaptationCard')]
    assert 'e.estimated_recovery_time' in recovery


def test_frontend_revision_matches_backend():
    f = re.search(r'FITNESS_DASHBOARD_VERSION = "([^"]+)"', JS)
    b = re.search(r'_RESOURCE_URL = f".*?\\?v=([^"]+)"', DASH)
    assert f and b and f.group(1) == b.group(1)


def test_new_attributes_are_translated_in_every_language():
    langs = ('en','el','de','fr','es','it','pt','nl','pl','ru','uk','tr','zh','ja','ko')
    needed_recovery = {
        'estimated_total_recovery_hours','elapsed_hours_since_workout','level','level_display',
        'confidence_percent','last_workout_start','last_workout_end','sport','evidence',
        'workout_demand_components_hours','recovery_modifiers','data_source','method','formula',
        'diagnostic_interpretation',
    }
    needed_adaptation = {
        'baseline_reliable','minimum_workouts_28d_for_baseline','minimum_active_days_28d_for_baseline',
    }
    for lang in langs:
        data = json.loads((ROOT / f'custom_components/fitness/translations/{lang}.json').read_text(encoding='utf-8'))
        sensors = data['entity']['sensor']
        assert needed_recovery <= set(sensors['estimated_recovery_time']['state_attributes'])
        assert needed_adaptation <= set(sensors['training_adaptation_status']['state_attributes'])
