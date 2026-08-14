from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANT = (ROOT / "custom_components/fitness/live/antplus.py").read_text()
RECEIVER = (ROOT / "custom_components/fitness/live/antplus_core/receiver.py").read_text()
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
DIAG = (ROOT / "custom_components/fitness/live/antplus_core/diagnostics.py").read_text()


def test_ant_metric_callbacks_are_coalesced_before_ha_publish():
    assert "self._publish_lock = threading.Lock()" in ANT
    assert "self._publish_scheduled: set[int] = set()" in ANT
    assert "if device_id in self._publish_scheduled:" in ANT
    assert "self.hass.loop.call_soon_threadsafe(self._flush_publish_device, device_id)" in ANT
    # Regression: never schedule one complete HA publish directly per changed metric.
    assert "call_soon_threadsafe(self._publish_device, device)" not in ANT


def test_deleted_ant_sensor_evicts_receiver_identity_for_rediscovery():
    assert "def forget_device(self, device_id: int)" in RECEIVER
    assert "self.devices.pop(device_id, None)" in RECEIVER
    assert "self._discovery_candidates.pop(key, None)" in RECEIVER
    assert 'if endpoint.transport == "antplus":' in RUNTIME
    assert 'forget(int(device_number))' in RUNTIME


def test_radio_state_writes_are_coalesced_and_idle_profiles_skipped():
    assert "def _notify_values_throttled(" in RUNTIME
    assert "0.5 - elapsed" in RUNTIME
    assert "self._notify_values_throttled(physical_dirty)" in RUNTIME
    assert "_pending_sensor_value_changes" in RUNTIME
    assert "_notify_sensor_value_changes" in RUNTIME
    assert "def _profile_is_live_session" in RUNTIME
    assert "manager.session_armed or manager.session_active" in RUNTIME


def test_hot_cpu_watchdog_does_not_dump_every_thread_automatically():
    watchdog = DIAG[DIAG.index("def _watchdog_run"):DIAG.index("    def inc(")]
    assert "hot-CPU snapshot" in watchdog
    assert "log_diagnostics(self)" not in watchdog
    assert "format_thread_stacks()" not in watchdog
