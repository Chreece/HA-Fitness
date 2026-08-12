import sys
import types
from conftest import FITNESS, install_homeassistant_stubs, load_module

install_homeassistant_stubs()
pkg = sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
pkg.__path__ = [str(FITNESS.parent.parent)]
fitness_pkg = sys.modules.setdefault("custom_components.fitness", types.ModuleType("custom_components.fitness"))
fitness_pkg.__path__ = [str(FITNESS)]
providers_pkg = sys.modules.setdefault("custom_components.fitness.providers", types.ModuleType("custom_components.fitness.providers"))
providers_pkg.__path__ = [str(FITNESS / "providers")]
sleep = load_module("custom_components.fitness.providers.sleep", "providers/sleep.py")
SleepRecord = sleep.SleepRecord

def test_duration_and_stages_stay_on_same_provider_bundle():
    garmin = SleepRecord(
        source="garmin", provider_domain="garmin_connect",
        start="2026-08-11T21:00:00+00:00", end="2026-08-12T05:00:00+00:00",
        duration_s=344*60, light_sleep_s=180*60, deep_sleep_s=90*60, rem_sleep_s=74*60,
    )
    saa = SleepRecord(
        source="saa", provider_domain="sleep_as_android",
        start="2026-08-11T21:02:00+00:00", end="2026-08-12T05:01:00+00:00",
        duration_s=408*60, light_sleep_s=216*60, deep_sleep_s=104*60, rem_sleep_s=88*60, awake_s=32*60,
    )
    merged = sleep.merge_sleep_records([garmin, saa])
    assert merged.duration_s == 408*60
    assert merged.light_sleep_s == 216*60
    assert merged.deep_sleep_s == 104*60
    assert merged.rem_sleep_s == 88*60
    assert merged.field_sources["duration_s"] == "sleep_as_android"
    assert merged.field_sources["light_sleep_s"] == "sleep_as_android"
