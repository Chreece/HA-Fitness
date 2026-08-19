from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_direct_history_coordinator_exposes_full_manual_sync_contract():
    text = (ROOT / "custom_components/fitness/device_adapters/history_coordinator.py").read_text()
    assert "async def async_sync_now" in text
    assert "complete protocol transaction" in text


def test_archive_button_uses_coordinator_sync_now_and_exposes_scope():
    text = (ROOT / "custom_components/fitness/button.py").read_text()
    assert '"sync_scope": "full"' in text
    assert '"sync_capabilities"' in text
    assert 'getattr(coordinator, "async_sync_now", None)' in text


def test_all_direct_adapters_declare_explicit_sync_capabilities():
    expected = {
        "bangle/adapter.py": {"health_history", "sleep_history", "workout_history", "gps_tracks", "device_state"},
        "cycplus_adapter.py": {"workout_history", "gps_tracks", "device_state"},
        "garmin/adapter.py": {"workout_history", "gps_tracks"},
        "hplus/adapter.py": {"health_history", "device_state"},
        "miband1/adapter.py": {"health_history", "sleep_history", "device_state"},
        "miband2/adapter.py": {"health_history", "device_state"},
        "ultrahuman/adapter.py": {"health_history", "device_state"},
        "zetime/adapter.py": {"health_history", "sleep_history", "device_state"},
    }
    base = ROOT / "custom_components/fitness/device_adapters"
    for rel, capabilities in expected.items():
        text = (base / rel).read_text()
        assert "sync_capabilities=frozenset" in text
        for capability in capabilities:
            assert repr(capability) in text or f'"{capability}"' in text
