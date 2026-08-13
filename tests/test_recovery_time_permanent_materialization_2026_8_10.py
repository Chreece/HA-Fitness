from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")


def test_estimated_recovery_time_is_always_materialized():
    setup = SENSOR[SENSOR.index("async def async_setup_entry"):]
    assert 'manager.remember_materialized_sensor(\n        "estimated_recovery_time",' in setup


def test_estimated_recovery_time_still_lives_on_recovery_device():
    marker = 'Desc(key="estimated_recovery_time"'
    start = SENSOR.index(marker)
    definition = SENSOR[start:start + 250]
    assert 'kind="sleep"' in definition
    assert 'metric="estimated_recovery_time"' in definition
    assert 'unit="h"' in definition
