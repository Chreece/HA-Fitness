from pathlib import Path
ROOT=Path(__file__).parents[1]
MAN=(ROOT/'custom_components/fitness/manager.py').read_text()
JS=(ROOT/'custom_components/fitness/frontend/fitness-dashboard.js').read_text()
DASH=(ROOT/'custom_components/fitness/dashboard.py').read_text()
TV=(ROOT/'custom_components/fitness/tv_dashboard.py').read_text()
GAR=(ROOT/'custom_components/fitness/device_adapters/garmin/fit.py').read_text()
CYC=(ROOT/'custom_components/fitness/device_adapters/cycplus_m1.py').read_text()
ARCH=(ROOT/'custom_components/fitness/device_archives.py').read_text()
CONF=(ROOT/'custom_components/fitness/config_flow.py').read_text()
ACCESS=(ROOT/'custom_components/fitness/access_control.py').read_text()

def test_workouts_card_uses_route_and_compact_sport_specific_summary():
    assert 'extra.gps_track||extra.gps_points' in JS
    assert 'class="tools"' in JS and '… More' in JS
    assert 'Avg power' in JS and 'Pace' in JS and 'Best e1RM' in JS
    assert 'class="strava"' in JS
    assert '"gps_track": _gps_points(relevant)' in GAR
    assert '"gps_track": _gps_points(relevant)' in CYC

def test_ai_daily_plan_refreshes_at_midnight_sleep_and_provider_availability():
    assert 'hour=0, minute=0, second=1' in MAN
    assert '_sleep_plan_key' in MAN
    assert 'fresh completed sleep' in MAN
    assert 'service_registered' in MAN and 'Home Assistant AI available' in MAN
    assert 'selected AI available' in MAN

def test_goal_based_training_plan_and_guided_live_steps_are_shared_prescriptions():
    for key in ('CONF_TRAINING_GOAL','CONF_TRAINING_GOAL_DATE','CONF_TRAINING_DAYS_PER_WEEK'):
        assert key in CONF
    assert 'async_generate_training_plan' in MAN
    assert 'async_start_training_plan_day' in MAN
    assert '_async_run_prescription_steps' in MAN
    assert 'fitness/training/plan' in DASH
    assert 'fitness/training/step' in DASH
    assert 'fitness-training-plan-card' in JS
    assert 'active_workout_instruction' in JS

def test_tv_plugins_themes_and_remote_portal_are_real_surfaces():
    for card in ('plugin_rss','plugin_weather','plugin_lights','plugin_music','plugin_video','plugin_tts'):
        assert card in JS and card in TV
    for theme in ('fitness_performance','fitness_minimal','fitness_oled','fitness_glass','fitness_classic'):
        assert theme in CONF and theme in JS
    assert '/fitness-tv/main' in ACCESS
    assert 'entries||s.attributes.items||s.attributes.feed||s.attributes.news' in JS

def test_workout_export_only_appears_for_adapter_with_real_writer():
    assert 'workout_export_targets' in ARCH
    assert 'async_write_workout' in ARCH
    assert 'fitness/training/export_targets' in DASH
    assert 'fitness/training/export' in DASH
    assert 'watch-export' in JS
