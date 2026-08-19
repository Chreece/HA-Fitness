from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components/fitness"
RUNTIME = (FIT / "live/runtime.py").read_text(encoding="utf-8")
JS = (FIT / "frontend/fitness-dashboard.js").read_text(encoding="utf-8")
DASH = (FIT / "dashboard.py").read_text(encoding="utf-8")
CATALOG = json.loads((FIT / "live/device_catalog.json").read_text(encoding="utf-8"))


def _identity_module():
    spec = importlib.util.spec_from_file_location(
        "fitness_device_identity_test", FIT / "live/device_identity.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sensor(name: str, transport: str, caps: set[str], metadata: dict):
    endpoint = SimpleNamespace(metadata=metadata)
    return SimpleNamespace(name=name, capabilities=caps, endpoints={transport: endpoint})


def test_catalog_correlation_treats_required_capabilities_as_subset():
    identity = _identity_module()
    bt = _sensor(
        "Forerunner",
        "bluetooth",
        {"heart_rate", "battery"},
        {"advertised_name": "Any name", "manufacturer_data_ids": [135]},
    )
    match = identity.catalog_transport_correlation(bt)
    assert match and match["rule_id"] == "garmin_wearable_hr_broadcast"
    assert match["role"] == "bluetooth"


def test_catalog_has_data_driven_stryd_bt_ant_correlation():
    identity = _identity_module()
    rule = next(
        item
        for item in CATALOG["transport_correlation_rules"]
        if item["id"] == "stryd_running_power_broadcast"
    )
    assert rule["roles"]["bluetooth"]["manufacturer_data_id"] == 43690
    assert set(rule["roles"]["antplus"]["profiles_any"]) >= {11, 124}

    bt = _sensor(
        "Stryd",
        "bluetooth",
        {"battery"},
        {"advertised_name": "Stryd", "manufacturer_data_ids": [43690]},
    )
    ant = _sensor(
        "Power Meter",
        "antplus",
        {"power"},
        {"manufacturer_id": 95, "profiles": [11]},
    )
    assert identity.catalog_transport_correlation(bt)["rule_id"] == rule["id"]
    assert identity.catalog_transport_correlation(ant)["rule_id"] == rule["id"]


def test_late_provisional_merge_collapses_stale_ha_discovery_flows():
    merge = RUNTIME.split("def _merge_physical_sensors", 1)[1].split(
        "def _schedule_merged_registry_cleanup", 1
    )[0]
    helper = RUNTIME.split(
        "def _collapse_provisional_discovery_flows_after_merge", 1
    )[1].split("def _schedule_merged_registry_cleanup", 1)[0]
    assert "provisional_merge = not a_was_accepted and not b_was_accepted" in merge
    assert "_collapse_provisional_discovery_flows_after_merge" in merge
    assert "manager.async_abort(flow_id)" in helper
    assert "include_uninitialized=True" in helper
    assert "self.hass.loop.call_soon(self._schedule_sensor_discovery, canonical_id)" in helper


def test_vo2_history_has_date_axis_scroll_zoom_and_pan_controls():
    assert 'class="history-scroll"' in JS
    assert 'class="history-x-axis"' in JS
    assert 'class="history-zoom-in"' in JS
    assert 'class="history-zoom-out"' in JS
    assert 'class="history-zoom-reset"' in JS
    assert 'event.ctrlKey || event.metaKey' in JS
    assert 'scroller.scrollLeft' in JS
    assert 'this._vo2HistoryZoom' in JS
    assert 'Intl.DateTimeFormat(locale, {month:"short", day:"numeric"})' in JS


def test_new_visible_vo2_and_strength_ui_text_is_profile_translatable():
    required = {
        "difference", "history", "measurements", "actual", "trend", "predicted",
        "below_zoom", "above_zoom", "zoom_in", "zoom_out", "reset_zoom", "pan_hint",
        "workout", "exercise", "exercises", "sets", "reps", "volume",
        "strength_progression", "total_volume", "estimated_1rm_method", "no_current_data",
        "no_live_data", "awake", "light_sleep", "deep_sleep", "rem_sleep",
        "current_marker", "predicted_marker", "date_axis",
    }
    for key in required:
        assert f'"{key}"' in DASH
    assert '_DASHBOARD_UI_TEXT' in DASH
    assert "l.measurements" in JS
    assert "l.actual" in JS
    assert "l.predicted" in JS
    assert "l.zoom_in" in JS
    assert "l.strength_progression" in JS


def test_frontend_resource_revision_bumped():
    assert 'unreleased-89' in JS
    assert 'unreleased-89' in DASH



def test_every_profile_label_fallback_used_by_frontend_has_dashboard_translation_key():
    import re
    keys = set(re.findall(r"\\bl\\.([A-Za-z0-9_]+)\\s*\\|\\|\\s*[\"']", JS))
    missing = sorted(key for key in keys if f'"{key}"' not in DASH)
    assert not missing, f"Frontend labels missing from dashboard translation map: {missing}"
