"""Regression guards for BLE idle telemetry, entity recreation and Recovery UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BT = (ROOT / "custom_components/fitness/live/bluetooth.py").read_text()
ENTITIES = (ROOT / "custom_components/fitness/live/ha_entities.py").read_text()
FRONTEND = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text()
BACKEND = (ROOT / "custom_components/fitness/dashboard.py").read_text()


def test_accepted_ble_sensor_subscribes_to_raw_gatt_metrics_while_idle():
    assert "self._schedule_idle_connection(sensor_id)" in BT
    assert "await self._subscribe(sensor, client)" in BT
    assert "Bluetooth idle telemetry connect failed" in BT
    assert "not self.runtime.sensor_is_accepted(sensor_id)" in BT
    assert "self._ant_covers_ble_metrics(sensor)" in BT


def test_ble_idle_connection_is_preserved_after_profile_disconnect_and_closed_on_shutdown():
    assert "sensor_id in self._idle_connected_sensors" in BT
    assert "this accepted BLE-only sensor still" in BT
    assert "Idle raw-telemetry connections are not necessarily owned by a profile" in BT


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
    assert 'FITNESS_DASHBOARD_VERSION = "2026.8.11.14"' in FRONTEND
    assert '?v=2026.8.11.14' in BACKEND
