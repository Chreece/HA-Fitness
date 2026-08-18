"""Smart workout device setup, ownership and merge safety regressions."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
FLOW = (FIT / "config_flow.py").read_text(encoding="utf-8")
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
SMART = (FIT / "smart_workout_devices.py").read_text(encoding="utf-8")
GARMIN = (FIT / "device_adapters" / "garmin" / "coordinator.py").read_text(encoding="utf-8")
CYCPLUS = (FIT / "live" / "cycplus_m1.py").read_text(encoding="utf-8")
BT = (FIT / "live" / "bluetooth.py").read_text(encoding="utf-8")


def _method(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(name)


def test_vendor_specific_menu_is_replaced_by_generic_smart_device_control_plane():
    init = _method(FLOW, "async_step_init")
    assert '"smart_workout_devices"' in init
    assert '"garmin_local_guide"' not in init
    assert "async_step_smart_workout_devices" in FLOW
    assert "async_step_garmin_local_guide" in FLOW  # compatibility alias only
    assert (ROOT / "docs" / "SMART_WORKOUT_DEVICES.md").is_file()


def test_smart_device_setup_scan_and_selector_are_strictly_bounded():
    refresh = _method(FLOW, "_async_refresh_smart_workout_discovery")
    choices = _method(FLOW, "_smart_workout_choices")
    assert "asyncio.timeout(15.0)" in refresh
    assert "async_refresh_discovery" in refresh
    assert "MAX_SMART_WORKOUT_DEVICE_CHOICES" in choices
    assert "MAX_SMART_DEVICE_MODEL_LABEL" in FLOW
    assert "vol.Length(max=MAX_SMART_DEVICE_MODEL_LABEL)" in FLOW
    # The UI reuses the Bluetooth provider's bounded one-shot scan. It must never
    # establish a GATT client itself.
    assert "establish_connection" not in refresh
    assert "BleakClient" not in FLOW


def test_model_and_device_type_are_display_metadata_not_protocol_routing():
    configure = _method(RUNTIME, "configure_smart_workout_device")
    assert 'sensor.metadata["smart_device_type"]' in configure
    assert 'sensor.metadata["smart_device_model_label"]' in configure
    for forbidden in ("Forerunner", "Fenix", "Fēnix", "Venu", "965"):
        assert forbidden.lower() not in (
            SMART + GARMIN + (FIT / "device_archives.py").read_text(encoding="utf-8")
        ).lower()
    assert "transport_candidates_from_client" in GARMIN


def test_verified_archive_marker_makes_blank_name_device_discoverable():
    ready = _method(RUNTIME, "_sensor_discovery_ready")
    assert 'bluetooth.metadata.get("archive_adapter")' in ready
    assert "return True" in ready


def test_one_physical_device_can_gain_archive_capability_without_duplicate_object():
    register = _method(RUNTIME, "register_transport_sensor")
    match = _method(RUNTIME, "_match_sensor")
    assert "known_sensor_id = self.endpoint_aliases.get(endpoint_id)" in register
    assert "sensor.capabilities.update(capabilities)" in register
    assert "current = self.sensors.get" in match
    assert "return current" in match
    # Garmin archive discovery goes through the exact same physical Bluetooth
    # endpoint registration path as live HR/etc., rather than making a second
    # Garmin-specific device object.
    assert "register_transport_sensor" in BT
    assert "device_archives.match_bluetooth" in BT


def test_smart_archive_owner_is_single_profile_while_live_assignment_stays_many_to_many():
    owner = _method(RUNTIME, "smart_device_owner_profile_id")
    archive_targets = _method(RUNTIME, "sensor_archive_profile_ids")
    assigned = _method(RUNTIME, "sensor_assigned_profile_ids")
    assert 'smart_device_owner_profile_id' in owner
    assert "return [owner]" in archive_targets
    assert "sensor_assigned_profile_ids" in archive_targets  # one-profile fallback
    assert "len(assigned) == 1" in archive_targets
    assert "for entry in self.profile_entries.values()" in assigned
    assert "sensor_archive_profile_ids(sensor_id)" in GARMIN
    assert "sensor_archive_profile_ids(sensor_id)" in CYCPLUS


def test_owner_metadata_survives_physical_sensor_merge_without_silent_reassignment():
    merge = _method(RUNTIME, "_merge_physical_sensors")
    assert "primary.metadata.update" in merge
    assert "secondary.metadata.items()" in merge
    assert "primary_owner" in merge and "secondary_owner" in merge
    assert 'merged_metadata.pop("smart_device_owner_profile_id", None)' in merge
    assert 'smart_device_owner_conflict' in merge
    configure = _method(RUNTIME, "configure_smart_workout_device")
    assert 'sensor.metadata.pop("smart_device_owner_conflict", None)' in configure


def test_smart_device_flow_assigns_current_profile_without_reloading_hot_path():
    setup = _method(FLOW, "async_step_smart_workout_device_setup")
    assert "self.config_entry.entry_id" in setup
    assert "runtime.configure_smart_workout_device" in setup
    assert "runtime.mark_sensor_accepted" in setup
    assert "runtime.suppress_entry_reload_once" in setup
    assert "asyncio.sleep(0.5)" in setup
    assert "async_create_background_task" in setup


def test_manual_vendor_guide_is_model_agnostic_and_currently_exposes_garmin():
    assert 'vendor_id="garmin"' in SMART
    assert "SUPPORTED_SETUP_VENDORS" in SMART
    guide = _method(FLOW, "async_step_smart_workout_vendor_guide")
    assert "_async_refresh_smart_workout_discovery" in guide
    assert "smart_workout_vendor(sensor) == vendor.vendor_id" in guide
    assert "model" in guide  # display-only placeholder


def test_automatic_discovery_requires_one_archive_owner_but_can_share_live_later():
    assign = _method(FLOW, "async_step_assign_live_sensor")
    assert "smart_archive = is_smart_workout_sensor(sensor)" in assign
    assert "len(selected_profiles) > 1" in assign
    assert 'errors={"base": "select_smart_device_owner"}' in assign
    assert "runtime.configure_smart_workout_device" in assign
    assert "owner_profile_id=owner_profile_id" in assign
