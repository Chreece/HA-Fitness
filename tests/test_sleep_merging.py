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


def test_same_night_from_two_providers_merges_without_duplicate():
    garmin = SleepRecord(
        source="garmin",
        provider_domain="garmin_connect",
        provider_domains=["garmin_connect"],
        start="2026-08-10T21:00:00+00:00",
        end="2026-08-11T05:00:00+00:00",
        duration_s=7.5 * 3600,
        rem_sleep_s=90 * 60,
        hrv_ms=54,
    )
    saa = SleepRecord(
        source="saa",
        provider_domain="sleep_as_android",
        provider_domains=["sleep_as_android"],
        start="2026-08-10T20:57:00+00:00",
        end="2026-08-11T05:03:00+00:00",
        duration_s=7.7 * 3600,
        deep_sleep_s=80 * 60,
    )

    merged = sleep.merged_sleeps([garmin, saa])
    assert len(merged) == 1
    result = merged[0]
    assert set(result.provider_domains) == {"garmin_connect", "sleep_as_android"}
    assert result.rem_sleep_s == 90 * 60
    assert result.deep_sleep_s == 80 * 60
    assert result.hrv_ms == 54


def test_nap_does_not_merge_into_night_sleep():
    night = SleepRecord(
        source="night",
        provider_domain="garmin_connect",
        start="2026-08-10T21:00:00+00:00",
        end="2026-08-11T05:00:00+00:00",
    )
    nap = SleepRecord(
        source="nap",
        provider_domain="oura",
        start="2026-08-11T12:00:00+00:00",
        end="2026-08-11T12:40:00+00:00",
    )
    assert len(sleep.merged_sleeps([night, nap])) == 2


def test_complete_link_prevents_transitive_sleep_chain():
    a = SleepRecord(source="a", provider_domain="a", start="2026-08-10T21:00:00+00:00", end="2026-08-11T05:00:00+00:00")
    b = SleepRecord(source="b", provider_domain="b", start="2026-08-10T22:30:00+00:00", end="2026-08-11T06:30:00+00:00")
    c = SleepRecord(source="c", provider_domain="c", start="2026-08-11T00:30:00+00:00", end="2026-08-11T08:30:00+00:00")
    assert len(sleep.merged_sleeps([a, b, c])) >= 2


def test_sparse_nightly_aggregate_merges_by_observation_time():
    timed = SleepRecord(
        source="timed",
        provider_domain="garmin_connect",
        start="2026-08-10T21:00:00+00:00",
        end="2026-08-11T05:00:00+00:00",
        observed_at="2026-08-11T05:20:00+00:00",
        rem_sleep_s=5000,
    )
    aggregate = SleepRecord(
        source="aggregate",
        provider_domain="fitbit",
        observed_at="2026-08-11T06:00:00+00:00",
        deep_sleep_s=4000,
    )
    merged = sleep.merged_sleeps([timed, aggregate])
    assert len(merged) == 1
    assert merged[0].rem_sleep_s == 5000
    assert merged[0].deep_sleep_s == 4000
