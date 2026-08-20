from pathlib import Path
import json

ROOT = Path(__file__).parents[1]
COORD = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text()
GFDI = (ROOT / "custom_components/fitness/device_adapters/garmin/gfdi.py").read_text()
STRINGS = json.loads((ROOT / "custom_components/fitness/strings.json").read_text())
EL = json.loads((ROOT / "custom_components/fitness/translations/el.json").read_text())


def _method(text: str, name: str) -> str:
    start = text.index(f"    async def {name}")
    next_async = text.find("\n    async def ", start + 1)
    next_sync = text.find("\n    def ", start + 1)
    ends = [value for value in (next_async, next_sync) if value >= 0]
    end = min(ends) if ends else len(text)
    return text[start:end]


def test_manual_sync_respects_short_post_batch_cooldown():
    sync_now = _method(COORD, "async_sync_now")
    assert "MIN_SESSION_RECONNECT_GAP = 60.0" in COORD
    assert 'last_batch = _dt(state.get("last_batch_success"))' in sync_now
    assert 'sync_state="cooldown"' in sync_now
    assert 'last_error_code="none"' in sync_now
    assert "MIN_SESSION_RECONNECT_GAP - age" in sync_now
    assert "self.schedule(canonical, delay=delay, force=True)" in sync_now


def test_successful_partial_batch_is_reported_as_cooldown_not_failure():
    sync = _method(COORD, "_async_sync")
    assert 'sync_state="cooldown" if more_work else "ready"' in sync
    assert 'last_batch_success=now_utc.isoformat()' in sync
    assert 'last_error_code="none"' in sync
    assert '"garmin_last_batch_success": state.get("last_batch_success")' in COORD
    assert '"garmin_next_attempt": state.get("next_attempt")' in COORD


def test_transient_post_batch_handshake_failure_does_not_poison_last_error():
    sync = _method(COORD, "_async_sync")
    assert '"cooldown"' in sync
    assert "if partial_retry" in sync
    assert "active_host_contention" in sync
    assert 'last_error_code="none" if partial_retry else error_code' in sync
    assert 'last_transient_error_code=error_code if partial_retry else "none"' in sync


def test_one_bad_filesync_record_cannot_abort_the_whole_archive_session():
    sync = _method(COORD, "_async_sync")
    assert "MAX_FILE_VALIDATION_FAILURES = 3" in COORD
    assert 'failures = state.setdefault("validation_failures", {})' in sync
    assert '"kind": "invalid"' in sync
    assert 'failure_count >= MAX_FILE_VALIDATION_FAILURES' in sync
    assert '"Garmin device file validation failed' in sync
    assert "continue" in sync
    assert '"garmin_quarantined_file_count": state.get("quarantined_file_count", 0)' in COORD


def test_full_sync_requires_actual_fit_evidence_for_opaque_modern_records():
    candidate = GFDI.split("def _modern_sync_candidate", 1)[1].split(
        "def _modern_sync_priority", 1
    )[0]
    assert 'name.startswith("FIT_TYPE_")' in candidate
    assert 'item.type_code in {4, 9, 14, 15, 28, 32}' in candidate
    assert "item.type_code is not None" not in candidate


def test_cooldown_and_new_diagnostics_are_localized_in_greek():
    en_sensor = STRINGS["entity"]["sensor"]
    el_sensor = EL["entity"]["sensor"]
    assert en_sensor["garmin_sync_state"]["state"]["cooldown"] == "Device cooldown"
    assert el_sensor["garmin_sync_state"]["state"]["cooldown"] == "Χρόνος αναμονής συσκευής"
    assert el_sensor["garmin_imported_file_count"]["name"] == "Ληφθέντα αρχεία συσκευής"
    assert "garmin_last_batch_success" in el_sensor
    assert "garmin_next_attempt" in el_sensor
    assert "garmin_quarantined_file_count" in el_sensor
