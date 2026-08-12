from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT/"custom_components/fitness/manager.py").read_text()
SAA = (ROOT/"custom_components/fitness/providers/sleep_adapters/sleep_as_android.py").read_text()
REGISTRY = (ROOT/"custom_components/fitness/providers/sleep_adapters/registry.py").read_text()

def test_sleep_as_android_is_completed_only():
    assert "if self._sleep_as_android_active:" in MANAGER
    assert "phase transition are intentionally" in MANAGER
    assert 'event_type == "stopped"' in MANAGER
    assert "_schedule_sleep_as_android_history_refresh(delay=1.5)" in MANAGER
    assert "_latest_completed_session" in SAA
    assert '"sleep_phase" in label' in REGISTRY

def test_recorder_reconstructs_stages():
    assert "get_significant_states" in MANAGER
    for stage in ("awake_s", "light_sleep_s", "deep_sleep_s", "rem_sleep_s"):
        assert stage in SAA
