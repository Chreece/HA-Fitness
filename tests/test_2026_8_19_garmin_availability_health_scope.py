from pathlib import Path

ROOT = Path(__file__).parents[1]
ARCH = (ROOT / "custom_components/fitness/device_archives.py").read_text()
BT = (ROOT / "custom_components/fitness/live/bluetooth.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
GARMIN = (ROOT / "custom_components/fitness/device_adapters/garmin/adapter.py").read_text()
GFDI = (ROOT / "custom_components/fitness/device_adapters/garmin/gfdi.py").read_text()
COORD = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text()

def test_real_unavailable_to_available_transition_forces_archive_retry():
    assert "was_available = bool(known_endpoint is not None and known_endpoint.available)" in BT
    assert "became_available=bool(" in BT
    assert "not was_available" in BT
    assert "became_available: bool = False" in ARCH
    assert 'reason="device_available_again"' in ARCH
    assert "now - last_retry < 60.0" in ARCH

def test_cached_startup_replay_does_not_bypass_radio_cooldown():
    assert "self._availability_retry_after = self.provider.hass.loop.time() + 45.0" in ARCH
    assert "now < self._availability_retry_after" in ARCH
    assert 'reason="home_assistant_startup"' in ARCH

def test_fresh_sleep_archive_sync_is_deduped_independently_from_ai():
    assert "self.archive_sleep_sync_key: str | None = None" in MANAGER
    assert '"archive_sleep_sync_key": self.archive_sleep_sync_key' in MANAGER
    assert 'self.archive_sleep_sync_key = stored.get("archive_sleep_sync_key")' in MANAGER
    assert "sleep_key != self.archive_sleep_sync_key" in MANAGER
    assert 'reason="fresh_completed_sleep"' in MANAGER

def test_direct_garmin_sync_includes_standard_health_and_sleep_archives():
    assert '"health_history"' in GARMIN
    assert '"sleep_history"' in GARMIN
    assert '"device_state"' in GARMIN
    for fit_type in ("FIT_TYPE_9", "FIT_TYPE_14", "FIT_TYPE_15", "FIT_TYPE_28", "FIT_TYPE_32"):
        assert fit_type in GFDI
    assert "async_sync_catalog" in GFDI

def test_garmin_logs_complete_read_only_file_type_inventory_for_health_support():
    assert "self.catalog_type_counts: dict[str, int] = {}" in GFDI
    assert 'state["catalog_file_types"] = catalog_types' in COORD
    assert "Garmin read-only catalogue for %s" in COORD
