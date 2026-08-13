from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")
SENSOR = (ROOT / "custom_components/fitness/sensor.py").read_text(encoding="utf-8")
JS = (ROOT / "custom_components/fitness/frontend/fitness-dashboard.js").read_text(encoding="utf-8")


def test_recovery_time_uses_latest_workout_not_only_local_history():
    start = MANAGER.index("def recovery_time_evaluation")
    end = MANAGER.index("def readiness_evaluation", start)
    section = MANAGER[start:end]
    assert "latest = self.latest_workout()" in section
    assert "workouts = self.local_workouts()" not in section


def test_recovery_time_is_exposed_on_recovery_device_and_card():
    assert 'Desc(key="estimated_recovery_time"' in SENSOR
    assert 'kind="sleep"' in SENSOR[SENSOR.index('Desc(key="estimated_recovery_time"'):][:200]
    assert "e.estimated_recovery_time" in JS
    assert 'const recoveryTime = this._hass.states[e.estimated_recovery_time]' in JS
