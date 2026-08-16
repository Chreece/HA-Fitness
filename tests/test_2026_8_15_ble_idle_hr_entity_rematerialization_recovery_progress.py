"""Regression guards for BLE session telemetry, entity recreation and Recovery UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BT = (ROOT / "custom_components/fitness/live/bluetooth.py").read_text()
ENTITIES = (ROOT / "custom_components/fitness/live/ha_entities.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
BACKEND = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_accepted_ble_sensor_only_probes_identity_while_idle():
    assert "self._schedule_idle_connection" not in BT
    assert "self._schedule_identity_probe(sensor_id)" in BT
    assert "self._schedule_identity_probe(sensor.sensor_id)" in BT
    assert "await self._subscribe(sensor, client)" in BT  # live profile connection path


def test_profile_disconnect_closes_unowned_gatt_and_shutdown_closes_all_clients():
    assert "if users:\n                return" in BT
    assert "client = self._clients.pop(sensor_id, None)" in BT
    assert "explicitly close all clients during integration shutdown" in BT


def test_deleted_physical_entities_can_be_recreated_for_same_sensor_id():
    assert "def _claim(marker: tuple[str, str, str], unique_id: str) -> bool:" in ENTITIES
    assert 'entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)' in ENTITIES
    assert "materialized.discard(marker)" in ENTITIES
    assert '_claim(key, f"fitness_{sensor_id}_{metric}")' in ENTITIES
    assert '_claim(key, f"fitness_{sensor_id}_last_seen")' in ENTITIES


def test_training_recovery_bar_is_removed_and_recovery_progress_uses_readiness_score_style():
    assert "trainingRecoveryBar" not in FRONTEND
    assert "readinessTrainingStack" not in FRONTEND
    assert 'kind:"progress"' in FRONTEND
    assert 'label:l.recovery_progress_label || "Recovery progress"' in FRONTEND
    assert "recoveryProgressBar" in FRONTEND
    assert "recovery-progress\"><i" not in FRONTEND
    assert "recovery-score-track" in FRONTEND


def test_dashboard_cache_is_bumped():
    assert 'FITNESS_DASHBOARD_VERSION = "unreleased-82"' in FRONTEND
    assert '?v=unreleased-82' in BACKEND
