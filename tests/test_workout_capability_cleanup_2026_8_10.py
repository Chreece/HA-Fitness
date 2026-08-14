from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'custom_components/fitness/sensor.py').read_text()
M=(ROOT/'custom_components/fitness/manager.py').read_text()
J=(ROOT/'custom_components/fitness/frontend/fitness-dashboard.js').read_text()

def test_duplicate_workout_source_entity_removed():
    descriptions=S[S.index('# Workout device'):S.index('# Sleep device')]
    assert 'key="last_workout_source"' not in descriptions
    assert 'key="last_workout_sources"' in descriptions
    assert 'key == "last_workout_source"' in S
    assert 'registry.async_remove(registry_entry.entity_id)' in S

def test_provider_zero_placeholders_are_suppressed():
    assert 'def _meaningful_workout_value' in S
    for metric in ('workout_distance','workout_average_speed','workout_avg_power','workout_avg_cadence'):
        assert f'"{metric}"' in S
    assert 'abs(float(value)) < 1e-12' in S

def test_workout_registry_cleanup_is_startup_safe():
    assert 'key == "last_workout_source"' in S
    assert 'registry.async_remove(registry_entry.entity_id)' in S
    setup = S[S.index('async def async_setup_entry'):S.index('class FitnessSensor')]
    assert setup.count('registry.entities.values()') == 1
    initial = setup[:setup.index('def collect_new_entities')]
    assert '.native_value' not in initial
    assert 'manager.forget_materialized_sensor' in S
    assert 'def forget_materialized_sensor' in M

def test_workout_highlights_never_overflow_and_hide_zero_placeholders():
    section=J[J.index('class FitnessWorkoutHighlightsCard'):J.index('class FitnessStrengthDetailsCard')]
    assert 'zeroIsMissing' in section
    assert 'Math.abs(numeric) < 1e-12' in section
    assert 'overflow-wrap:anywhere' in section
    assert 'word-break:normal' in section
    assert 'workout-name' in section
