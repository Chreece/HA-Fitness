"""Universal health catalog, direct history fidelity and FIT map regressions."""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"


def _pure(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, FIT / rel)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_health_catalog_normalizes_legacy_names():
    catalog = _pure("fitness_test_health_catalog", "health_catalog.py")
    assert catalog.canonical_metric_key("max_hr") == "max_heart_rate"
    assert catalog.canonical_metric_key("min_hr") == "min_heart_rate"
    assert catalog.canonical_metric_key("activity_minutes") == "active_minutes"
    assert catalog.metric_spec("skin_temperature_min").category == "temperature"
    assert catalog.metric_spec("battery").category == "device_state"
    assert {"measurement_context", "wear_state", "charging"} <= catalog.DEVICE_CONTEXT_FIELDS


def test_ultrahuman_preserves_measurement_context_and_device_state():
    protocol = _pure("fitness_test_uh_protocol_v2", "device_adapters/ultrahuman/protocol.py")
    assert protocol.measurement_context(1) == "normal"
    assert protocol.measurement_context(5) == "exercise"
    assert protocol.measurement_context(6) == "breathing"
    assert protocol.measurement_context(100) == "not_on_finger"
    state = protocol.parse_device_state(bytes.fromhex("4c4c2900000317"))
    assert state.battery == 76
    assert state.charging is True
    assert state.device_temperature == 23.0


def test_fit_adapters_keep_bounded_gps_track_for_internal_map():
    for rel in ("device_adapters/garmin/fit.py", "device_adapters/cycplus_m1.py"):
        source = (FIT / rel).read_text(encoding="utf-8")
        assert "def _gps_points(" in source
        assert '"gps_points": _gps_points(relevant)' in source
    dashboard = (FIT / "dashboard.py").read_text(encoding="utf-8")
    frontend = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
    assert '"source": "fitness_workout"' in dashboard
    assert 'Object.prototype.hasOwnProperty.call(this._resolved, "value")' in frontend


def test_garmin_user_action_signal_contains_clean_pairing_steps():
    source = (FIT / "device_adapters" / "garmin" / "coordinator.py").read_text(encoding="utf-8")
    assert '"fitness_device_user_action_required"' in source
    assert '"action": "pairing_required"' in source
    assert '"fields": []' in source
    assert "Keep the Garmin paired with your phone." in source
