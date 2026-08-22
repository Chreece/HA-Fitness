"""Final 2026.8.11 native-sensor/UI refinement contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
BUTTON = (FIT / "button.py").read_text(encoding="utf-8")
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
SENSOR = (FIT / "sensor.py").read_text(encoding="utf-8")
SELECT = (FIT / "select.py").read_text(encoding="utf-8")
SLEEP = (FIT / "providers" / "sleep.py").read_text(encoding="utf-8")
DASHBOARD = (FIT / "dashboard.py").read_text(encoding="utf-8")
FRONTEND = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")


def test_complete_identity_dependencies_are_shipped():
    assert (FIT / "live" / "device_identity.py").is_file()
    assert (FIT / "live" / "device_catalog.json").is_file()
    assert (FIT / "event.py").is_file()


def test_capture_and_manual_gatt_controls_are_removed_in_favor_of_adapter_switch():
    assert "class SensorTransportStartCaptureButton" not in BUTTON
    assert "class SensorTransportStopCaptureButton" not in BUTTON
    assert "AntReceiverStartCaptureButton" not in BUTTON
    assert "AntReceiverStopCaptureButton" not in BUTTON
    assert "SensorGattConnectButton" not in BUTTON
    assert "SensorGattDisconnectButton" not in BUTTON
    assert "async_set_sensor_transport_capture" not in RUNTIME
    assert "async_manual_gatt_connect" not in RUNTIME
    assert "async_manual_gatt_disconnect" not in RUNTIME


def test_live_transport_selection_uses_adapter_state_only():
    choose = RUNTIME.split("def choose_transport", 1)[1].split("async def _claim_transport", 1)[0]
    assert 'self.adapter_enabled("antplus")' in choose
    assert 'self.adapter_enabled("bluetooth")' in choose
    assert "_sensor_workout_capture" not in choose


def test_live_profile_calculation_surface_and_device_are_stable():
    assert "def profile_has_assigned_live_sensor" in RUNTIME
    assert "manager.remember_materialized_sensors(live_keys, persist=True)" in SENSOR
    assert "runtime.profile_has_assigned_live_sensor(entry)" not in SENSOR
    assert "entities = [\n        StartWorkoutButton" in BUTTON
    assert "runtime.profile_has_assigned_live_sensor(entry)" not in SELECT
    assert "def ensure_profile_live_registry" in RUNTIME
    ensure = RUNTIME[RUNTIME.index("def ensure_profile_live_registry"):RUNTIME.index("def _start_presence_monitor")]
    assert "profile_has_assigned_live_sensor" not in ensure
    assert "async_remove_device" not in ensure


def test_fitness_sleep_score_is_marked_as_calculated_and_non_medical():
    assert "def fitness_derived_sleep_score" in SLEEP
    assert 'merged.field_sources["score"] = "fitness_calculated"' in SLEEP
    assert 'attrs["calculated_by_fitness"] = True' in SENSOR
    assert 'attrs["medical_interpretation"] = False' in SENSOR
    assert 'fitness_sleep_score' in DASHBOARD


def test_recovery_ui_uses_compact_progress_detail_and_relative_ready_time():
    assert "l.recovery_done_short" in FRONTEND
    assert "l.ready_at_compact" in FRONTEND
    assert "l.remaining_compact" in FRONTEND
    assert 'Math.round(remaining * 60)' in FRONTEND
    assert 'new Intl.RelativeTimeFormat(language, {numeric:"auto"})' in FRONTEND
    assert 'class="next-main"' not in FRONTEND


def test_empty_frontend_sections_hide_instead_of_rendering_placeholders():
    assert 'if (points.length < 2) {\n      this.shadowRoot.innerHTML = "";' in FRONTEND
    assert 'if (!rows) {\n      this.shadowRoot.innerHTML = "";' in FRONTEND
    assert "if (!hasLoadData)" in FRONTEND
    assert "if (!children.length)" in FRONTEND


def test_hr_baseline_exposes_actual_baseline_and_current_values():
    assert 'attrs["current_average_hr_bpm"]' in SENSOR
    assert 'attrs["personal_baseline_average_hr_bpm"]' in SENSOR
    assert 'attrs["absolute_deviation_bpm"]' in SENSOR
    assert 'state.attributes?.personal_baseline_average_hr_bpm' in FRONTEND
    assert 'state.attributes?.current_average_hr_bpm' in FRONTEND
    assert 'distance <= 2 ? "#43a047"' in FRONTEND
    assert 'distance <= 5 ? "#f9a825"' in FRONTEND
    assert 'distance <= 8 ? "#ef6c00"' in FRONTEND


def test_frontend_cache_revision_is_current_and_single_module():
    assert 'const FITNESS_DASHBOARD_VERSION = "unreleased-138";' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=unreleased-138"' in DASHBOARD


def test_ant_decoder_backend_diagnostics_have_no_missing_profile_support_module():
    adapters = (FIT / "live" / "antplus_core" / "decoder_adapters.py").read_text(encoding="utf-8")
    decoder = (FIT / "live" / "antplus_core" / "decoder.py").read_text(encoding="utf-8")
    assert "from .profile_support" not in adapters
    assert "from .decoder import native_profile_types" in adapters
    assert "def native_profile_types()" in decoder
