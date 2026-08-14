from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "custom_components/fitness/live/runtime.py").read_text()
INIT = (ROOT / "custom_components/fitness/__init__.py").read_text()


def test_deleted_sensor_is_persistently_revoked_until_reassigned():
    assert "self._requires_reassignment: set[str] = set()" in RUNTIME
    assert 'stored.get("requires_reassignment")' in RUNTIME
    assert '"requires_reassignment": sorted(self._requires_reassignment)' in RUNTIME
    accepted = RUNTIME[RUNTIME.index("def sensor_is_accepted"):RUNTIME.index("def mark_sensor_accepted")]
    assert "sensor_id in self._requires_reassignment" in accepted
    marked = RUNTIME[RUNTIME.index("def mark_sensor_accepted"):RUNTIME.index("def remove_unaccepted_sensor_device")]
    assert "self._requires_reassignment.discard(sensor_id)" in marked


def test_device_delete_revokes_immediately_and_persists_after_return():
    assert "await runtime.async_forget_sensor" in INIT
    forgotten = RUNTIME[RUNTIME.index("async def async_forget_sensor"):RUNTIME.index("def _listen_for_registry_deletions")]
    assert "await self._async_save_adapter_config()" not in forgotten
    assert "self._schedule_save()" in forgotten
    assert "self._schedule_deleted_sensor_cleanup" in forgotten


def test_revoked_sensor_is_rediscoverable_despite_stale_profile_selection():
    discovery = RUNTIME[RUNTIME.index("def _schedule_sensor_discovery"):RUNTIME.index("def sensor_is_accepted")]
    assert "sensor_id not in self._requires_reassignment" in discovery
    assert 'context={"source": "integration_discovery"}' in discovery
