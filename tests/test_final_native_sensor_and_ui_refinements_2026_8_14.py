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


def test_capture_controls_are_per_physical_sensor_transport():
    assert "class SensorTransportStartCaptureButton" in BUTTON
    assert "class SensorTransportStopCaptureButton" in BUTTON
    assert 'for transport in ("antplus", "bluetooth")' in BUTTON
    assert 'if transport not in sensor.endpoints:' in BUTTON
    assert 'AdapterStartCaptureButton(runtime, "bluetooth")' not in BUTTON
    assert "sensor_transport_capture_enabled" in RUNTIME
    assert "async_set_sensor_transport_capture" in RUNTIME
    assert 'stored.get("sensor_transport_capture")' in RUNTIME


def test_capture_gates_are_respected_by_live_transport_selection_and_publish():
    assert 'not self.sensor_transport_capture_enabled(sensor.sensor_id, "antplus")' in RUNTIME
    assert 'self.sensor_transport_capture_enabled(sensor.sensor_id, "bluetooth")' in RUNTIME
    assert "capture_enabled = self.sensor_transport_capture_enabled(sensor_id, transport)" in RUNTIME


def test_live_profile_surface_requires_an_accepted_assigned_sensor():
    assert "def profile_has_assigned_live_sensor" in RUNTIME
    assert "runtime.profile_has_assigned_live_sensor(entry)" in SENSOR
    assert "runtime.profile_has_assigned_live_sensor(entry)" in BUTTON
    assert "runtime.profile_has_assigned_live_sensor(entry)" in SELECT
    assert "self.profile_has_assigned_live_sensor(entry)" in RUNTIME


def test_fitness_sleep_score_is_marked_as_calculated_and_non_medical():
    assert "def fitness_derived_sleep_score" in SLEEP
    assert 'merged.field_sources["score"] = "fitness_calculated"' in SLEEP
    assert 'attrs["calculated_by_fitness"] = True' in SENSOR
    assert 'attrs["medical_interpretation"] = False' in SENSOR
    assert 'fitness_sleep_score' in DASHBOARD


def test_recovery_ui_formats_total_minutes_and_relative_ready_time():
    assert 'l.recovery_from_last_workout || "Time to recover from last workout"' in FRONTEND
    assert 'l.total_recovery || "Total recovery"' in FRONTEND
    assert 'remaining < 1 ? `~${Math.max(1, Math.round(remaining * 60))} min`' in FRONTEND
    assert 'new Intl.RelativeTimeFormat(language, {numeric:"auto"})' in FRONTEND
    assert 'const recoveryIcon = fullyRecovered ? "mdi:check-circle"' in FRONTEND


def test_empty_frontend_sections_hide_instead_of_rendering_placeholders():
    assert 'if (points.length < 2) {\n      this.shadowRoot.innerHTML = "";' in FRONTEND
    assert 'if (!rows) {\n      this.shadowRoot.innerHTML = "";' in FRONTEND
    assert "if (!hasLoadData && !hasAdaptationData)" in FRONTEND
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
    assert 'const FITNESS_DASHBOARD_VERSION = "2026.8.11.1";' in FRONTEND
    assert '_RESOURCE_URL = f"{_RESOURCE_NAMESPACE}?v=2026.8.11.1"' in DASHBOARD


def test_ant_decoder_backend_diagnostics_have_no_missing_profile_support_module():
    adapters = (FIT / "live" / "antplus_core" / "decoder_adapters.py").read_text(encoding="utf-8")
    decoder = (FIT / "live" / "antplus_core" / "decoder.py").read_text(encoding="utf-8")
    assert "from .profile_support" not in adapters
    assert "from .decoder import native_profile_types" in adapters
    assert "def native_profile_types()" in decoder
