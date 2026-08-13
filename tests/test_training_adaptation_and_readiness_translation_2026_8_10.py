import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SENSOR=(ROOT/'custom_components/fitness/sensor.py').read_text()
CODES=('en','el','de','fr','es','it','pt','nl','pl','ru','uk','tr','zh','ja','ko')

def load(code):
    p=ROOT/'custom_components/fitness'/('strings.json' if code=='en' else f'translations/{code}.json')
    return json.loads(p.read_text())

def test_readiness_every_runtime_attribute_is_translated_everywhere():
    keys={'level','level_display','confidence_percent','components_available','components','reason','data_source','updated_at','scientific_basis','additional_scientific_basis','formula','data_used','what_it_means','why_useful'}
    for code in CODES:
        attrs=load(code)['entity']['sensor']['readiness']['state_attributes']
        assert keys <= set(attrs), (code, keys-set(attrs))

def test_training_adaptation_sensor_and_attributes_exist_all_languages():
    keys={'status','workouts_28d','active_days_28d','trimp_7d','trimp_28d_weekly_equivalent','recent_to_baseline_load_ratio','vo2max_slope_percent_per_30d','hrv_7d_vs_baseline_percent','resting_hr_vs_28d_bpm','readiness_score','evidence_count','causal_interpretation','diagnostic_interpretation','scientific_basis','formula','data_used','what_it_means','why_useful'}
    for code in CODES:
        sensor=load(code)['entity']['sensor']['training_adaptation_status']
        assert sensor.get('name')
        assert keys <= set(sensor['state_attributes']), (code, keys-set(sensor['state_attributes']))

def test_translation_sensor_schema_parity_all_supported_languages():
    english=load('en')['entity']['sensor']
    for code in CODES[1:]:
        translated=load(code)['entity']['sensor']
        assert set(english) == set(translated), code
        for key,item in english.items():
            assert set((item.get('state_attributes') or {})) == set((translated[key].get('state_attributes') or {})), (code,key)

def test_training_adaptation_is_fitness_owned_multisignal_not_provider_status():
    assert 'Desc(key="training_adaptation_status"' in SENSOR
    assert 'def _training_adaptation_evaluation' in SENSOR
    block=SENSOR[SENSOR.index('def _training_adaptation_evaluation'):SENSOR.index('def _localized_training_adaptation_status')]
    for token in ('banister_trimp_7d','vo2max_slope_percent_per_30d','sleep_hrv_7d_vs_baseline_percent','resting_hr_vs_28d','readiness_evaluation'):
        assert token in block
    assert 'provider_training_status' not in block
