from pathlib import Path
from custom_components.fitness.workout_prescriptions import fitness_test_catalog, normalize_prescription

ROOT=Path(__file__).parents[1]
DASH=(ROOT/'custom_components/fitness/dashboard.py').read_text()
MGR=(ROOT/'custom_components/fitness/manager.py').read_text()
JS=(ROOT/'custom_components/fitness/frontend/fitness-dashboard.js').read_text()

def test_builtin_tests_share_canonical_prescription_model():
    tests=fitness_test_catalog()
    assert {x['sport'] for x in tests} >= {'running','cycling','strength'}
    assert all(x['steps'] for x in tests)
    assert all(x['schema_version']==1 for x in tests)

def test_prescription_is_bounded():
    x=normalize_prescription({'name':'x'*500,'steps':[{'name':'s'}]*100})
    assert len(x['name']) <= 160
    assert len(x['steps']) == 64

def test_dashboard_exposes_test_catalog_and_start_control():
    assert 'fitness/training/tests' in DASH
    assert 'fitness/training/start' in DASH
    assert 'async_control_profile_ids' in DASH
    assert 'async_start_fitness_test' in MGR
    assert 'async_start_ai_daily_workout' in MGR
    assert 'fitness-tests-card' in JS
