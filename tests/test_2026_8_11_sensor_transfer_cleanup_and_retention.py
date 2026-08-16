"""2026.8.11 ownership transfer, cleanup, retention and startup regressions."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT/"custom_components/fitness/live/runtime.py").read_text()
IDENTITY = (ROOT/"custom_components/fitness/live/device_identity.py").read_text()
INIT = (ROOT/"custom_components/fitness/__init__.py").read_text()
CONFIG = (ROOT/"custom_components/fitness/config_flow.py").read_text()
SELECT = (ROOT/"custom_components/fitness/select.py").read_text()
CALENDAR = (ROOT/"custom_components/fitness/calendar.py").read_text()


def test_catalog_is_not_read_from_ble_advertisement_callback():
    load_body = IDENTITY.split("def load_catalog()",1)[1].split("def canonical_identity_fields",1)[0]
    assert "read_text" not in load_body
    assert "return _CATALOG" in load_body
    assert "JSONDecodeError" in IDENTITY


def test_adapter_switch_is_the_only_transport_lifecycle_control():
    assert "_sensor_workout_capture_baseline" not in RUNTIME
    assert "_sensor_workout_capture_override" not in RUNTIME
    assert "async_set_sensor_transport_capture" not in RUNTIME
    assert "async_start_capture" not in RUNTIME
    assert "async_stop_capture" not in RUNTIME
    claim = RUNTIME.split("async def _claim_transport", 1)[1].split(
        "async def _release_transport", 1
    )[0]
    assert "adapter_enabled(transport)" in claim


def test_gatt_fallback_and_ant_return_are_automatic():
    choose = RUNTIME.split("def choose_transport",1)[1].split("async def _claim_transport",1)[0]
    assert 'return "antplus"' in choose
    assert 'return "bluetooth"' in choose
    assert 'self.adapter_enabled("antplus")' in choose
    assert 'self.adapter_enabled("bluetooth")' in choose
    assert "_sensor_workout_capture_baseline" not in choose


def test_mid_workout_transfer_is_explicit_and_safe():
    transfer = RUNTIME.split("async def async_transfer_workout_sensor_owner",1)[1].split(
        "def profile_has_assigned_live_sensor",1
    )[0]
    assert "Pause the current sensor owner" in transfer
    assert "_sensor_workout_owner[sensor_id] = target_entry_id" in transfer
    assert "measurement_sources" in transfer
    assert "measurement_time.pop" in transfer
    assert "async_disconnect_sensor" in transfer
    assert "FitnessSensorWorkoutOwnerSelect" in SELECT
    assert '"select"' in INIT.split("HUB_PLATFORMS =",1)[1].splitlines()[0]


def test_retention_is_inside_workout_section_not_top_level_menu():
    menu = CONFIG.split("async def async_step_init",1)[1].split("async def async_step_sensor_assignments",1)[0]
    assert 'menu.extend(["workout_devices", "sleep_devices", "ai", "feedback", "tv_dashboard"])' in menu
    workout = CONFIG.split("async def async_step_workout_devices",1)[1].split("async def async_step_history",1)[0]
    assert "CONF_WORKOUT_RETENTION_DAYS" in workout


def test_retention_has_translation_in_every_language():
    paths = [ROOT/"custom_components/fitness/strings.json", *(ROOT/"custom_components/fitness/translations").glob("*.json")]
    for path in paths:
        data=json.loads(path.read_text())
        for section in ("config","options"):
            step=data[section]["step"]["workout_devices"]
            assert step["data"]["workout_retention_days"]
            assert step["data_description"]["workout_retention_days"]


def test_removing_profile_deletes_fitness_owned_store():
    hook = INIT.split("async def async_remove_entry",1)[1].split("async def async_remove_config_entry_device",1)[0]
    assert "STORE_KEY_PREFIX" in hook
    assert "await store.async_remove()" in hook
    assert "async_unregister_profile" in hook


def test_calendar_name_is_profile_plus_translated_workouts():
    assert 'f"{profile} {tr(self.language, \'workouts\')}"' in CALENDAR
