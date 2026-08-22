from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
FLOW = (FIT / "config_flow.py").read_text(encoding="utf-8")
BUTTON = (FIT / "button.py").read_text(encoding="utf-8")
DASH = (FIT / "dashboard.py").read_text(encoding="utf-8")
FRONT = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
MANAGER = (FIT / "manager.py").read_text(encoding="utf-8")
COORD = (FIT / "device_adapters" / "garmin" / "coordinator.py").read_text(encoding="utf-8")


def test_phone_mediated_gadgetbridge_adapter_is_removed():
    assert not (FIT / "providers" / "workout_adapters" / "gadgetbridge.py").exists()
    assert "CONF_GADGETBRIDGE" not in FLOW
    assert "gadgetbridge_fit_export" not in (FIT / "const.py").read_text(encoding="utf-8")


def test_first_install_offers_protocol_manager_or_user_without_rewriting_profile_flow():
    assert "async_step_first_install" in FLOW
    assert 'menu_options=["add_protocol", "add_user"]' in FLOW
    assert "async_step_manage_protocols" in FLOW
    assert "async_step_add_protocol" in FLOW  # backward-compatible alias
    assert "async_step_add_user" in FLOW
    assert '"initial_protocols": sorted(selected)' in FLOW
    assert '"initial_hardware": {' in FLOW
    assert 'menu_options=["discover_protocol_hardware", "select_protocol_hardware"]' in FLOW
    assert 'runtime.transport_hardware_choices(transport)' in FLOW


def test_adapter_scan_now_is_bounded_and_transport_generic():
    assert "class PhysicalAdapterScanNowButton" in BUTTON
    assert "asyncio.timeout(15.0)" in BUTTON
    assert "async_refresh_discovery" in BUTTON
    assert "async_refresh_local" in BUTTON
    block = BUTTON.split("class PhysicalAdapterScanNowButton", 1)[1].split("class BaseFitnessButton", 1)[0]
    assert "Garmin" not in block and "CYCPLUS" not in block and "Forerunner" not in block


def test_dashboard_features_are_presentation_only_and_entity_backed():
    assert "async_step_features" in FLOW
    assert "CONF_DASHBOARD_MODULES" in FLOW
    assert "CONF_DASHBOARD_RSS_ENTITY_IDS" in FLOW
    assert "CONF_DASHBOARD_WEATHER_ENTITY_ID" in FLOW
    assert "aiohttp" not in FLOW
    assert "dashboard_preferences" in DASH
    assert 'modules.has("weather")' in FRONT
    assert 'type:"media-control"' in FRONT


def test_workout_browser_has_bounded_list_batch_delete_and_explicit_empty_confirmation():
    assert '"fitness/workouts/list"' in DASH
    assert 'vol.Range(min=1, max=500)' in DASH
    assert '"fitness/workouts/delete"' in DASH
    assert 'vol.Length(min=1, max=100)' in DASH
    assert '"fitness/workouts/empty"' in DASH
    assert "confirmation_required" in DASH
    assert "async_delete_calendar_workouts" in MANAGER
    assert "async_empty_workout_history" in MANAGER
    assert "class FitnessWorkoutBrowserCard" in FRONT


def test_body_composition_and_ai_coach_add_no_new_polling_loops():
    assert '"fitness/body_composition"' in DASH
    assert "daily[:90]" in DASH
    assert "class FitnessBodyCompositionCard" in FRONT
    assert "class FitnessTrainingAiCoachCard" in FRONT
    coach = FRONT.split("class FitnessTrainingAiCoachCard", 1)[1].split("class FitnessDashboardStrategy", 1)[0]
    assert "callWS" not in coach
    assert "setInterval" not in coach


def test_garmin_partial_archive_batches_continue_without_restart_but_back_off():
    assert "BATCH_CONTINUE_DELAY = 5 * 60.0" in COORD
    assert "PARTIAL_BATCH_RETRY_DELAY = 5 * 60.0" in COORD
    assert "MAX_PARTIAL_BATCH_RETRIES = 3" in COORD
    assert "recent_partial" in COORD
