from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("fitness_history", ROOT/"custom_components/fitness/history.py")
history=importlib.util.module_from_spec(spec); spec.loader.exec_module(history)

def test_epoch_future_and_nonfinite_are_rejected():
    now=datetime(2026,8,12,tzinfo=timezone.utc)
    pts,a=history.validate_series("vo2max", [{"timestamp":"1970-01-01T00:00:12+00:00","value":46},{"timestamp":(now+timedelta(days=2)).isoformat(),"value":46},{"timestamp":now.isoformat(),"value":"nan"}], now)
    assert pts == []
    assert a["rejected_samples"] == 3

def test_current_fitness_wins_over_recorder_same_day():
    now=datetime(2026,8,12,12,tzinfo=timezone.utc)
    raw=[{"timestamp":"2026-08-12T00:00:00+00:00","value":45,"source_type":"recorder_bootstrap","imported":True},{"timestamp":"2026-08-12T11:00:00+00:00","value":46,"source_type":"fitness_merged_current"}]
    pts,a=history.validate_series("vo2max",raw,now)
    assert len(pts)==1 and pts[0]["value"]==46
    assert a["rejection_reasons"]["duplicate_day"]==1

def test_28_day_result_requires_21_distinct_valid_days():
    now=datetime(2026,8,12,12,tzinfo=timezone.utc)
    raw=[{"timestamp":(now-timedelta(days=i)).isoformat(),"value":45+i/100,"source_type":"fitness_merged_current"} for i in range(20)]
    assert history.summarize("vo2max",raw,now)["mean_28d"] is None
    raw.append({"timestamp":(now-timedelta(days=20)).isoformat(),"value":45.2,"source_type":"fitness_merged_current"})
    s=history.summarize("vo2max",raw,now)
    assert s["mean_28d"] is not None and s["data_source"]=="fitness_canonical_history"

def test_sleep_requires_completed_interval():
    class S: start="2026-08-11T20:00:00+00:00"; end=None; duration_s=None
    assert history.validate_sleep(S()) == "incomplete_sleep"

def test_version_format_and_single_changelog():
    import json,re
    manifest=json.loads((ROOT/"custom_components/fitness/manifest.json").read_text())
    assert manifest["version"] == "0.0.0" or re.fullmatch(r"\d{4}\.\d{1,2}\.\d+(?:-(?:alpha|beta)\d+)?",manifest["version"])
    assert (ROOT/"CHANGELOG.md").exists()
    assert not list(ROOT.glob("CHANGELOG_*.md"))
