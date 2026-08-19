from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
FLOW = (FIT / "config_flow.py").read_text(encoding="utf-8")
DASH = (FIT / "dashboard.py").read_text(encoding="utf-8")
ACCESS = (FIT / "access_control.py").read_text(encoding="utf-8")
FRONT = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")


def test_top_level_protocol_flow_is_real_multi_manager_with_manual_discovery():
    assert 'menu_options=["manage_protocols", "add_user"]' in FLOW
    assert 'async def async_step_manage_protocols' in FLOW
    assert '"bluetooth_automatic_hardware"' in FLOW
    assert '"antplus_automatic_hardware"' in FLOW
    assert 'menu_options=["discover_protocol_hardware", "select_protocol_hardware"]' in FLOW
    assert 'runtime.transport_hardware_choices(transport)' in FLOW
    assert '"initial_protocols": sorted(selected)' in FLOW


def test_devices_hub_is_never_a_person_profile():
    assert 'entry.data.get("entry_type") not in {"live_hub", "devices_hub"}' in ACCESS
    assert 'entry.data.get("entry_type") in {"live_hub", "devices_hub"}' in DASH
    assert 'entry.data.get("entry_type") not in {"live_hub", "devices_hub"}' in DASH


def test_workout_history_is_addable_and_card_picker_preserves_live_preview():
    assert 'class FitnessWorkoutBrowserCard' in FRONT
    assert 'fitness-workout-selected' in FRONT
    assert 'card-picker-live-preview' in FRONT
    assert 'card-picker-preview-backdrop' in FRONT
    assert 'pointer-events:none' in FRONT
    assert 'pointer-events:auto' in FRONT
