"""Cross-transport ownership safety regressions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text(encoding="utf-8")
ENTITIES = (ROOT / "custom_components/fitness/live/ha_entities.py").read_text(encoding="utf-8")


def test_physical_identity_merge_migrates_workout_lock_and_provenance():
    assert "def _migrate_workout_state_for_sensor_merge(" in RUNTIME
    merge = RUNTIME.split("def _migrate_workout_state_for_sensor_merge", 1)[1].split(
        "def _merge_physical_sensors", 1
    )[0]
    assert "owner_primary" in merge
    assert "owner_secondary" in merge
    assert "self._sensor_workout_owner[primary_id] = winner" in merge
    assert "self._profile_claimed_sensors" in merge
    assert "self._profile_sensor_transport" in merge
    assert "self.measurement_sources.values()" in merge
    assert "sources[metric] = primary_id" in merge


def test_conflicting_premerge_owners_choose_oldest_session():
    merge = RUNTIME.split("def _migrate_workout_state_for_sensor_merge", 1)[1].split(
        "def _merge_physical_sensors", 1
    )[0]
    assert "self._profile_session_order.get(entry_id, 10**12)" in merge
    assert "winner = min(" in merge


def test_ant_takeover_keeps_old_transport_until_disconnect_reconcile():
    publish = RUNTIME.split("    def publish(", 1)[1].split("    def live_values(", 1)[0]
    assert "do NOT overwrite the old chosen transport yet" in publish
    assert "self._schedule_sensor_claim_reconcile(sensor_id)" in publish
    handover = publish.split("if desired is not None and desired != chosen:", 1)[1].split(
        "elif chosen is not None", 1
    )[0]
    assert "chosen_map[sensor_id] = desired" not in handover


def test_gatt_reconcile_is_exclusive_and_connection_failures_release_claims():
    reconcile = RUNTIME.split("async def _reconcile_profile_transports", 1)[1].split(
        "def _start_profile_handover_monitor", 1
    )[0]
    assert "owned_ids = self.profile_claimed_sensor_ids(entry.entry_id)" in reconcile
    assert "await self._release_transport(entry.entry_id, \"bluetooth\")" in reconcile
    assert "Unable to connect Fitness BLE GATT sensor" in reconcile


def test_failed_capture_start_cannot_leave_phantom_transport_claim():
    claim = RUNTIME.split("async def _claim_transport", 1)[1].split(
        "async def _release_transport", 1
    )[0]
    assert "except Exception:" in claim
    assert "claims.discard(entry_id)" in claim
    assert "self._transport_claims.pop(transport, None)" in claim


def test_gatt_retry_is_not_advertisement_frequency():
    claim = RUNTIME.split("def _schedule_sensor_claim_reconcile", 1)[1].split(
        "def selected_sensor_ids", 1
    )[0]
    assert "_sensor_claim_reconcile_last_attempt" in claim
    assert "now - last_attempt < 1.0" in claim
    assert "desired == current" in claim


def test_workout_owner_is_visible_as_opt_in_diagnostic():
    assert "class PhysicalWorkoutOwnerSensor" in ENTITIES
    assert '_attr_entity_registry_enabled_default = False' in ENTITIES
    assert 'return ("workout_owner", None)' in ENTITIES
    assert '"release_policy": "when_all_overlapping_fitness_sessions_are_idle"' in ENTITIES
