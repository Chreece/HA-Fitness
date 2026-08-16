from pathlib import Path
import json
import re
ROOT=Path(__file__).resolve().parents[1]
C=(ROOT/'custom_components/fitness/const.py').read_text()
I=(ROOT/'custom_components/fitness/__init__.py').read_text()
N=(ROOT/'custom_components/fitness/number.py').read_text()
W=(ROOT/'custom_components/fitness/providers/workouts.py').read_text()
M=(ROOT/'custom_components/fitness/manager.py').read_text()
J=(ROOT/'custom_components/fitness/frontend/fitness-dashboard.js').read_text()

def test_beta2_version_and_number_platform():
    version=json.loads((ROOT/'custom_components/fitness/manifest.json').read_text())['version']
    assert version == "0.0.0" or re.fullmatch(r"\d{4}\.\d{1,2}\.\d+(?:(?:a\d+)|-(?:alpha|beta)\d+)?", version)
    assert '"number"' in I
    assert '_attr_native_step = 1' in N and '_attr_native_min_value = 1' in N and '_attr_native_max_value = 10' in N

def test_rpe_provider_and_recalculation():
    assert 'ratingOfPerceivedExertion' in W and 'activityRPE' in W
    assert 'session_rpe_load' in W
    assert 'async def async_set_session_rpe' in M
    assert 'await self._async_refresh_long_term_statistics()' in M

def test_rpe_reminder_only_when_missing():
    assert 'if workout.session_rpe is None' in M
    assert '"rpe_reminder"' in M
    assert 'one whole' in M and 'RPE number from 1 to 10' in M

def test_optional_strength():
    assert 'CONF_DETAILED_STRENGTH_ANALYSIS' in C
    assert 'self.config.get(CONF_DETAILED_STRENGTH_ANALYSIS)' in M
    S=(ROOT/'custom_components/fitness/strength.py').read_text()
    assert 'estimated_1rm_epley' in S

def test_cards_include_rpe_and_beta2_metrics():
    assert 'class FitnessWorkoutRpeCard' in J
    assert 'fitness-workout-rpe-card' in J
    assert 'data-rpe=' in J
    assert 'callService("number", "set_value"' in J
    live=J[J.index("class FitnessLiveWorkoutCard"):J.index("class FitnessWorkoutRpeCard")]
    assert 'session_rpe' not in live
    assert 'last_workout_session_rpe_load' in J
    assert 'last_workout_estimated_1rm' in J
    assert 'device_info(entry, "workout")' in N

def test_all_languages_have_number_translation():
    for path in [ROOT/'custom_components/fitness/strings.json', *sorted((ROOT/'custom_components/fitness/translations').glob('*.json'))]:
        d=json.loads(path.read_text())
        assert d['entity']['number']['session_rpe']['name']
        assert d['options']['step']['workout_devices']['data']['detailed_strength_analysis']
