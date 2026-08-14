"""Exclusive physical-sensor workout ownership regressions."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "custom_components/fitness/live/runtime.py"
RUNTIME = RUNTIME_PATH.read_text(encoding="utf-8")
CONFIG = (ROOT / "custom_components/fitness/config_flow.py").read_text(encoding="utf-8")


def _method(name: str):
    tree = ast.parse(RUNTIME)
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "LiveRuntime"
    )
    node = next(
        item for item in cls.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict = {}
    exec(compile(module, str(RUNTIME_PATH), "exec"), namespace)
    return namespace[name]


class Harness:
    _profile_is_live_session = _method("_profile_is_live_session")
    _profile_is_using_live_runtime = _method("_profile_is_using_live_runtime")
    _global_workout_epoch_active = _method("_global_workout_epoch_active")
    sensor_workout_owner = _method("sensor_workout_owner")
    profile_claimed_sensor_ids = _method("profile_claimed_sensor_ids")
    _claim_sensor_for_workout = _method("_claim_sensor_for_workout")
    _clear_workout_sensor_locks_if_idle = _method("_clear_workout_sensor_locks_if_idle")

    def __init__(self):
        self.profile_entries = {
            "chris": SimpleNamespace(entry_id="chris"),
            "profile_b": SimpleNamespace(entry_id="profile_b"),
        }
        self.managers = {
            "chris": SimpleNamespace(session_armed=False, session_active=False, recovery_active=False),
            "profile_b": SimpleNamespace(session_armed=False, session_active=False, recovery_active=False),
        }
        self.assignments = {
            "chris": ["sensor:x", "sensor:y"],
            "profile_b": ["sensor:x", "sensor:a"],
        }
        self._sensor_workout_owner = {}
        self._profile_claimed_sensors = {}
        self._profile_session_order = {}
        self._session_order_counter = 0
        self._sensor_workout_capture_baseline = {}
        self._sensor_workout_capture_override = {}
        self.sensors = {}
        self.notifications = []

    def _manager_for_profile(self, entry_id):
        return self.managers.get(entry_id)

    def selected_sensor_ids(self, entry):
        return list(self.assignments.get(entry.entry_id, []))

    def resolve_sensor_id(self, sensor_id):
        return str(sensor_id)

    def sensor_is_accepted(self, sensor_id):
        return str(sensor_id) in {"sensor:x", "sensor:y", "sensor:a"}

    def _ensure_workout_capture_baseline(self, sensor_id):
        self._sensor_workout_capture_baseline.setdefault(str(sensor_id), {})

    def _set_workout_capture_override(self, sensor_id, transport, enabled):
        self._sensor_workout_capture_override.setdefault(str(sensor_id), {})[str(transport)] = bool(enabled)

    def _restore_workout_capture_overrides(self):
        self._sensor_workout_capture_override.clear()
        self._sensor_workout_capture_baseline.clear()

    def _notify_values_throttled(self, changes):
        self.notifications.append(set(changes))


def test_first_started_profile_exclusively_claims_shared_sensor():
    h = Harness()
    h.managers["chris"].session_armed = True
    h._profile_session_order["chris"] = 1
    h.managers["profile_b"].session_armed = True
    h._profile_session_order["profile_b"] = 2

    assert h._claim_sensor_for_workout("sensor:x") == "chris"
    assert h.sensor_workout_owner("sensor:x") == "chris"
    assert h.profile_claimed_sensor_ids("chris") == {"sensor:x"}
    assert h.profile_claimed_sensor_ids("profile_b") == set()


def test_lock_survives_owner_stop_while_other_profile_continues():
    h = Harness()
    h.managers["chris"].session_active = True
    h.managers["profile_b"].session_active = True
    h._profile_session_order.update(chris=1, profile_b=2)
    assert h._claim_sensor_for_workout("sensor:x") == "chris"

    # Chris stops but B's overlapping activity remains active.
    h.managers["chris"].session_active = False
    assert h._clear_workout_sensor_locks_if_idle() is False
    assert h.sensor_workout_owner("sensor:x") == "chris"
    # Re-claim attempts cannot transfer the still-worn sensor to B.
    assert h._claim_sensor_for_workout("sensor:x") == "chris"

    # Only after every overlapping Fitness session is finished may it unlock.
    h.managers["profile_b"].session_active = False
    assert h._clear_workout_sensor_locks_if_idle() is True
    assert h.sensor_workout_owner("sensor:x") is None


def test_recovery_also_keeps_global_lock_epoch_open():
    h = Harness()
    h.managers["chris"].session_active = True
    h._profile_session_order["chris"] = 1
    assert h._claim_sensor_for_workout("sensor:x") == "chris"

    h.managers["chris"].session_active = False
    h.managers["chris"].recovery_active = True
    assert h._clear_workout_sensor_locks_if_idle() is False
    assert h.sensor_workout_owner("sensor:x") == "chris"

    h.managers["chris"].recovery_active = False
    assert h._clear_workout_sensor_locks_if_idle() is True


def test_different_free_sensor_can_start_second_profile():
    h = Harness()
    h.managers["chris"].session_active = True
    h._profile_session_order["chris"] = 1
    h.managers["profile_b"].session_armed = True
    h._profile_session_order["profile_b"] = 2

    assert h._claim_sensor_for_workout("sensor:x") == "chris"
    assert h._claim_sensor_for_workout("sensor:a") == "profile_b"
    assert h.sensor_workout_owner("sensor:x") == "chris"
    assert h.sensor_workout_owner("sensor:a") == "profile_b"


def test_runtime_routes_packets_only_to_exclusive_owner():
    assert "owner = self._claim_sensor_for_workout(sensor_id)" in RUNTIME
    assert "entry = self.profile_entries.get(owner)" in RUNTIME
    publish = RUNTIME.split("    def publish(", 1)[1].split("    def live_values(", 1)[0]
    assert "for entry in tuple(self.profile_entries.values())" not in publish
    assert "self.measurements.setdefault(owner, {})" in publish
    assert "self.measurement_sources.setdefault(owner, {})" in publish
    assert "intentionally discarded rather than handed over mid-session" in publish


def test_timer_waits_for_real_measurement_not_assignment_or_claim():
    prepare = RUNTIME.split("    async def async_prepare_session", 1)[1].split(
        "    async def async_manual_gatt_connect", 1
    )[0]
    assert "self.measurements.pop(entry.entry_id, None)" in prepare
    assert 'or "waiting_for_free_sensor"' in prepare
    assert "Do not pre-lock every recently seen assigned sensor" in prepare
    # Runtime never starts the manager's timer itself; manager does that only
    # after live_values contains a usable measurement.
    assert "_begin_session_from_live_data" not in prepare


def test_transport_handover_cannot_change_physical_workout_owner():
    reconcile = RUNTIME.split("    async def _reconcile_profile_transports", 1)[1].split(
        "    def _start_profile_handover_monitor", 1
    )[0]
    assert "owned_ids = self.profile_claimed_sensor_ids(entry.entry_id)" in reconcile
    assert "for sensor_id in sorted(owned_ids):" in reconcile
    assert "self.sensors_for_profile(entry)" not in reconcile


def test_sensor_centric_reassignment_exists_after_setup():
    assert 'menu_options=["sensor_assignments"]' in CONFIG
    assert "async def async_step_sensor_assignments" in CONFIG
    assert "async def async_step_sensor_assignment" in CONFIG
    assignment = CONFIG.split("async def async_step_sensor_assignment", 1)[1].split(
        "async def async_step_profile", 1
    )[0]
    assert '"fitness_profile_ids"' in assignment
    assert "multiple=True" in assignment
    assert "CONF_LIVE_SENSOR_IDS" in assignment
    # Removing all profiles is deliberately allowed during later reassignment.
    assert "if not selected_profiles" not in assignment
