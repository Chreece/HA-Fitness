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


def test_total_sleep_never_shorter_than_classified_sleep_stages():
    record = SleepRecord(
        source="sleep_as_android",
        provider_domain="sleep_as_android",
        start="2026-08-11T21:00:00+00:00",
        end="2026-08-12T05:00:00+00:00",
        duration_s=344 * 60,
        light_sleep_s=216 * 60,
        deep_sleep_s=104 * 60,
        rem_sleep_s=88 * 60,
    )
    merged = sleep.merge_sleep_records([record])
    assert merged.duration_s == (216 + 104 + 88) * 60
    assert merged.field_sources["duration_s"] == "sleep_as_android:classified_sleep_stages"


def test_longer_provider_duration_is_preserved_for_unclassified_sleep():
    record = SleepRecord(
        source="provider",
        provider_domain="provider",
        duration_s=450 * 60,
        light_sleep_s=216 * 60,
        deep_sleep_s=104 * 60,
        rem_sleep_s=88 * 60,
    )
    merged = sleep.merge_sleep_records([record])
    assert merged.duration_s == 450 * 60
