from pathlib import Path

ROOT = Path(__file__).parents[1]
COORD = (ROOT / "custom_components/fitness/device_adapters/garmin/coordinator.py").read_text()
GFDI = (ROOT / "custom_components/fitness/device_adapters/garmin/gfdi.py").read_text()


def _method(text: str, name: str) -> str:
    start = text.index(f"    async def {name}")
    next_method = text.find("\n    async def ", start + 1)
    if next_method < 0:
        next_method = text.find("\n    def ", start + 1)
    return text[start:] if next_method < 0 else text[start:next_method]


def test_garmin_handshake_failure_gets_one_fresh_bounded_reconnect():
    sync = _method(COORD, "_async_sync")
    assert "HANDSHAKE_RECONNECT_ATTEMPTS = 1" in COORD
    assert "HANDSHAKE_RECONNECT_DELAY = 1.5" in COORD
    assert "while True:" in sync
    assert "if handshake_retry >= HANDSHAKE_RECONNECT_ATTEMPTS:" in sync
    assert 'reason="Garmin GFDI handshake recovery reconnect"' in sync
    assert "await asyncio.sleep(HANDSHAKE_RECONNECT_DELAY)" in sync
    assert "_select_garmin_ble_route(" in sync
    assert "pair=False" in sync


def test_manual_retry_queued_during_auto_sync_keeps_earliest_delay():
    start = COORD.index("    def _schedule_after_current")
    end = COORD.index("\n    def _publish", start)
    block = COORD[start:end]
    assert "previous = self._queued.get(canonical)" in block
    assert "min(delay, previous[1])" in block
    assert "previous[0] is current" in block


def test_full_sync_prioritizes_workout_and_health_without_treating_every_numeric_file_as_fit():
    # FIT-labelled unknown families remain eligible, but a bare numeric FileSync
    # type is not sufficient evidence that an internal Garmin file is FIT.
    assert 'name.startswith("FIT_TYPE_")' in GFDI
    assert 'item.type_code in {4, 9, 14, 15, 28, 32}' in GFDI
    assert "def _modern_sync_priority" in GFDI
    assert 'name == "FIT_TYPE_4"' in GFDI
    assert "name in HEALTH_FIT_TYPE_NAMES" in GFDI
    assert "candidates.sort(key=self._modern_sync_priority, reverse=True)" in GFDI
    assert "preferred_subtypes = {4, 9, 14, 15, 28, 32}" in GFDI


def test_modern_activity_count_accepts_numeric_type_when_name_is_missing():
    assert "or item.type_code == 4" in GFDI
    assert "or item.type_code == 4" in COORD
