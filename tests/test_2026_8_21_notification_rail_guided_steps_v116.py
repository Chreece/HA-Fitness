from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
DASH = (ROOT / "custom_components/fitness/dashboard.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
ACCOUNTS = (ROOT / "custom_components/fitness/fitness_accounts.py").read_text()

def test_v116_notification_rail_is_pinned_and_browsable():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-138"' in JS
    assert 'class="fitness-notification-bar' in JS
    assert '.weight-confirmation-host{position:sticky;top:4px;z-index:88' in JS
    assert 'notification-prev' in JS and 'notification-next' in JS
    assert 'this._notificationIndex' in JS

def test_workout_step_temporarily_overrides_normal_notification():
    assert 'this._stepNotificationUntil = Date.now() + 10000' in JS
    assert 'workout-step-notification' in JS
    assert 'active_workout_instruction' in JS and 'active_workout_step' in JS
    assert 'this._stepNotificationUntil = 0' in JS

def test_structured_workout_steps_are_spoken_by_existing_tts_pipeline():
    assert 'await self._async_speak(instruction)' in MANAGER
    assert 'await self._async_speak(str(step["instruction"]))' in MANAGER
    assert 'tts_announcements_enabled' in MANAGER

def test_local_unassigned_sensors_can_be_claimed_from_notification():
    assert '"notification_sensor_candidates": notification_sensor_candidates' in DASH
    assert 'fitness/sensor/claim' in DASH
    assert 'local_ha_hardware_allowed' in DASH
    assert 'runtime.sensor_assigned_profile_ids(sensor_id)' in DASH
    assert '"fitness/sensor/claim": ("dashboard", "websocket_sensor_claim")' in ACCOUNTS
    assert 'type:"fitness/sensor/claim"' in JS

def test_notification_labels_exist_in_all_dashboard_languages():
    for key in ("notifications","notification_previous","notification_next","notification_apply","notification_ignore","notification_pair","notification_device_found","notification_device_found_body","notification_workout_step","notification_count"):
        assert DASH.count(f'"{key}"') >= 15
