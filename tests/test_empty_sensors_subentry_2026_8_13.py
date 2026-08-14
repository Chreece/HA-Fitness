from pathlib import Path

R = Path("custom_components/fitness/live/runtime.py").read_text()


def test_sensor_subentry_is_not_created_unconditionally_on_hub_setup():
    block = R[R.index("async def async_register_hub"):R.index("def _cleanup_legacy_profile_infrastructure")]
    assert "self.ensure_sensors_subentry()" not in block
    assert "self.remove_sensors_subentry_if_empty()" in block


def test_empty_sensor_subentry_is_removed_after_last_sensor_is_forgotten():
    assert "def remove_sensors_subentry_if_empty" in R
    assert "async_remove_subentry" in R
    block = R[R.index("def _forget_sensor_memory"):R.index("def _listen_for_registry_deletions")]
    assert "self.remove_sensors_subentry_if_empty()" in block


def test_sensor_subentry_remains_lazy_until_an_accepted_sensor_needs_a_device():
    block = R[R.index("def ensure_sensor_device"):R.index("def request_hub_reload")]
    assert "subentry_id = self._sensor_subentry_id()" in block
