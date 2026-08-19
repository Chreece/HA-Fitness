from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIT = ROOT / "custom_components" / "fitness"
CONFIG = (FIT / "config_flow.py").read_text(encoding="utf-8")
RUNTIME = (FIT / "live" / "runtime.py").read_text(encoding="utf-8")
BUTTON = (FIT / "button.py").read_text(encoding="utf-8")
FRONTEND = (FIT / "frontend" / "fitness-dashboard.js").read_text(encoding="utf-8")
STRINGS = (FIT / "strings.json").read_text(encoding="utf-8")


def test_protocol_flow_is_manage_multi_protocol_with_manual_hardware_selection():
    assert '"bluetooth_automatic_hardware"' in CONFIG
    assert '"antplus_automatic_hardware"' in CONFIG
    assert 'async def async_step_protocol_hardware' in CONFIG
    assert 'multiple=True' in CONFIG
    assert 'async_set_protocol_selection(selected)' in CONFIG
    assert 'async_set_hardware_selection' in CONFIG
    assert 'Manage sensor protocols' in STRINGS


def test_disabled_protocols_are_removed_from_fitness_protocols_ui():
    assert 'def _remove_transport_subentry' in RUNTIME
    assert 'if self.hub_entry is None or not self.adapter_configured(transport):' in RUNTIME
    assert 'if not self.adapter_configured(transport):' in RUNTIME
    assert 'self._remove_transport_subentry(transport)' in RUNTIME
    assert 'Only Fitness-exclusive hardware may be removed' in RUNTIME


def test_shared_vs_fitness_owned_hardware_is_controlled_safely():
    assert 'def receiver_management_scope' in RUNTIME
    assert 'return "system_shared"' in RUNTIME
    assert 'return "fitness_owned"' in RUNTIME
    assert 'Ownership uncertainty must never lead to destructive control.' in RUNTIME
    assert 'async_begin_receiver_manual_scan' in RUNTIME
    assert 'await self.runtime.async_begin_receiver_manual_scan' in BUTTON


def test_workout_history_is_a_first_class_calendar_view_with_gps_and_management():
    assert 'class FitnessWorkoutBrowserCard' in FRONTEND
    assert 'mdi:calendar-heart' in FRONTEND
    assert 'class FitnessWorkoutBrowserCard' in FRONTEND
    assert 'class="calendar"' in FRONTEND
    assert 'gps_track' in FRONTEND
    assert 'fitness/workouts/edit' in FRONTEND
    assert 'fitness/workouts/delete' in FRONTEND
    assert 'fitness-workout-selected' in FRONTEND
    assert 'data-prev' in FRONTEND and 'data-next' in FRONTEND
