from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sleep_deficit_never_falls_back_to_latest_night():
    source = (ROOT / "custom_components/fitness/sensor.py").read_text()
    start = source.index('"sleep_deficit_7d": sleep_long_term.get("sleep_deficit_7d_min")')
    assert "420.0 - latest_sleep" not in source[start - 500:start + 500]


def test_sleep_as_android_imports_completed_recorder_window():
    manager = (ROOT / "custom_components/fitness/manager.py").read_text()
    adapter = (ROOT / "custom_components/fitness/providers/sleep_adapters/sleep_as_android.py").read_text()
    assert "datetime.now(timezone.utc) - timedelta(days=8)" in manager
    assert "records_from_event_history(" in manager
    assert "for record in reconstructed:" in manager
    assert "def records_from_event_history(" in adapter


def test_sleep_deficit_requires_longitudinal_samples():
    manager = (ROOT / "custom_components/fitness/manager.py").read_text()
    assert "if self.age() >= 18 and len(seven) >= 5:" in manager
    assert "deficits = [max(0.0, 7 * 3600 - seconds) for seconds in seven]" in manager
