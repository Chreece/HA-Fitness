from pathlib import Path

ROOT = Path(__file__).parents[1]
REGISTRY = (ROOT / "custom_components/fitness/device_archives.py").read_text()
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text()
GARMIN = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text()

def test_archive_registry_schedules_nonblocking_startup_sync():
    assert 'schedule_archive_sync(delay=45.0, force=True, reason="home_assistant_startup")' in REGISTRY

def test_archive_registry_wakes_device_after_real_reappearance():
    assert "now - previous >= 300.0" in REGISTRY
    assert 'reason="device_available_again"' in REGISTRY

def test_fresh_completed_sleep_schedules_profile_archive_sync():
    assert 'reason="fresh_completed_sleep"' in MANAGER
    assert "profile_id=self.entry.entry_id" in MANAGER
    assert "delay=8.0" in MANAGER

def test_garmin_restart_caps_stale_error_timer_to_startup_cooldown():
    assert "STARTUP_RESUME_DELAY = 45.0" in GARMIN
    assert 'if status == "error" and not pending:' in GARMIN
    assert "due = min(due, now + timedelta(seconds=STARTUP_RESUME_DELAY))" in GARMIN

def test_garmin_restored_timer_log_exposes_error_and_due_checkpoint():
    assert "error=%s next_attempt=%s" in GARMIN
