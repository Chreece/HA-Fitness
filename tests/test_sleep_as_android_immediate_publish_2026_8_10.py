from datetime import datetime, timedelta, timezone
from pathlib import Path
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
adapters_pkg = sys.modules.setdefault("custom_components.fitness.providers.sleep_adapters", types.ModuleType("custom_components.fitness.providers.sleep_adapters"))
adapters_pkg.__path__ = [str(FITNESS / "providers" / "sleep_adapters")]

sleep = load_module("custom_components.fitness.providers.sleep", "providers/sleep.py")
load_module("custom_components.fitness.providers.sleep_adapters.registry_types", "providers/sleep_adapters/registry_types.py")
saa = load_module("custom_components.fitness.providers.sleep_adapters.sleep_as_android", "providers/sleep_adapters/sleep_as_android.py")
SleepRecord = sleep.SleepRecord

ROOT = Path(__file__).resolve().parents[1]
MANAGER = (ROOT / "custom_components/fitness/manager.py").read_text(encoding="utf-8")


def _event(at, event_type):
    return {"last_updated": at, "attributes": {"event_type": event_type}}


def test_live_event_timeline_can_publish_completed_sleep_without_recorder():
    start = datetime(2026, 8, 12, 21, 57, tzinfo=timezone.utc)
    end = start + timedelta(hours=7, minutes=28)
    tracking = [_event(start, "started"), _event(end, "stopped")]
    phases = [
        _event(start, "light_sleep"),
        _event(start + timedelta(hours=2), "deep_sleep"),
        _event(start + timedelta(hours=3, minutes=40), "rem"),
        _event(start + timedelta(hours=5), "light_sleep"),
    ]
    record = saa.record_from_event_history(
        tracking_entity_id="event.sleep_tracking",
        phase_entity_id="event.sleep_phase",
        tracking_states=tracking,
        phase_states=phases,
    )
    assert record is not None
    assert record.end == end.isoformat()
    assert record.duration_s == (end - start).total_seconds()
    assert record.light_sleep_s is not None
    assert record.deep_sleep_s is not None
    assert record.rem_sleep_s is not None


def test_manager_publishes_saa_on_stopped_before_recorder_and_retries_recorder():
    assert "_sleep_as_android_live_events" in MANAGER
    assert "immediate = record_from_event_history(" in MANAGER
    assert "records.append(immediate)" in MANAGER
    assert "self._notify_sleep()" in MANAGER
    assert "retries=3" in MANAGER
    assert "[2.0, 5.0, 10.0]" in MANAGER


def test_stale_sparse_saa_score_does_not_merge_into_new_night():
    end = datetime(2026, 8, 13, 3, 44, tzinfo=timezone.utc)
    event_record = SleepRecord(
        source="event.sleep_tracking", provider_domain="sleep_as_android",
        start=(end - timedelta(hours=7)).isoformat(), end=end.isoformat(),
        duration_s=7 * 3600, light_sleep_s=4 * 3600, deep_sleep_s=2 * 3600,
        rem_sleep_s=3600, provider_domains=["sleep_as_android"],
    )
    stale_score = SleepRecord(
        source="sensor.sleep_score", provider_domain="sleep_as_android", score=88,
        observed_at=(end - timedelta(hours=8)).isoformat(),
        provider_domains=["sleep_as_android"],
    )
    merged = sleep.merged_sleeps([event_record, stale_score])
    assert len(merged) == 2
    timed = next(item for item in merged if item.end == end.isoformat())
    assert timed.score is None


def test_fresh_sparse_saa_score_can_merge_into_completed_night():
    end = datetime(2026, 8, 13, 3, 44, tzinfo=timezone.utc)
    event_record = SleepRecord(
        source="event.sleep_tracking", provider_domain="sleep_as_android",
        start=(end - timedelta(hours=7)).isoformat(), end=end.isoformat(),
        duration_s=7 * 3600, provider_domains=["sleep_as_android"],
    )
    score = SleepRecord(
        source="sensor.sleep_score", provider_domain="sleep_as_android", score=91,
        observed_at=(end + timedelta(minutes=5)).isoformat(),
        provider_domains=["sleep_as_android"],
    )
    merged = sleep.merged_sleeps([event_record, score])
    assert len(merged) == 1
    assert merged[0].score == 91
