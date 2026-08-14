"""Continuous ANT traffic must never repeatedly run control-plane work."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()


def test_topology_save_is_true_quiet_period_debounce():
    block = RUNTIME.split("def _schedule_save", 1)[1].split(
        "def adapter_present", 1
    )[0]
    assert "self._save_handle.cancel()" in block
    assert "call_later(3.0" in block
    assert "await asyncio.sleep(0)" not in block


def test_structure_materialization_restarts_quiet_timer():
    block = RUNTIME.split("def _notify_structure_throttled", 1)[1].split(
        "def suppress_entry_reload_once", 1
    )[0]
    assert "self._structure_notify_handle.cancel()" in block
    assert "call_later(2.0" in block


def test_device_info_refresh_restarts_quiet_timer():
    block = RUNTIME.split("def _schedule_sensor_device_refresh", 1)[1].split(
        "def ensure_sensor_device", 1
    )[0]
    assert "existing.cancel()" in block
    assert "call_later(" in block
    assert "3.0, _refresh" in block


def test_accepted_ant_mailbox_is_two_hz_not_four_hz():
    block = ANT.split("def _flush_publish_device", 1)[1].split(
        "def _finish_publish_window", 1
    )[0]
    assert "call_later(0.5" in block
    assert "call_later(0.25" not in block


def test_physical_sensor_state_writes_are_one_hz():
    block = RUNTIME.split("def _notify_values_throttled", 1)[1].split(
        "def _mark_last_seen_change", 1
    )[0]
    assert "elapsed >= 1.0" in block
    assert "1.0 - elapsed" in block


def test_idle_radio_packets_do_not_scan_profiles_for_workout_claims():
    block = RUNTIME.split("def publish(", 1)[1].split(
        "def live_values", 1
    )[0]
    guard = block.index("if not self._global_workout_epoch_active():")
    claim = block.index("owner = self._claim_sensor_for_workout(sensor_id)")
    assert guard < claim
