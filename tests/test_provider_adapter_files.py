from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLEEP = ROOT / "custom_components/fitness/providers/sleep_adapters"
WORKOUT = ROOT / "custom_components/fitness/providers/workout_adapters"

def test_every_explicit_sleep_provider_has_its_own_adapter_module():
    expected = {
        "garmin", "oura", "fitbit", "withings", "whoop", "suunto",
        "sleepiq", "eight_sleep", "sleep_as_android",
    }
    assert expected <= {path.stem for path in SLEEP.glob("*.py")}
    registry = (SLEEP / "registry.py").read_text(encoding="utf-8")
    for provider in expected:
        assert f"{provider}.SPEC" in registry

def test_additional_workout_domains_have_explicit_adapter_owners():
    registry = (WORKOUT / "registry.py").read_text(encoding="utf-8")
    for provider in ("suunto", "fitbit", "withings"):
        assert (WORKOUT / f"{provider}.py").exists()
        assert f'WorkoutAdapterSpec("{provider}"' in registry
