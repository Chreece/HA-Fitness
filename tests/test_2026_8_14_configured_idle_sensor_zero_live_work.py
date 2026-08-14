"""Configured merged sensors must be quiet when nobody is training."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()


def test_sensor_live_telemetry_requires_active_profile():
    block = RUNTIME.split("def sensor_live_telemetry_needed", 1)[1].split(
        "def _refresh_live_provider_gates", 1
    )[0]
    assert "if not self.sensor_is_accepted(sensor_id):" in block
    assert "if not self._profile_is_using_live_runtime(entry_id):" in block
    assert "self.sensors_for_profile(entry)" in block


def test_idle_publish_returns_before_metric_and_last_seen_state_writes():
    block = RUNTIME.split("def publish(self, sensor_id", 1)[1].split(
        "def live_values", 1
    )[0]
    guard = block.index("if not self._global_workout_epoch_active():")
    ret = block.index("return", guard)
    metric_bucket = block.index("value_bucket = self.sensor_values", ret)
    last_seen = block.index("_mark_last_seen_change", ret)
    claim = block.index("_claim_sensor_for_workout", ret)
    assert guard < ret < metric_bucket < last_seen < claim


def test_idle_endpoint_fast_path_does_not_schedule_claim_reconcile():
    refresh = RUNTIME.split("def refresh_transport_endpoint", 1)[1].split(
        "def register_transport_sensor", 1
    )[0]
    assert "if available and self._global_workout_epoch_active():" in refresh
    reconcile = RUNTIME.split("def _schedule_sensor_claim_reconcile", 1)[1].split(
        "async def _reconcile_profile_transports", 1
    )[0]
    assert "if not self._global_workout_epoch_active():" in reconcile
    assert "not self.sensor_is_accepted(sensor_id)" in reconcile


def test_claim_reconcile_has_global_live_epoch_guard():
    block = RUNTIME.split("def _schedule_sensor_claim_reconcile", 1)[1].split(
        "async def _reconcile_profile_transports", 1
    )[0]
    assert "if not self._global_workout_epoch_active():" in block


def test_ant_decode_gate_is_live_need_not_acceptance():
    assert "def refresh_telemetry_gates" in ANT
    refresh = ANT.split("def refresh_telemetry_gates", 1)[1].split(
        "def sensor_acceptance_changed", 1
    )[0]
    assert "sensor_live_telemetry_needed" in refresh
    assert "sensor_is_accepted" not in refresh


def test_session_boundaries_refresh_ant_decode_gates():
    prepare = RUNTIME.split("async def async_prepare_session", 1)[1].split(
        "async def async_finish_session", 1
    )[0]
    finish = RUNTIME.split("async def async_finish_session", 1)[1].split(
        "async def async_finish_recovery", 1
    )[0]
    assert "_refresh_live_provider_gates()" in prepare
    assert "_refresh_live_provider_gates()" in finish
