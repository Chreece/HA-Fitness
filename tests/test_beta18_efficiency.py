from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
M=(ROOT/'custom_components/fitness/manager.py').read_text()
S=(ROOT/'custom_components/fitness/sensor.py').read_text()
A=(ROOT/'custom_components/fitness/providers/autofill.py').read_text()
F=(ROOT/'custom_components/fitness/config_flow.py').read_text()

def test_periodic_derived_calculations_30s():
    assert 'await asyncio.sleep(30.0)' in M
    start=S.index('if self.entity_description.kind == "live":')
    end=S.index('if self.entity_description.kind == "workout":',start)
    assert 'self.manager.evaluation()' not in S[start:end]
    assert 'live_derived_values()' in S[start:end]

def test_cached_stats_and_coaching():
    a=M.index('def live_session_statistics'); b=M.index('async def _async_delayed_long_term_refresh',a)
    assert 'for sample in self.samples' not in M[a:b]
    a=M.index('def live_coaching_context'); b=M.index('def _periodic_live_interval_seconds',a)
    assert 'self.evaluation()' not in M[a:b]

def test_strict_autofill_and_antplus_defaults():
    assert 'EXACT_PROFILE_KEYS' in A
    assert "('garmin_connect',CONF_THRESHOLD_PACE)" in A
    assert "('hevy',CONF_WEIGHT)" in A
    assert "('oura',CONF_VO2MAX)" in A
    assert 'profile_entity_choices(hass, field, profile_entry_id)' in A
    assert 'choices[0]["value"]' in A
    assert 'live_device_choices(self.hass)' in F
    assert 'workout_device_choices(self.hass)' in F

def test_max_hr_not_autofilled():
    section=A[A.index('EXACT_PROFILE_KEYS'):A.index('WORKOUT_DOMAINS')]
    assert 'CONF_MAX_HR' not in section

def test_ai_and_tts_are_mutually_exclusive():
    a=M.index('async def _call_ai('); b=M.index('async def _call_ai_unlocked',a)
    block=M[a:b]
    assert 'async with self._ai_lock:' in block
    assert 'async with self._tts_playback_lock:' in block

def test_light_cues_serialized_and_restore_finally():
    assert 'self._light_feedback_serial_lock = asyncio.Lock()' in M
    for name in ('_async_session_status_cue','_async_live_intensity_feedback'):
        a=M.index('async def '+name); block=M[a:a+4500]
        assert 'async with self._light_feedback_serial_lock:' in block
        assert 'finally:' in block
        assert '_async_restore_feedback_lights' in block
    for attr in ('rgbw_color','rgbww_color','color_temp_kelvin','color_temp','brightness','effect'):
        assert attr in M
